import fs from "node:fs/promises";
import path from "node:path";
import { chromium } from "@playwright/test";

const APP_URL = process.env.APP_URL || "http://127.0.0.1:5173";
const API_BASE = process.env.API_BASE || "http://127.0.0.1:8000";
const BUDGET_URL =
  process.env.BUDGET_URL ||
  "https://www.singaporebudget.gov.sg/budget-speech/budget-statement/e-give-families-more-support-and-greater-assurance#Give-Families-More-Support-and-Greater-Assurance";
const OUTPUT_DIR = process.env.OUTPUT_DIR || path.join(process.cwd(), "../output/playwright");

const ONBOARDING_TIMEOUT = 120_000;
const EXTRACTION_TIMEOUT = 600_000;
const POPULATION_TIMEOUT = 600_000;
const SIMULATION_TIMEOUT = 1_200_000;
const REPORT_TIMEOUT = 600_000;

function normalizeText(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function compactWhitespace(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function findDuplicateEntries(lines) {
  const counts = new Map();
  for (const line of lines) {
    const key = normalizeText(line);
    if (!key) continue;
    counts.set(key, (counts.get(key) || 0) + 1);
  }

  return Array.from(counts.entries())
    .filter(([, count]) => count > 1)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 20)
    .map(([text, count]) => ({ text, count }));
}

function collectRefusalMatches(lines) {
  const refusalRegex = /\b(as an ai|i cannot|i can't|i am unable|i do not have personal|i don't have personal|i cannot provide)\b/i;
  const matches = [];
  for (const line of lines) {
    if (refusalRegex.test(line)) {
      matches.push(compactWhitespace(line).slice(0, 400));
    }
  }
  return matches;
}

function collectFirstPersonMatches(lines) {
  const firstPersonRegex = /\b(i|me|my|mine|we|our|ours|us)\b/i;
  const matches = [];
  for (const line of lines) {
    if (firstPersonRegex.test(line)) {
      matches.push(compactWhitespace(line).slice(0, 400));
    }
  }
  return matches;
}

async function waitForVisibleButton(page, name, timeoutMs) {
  const locator = page.getByRole("button", { name });
  await locator.first().waitFor({ state: "visible", timeout: timeoutMs });
  return locator.first();
}

async function waitForEnabledButton(page, name, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  const locator = page.getByRole("button", { name }).first();
  await locator.waitFor({ state: "visible", timeout: timeoutMs });

  while (Date.now() < deadline) {
    if (await locator.isEnabled()) {
      return locator;
    }
    await page.waitForTimeout(800);
  }

  throw new Error(`Button ${name} did not become enabled within ${timeoutMs}ms`);
}

async function clickWhenEnabled(page, name, timeoutMs) {
  const button = await waitForEnabledButton(page, name, timeoutMs);
  await button.click();
}

async function waitForChatSendReady(page, timeoutMs = 60_000) {
  const sendButton = page.locator("button.h-10.w-10.shrink-0").first();
  await sendButton.waitFor({ state: "visible", timeout: timeoutMs });
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await sendButton.isEnabled()) {
      return;
    }
    await page.waitForTimeout(300);
  }
  throw new Error("Chat send button did not become ready in time.");
}

async function patchProviderCatalog(page) {
  await page.route("**/api/v2/providers", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    const patched = Array.isArray(body)
      ? body.map((provider) => {
          if (String(provider?.name || "").toLowerCase() === "gemini") {
            return { ...provider, requires_api_key: false };
          }
          return provider;
        })
      : body;
    await route.fulfill({ response, json: patched });
  });
}

async function expectChatOutcome(page, endpointMatcher, timeoutMs = 180_000) {
  const response = await page
    .waitForResponse(
      (res) => endpointMatcher.test(res.url()) && res.request().method() === "POST",
      { timeout: timeoutMs },
    )
    .catch(() => null);

  if (!response) {
    const errorText = await page
      .locator("p.text-xs.text-destructive")
      .first()
      .textContent()
      .then((value) => compactWhitespace(value || ""))
      .catch(() => "");
    return {
      ok: false,
      status: null,
      response_count: 0,
      ui_error_visible: Boolean(errorText),
      detail: errorText || "No backend response and no visible chat error.",
    };
  }

  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  const responses = Array.isArray(payload?.responses)
    ? payload.responses
    : (typeof payload?.response === "string" && payload.response.trim()
        ? [{ content: payload.response }]
        : []);
  if (response.ok() && responses.length > 0) {
    return {
      ok: true,
      status: response.status(),
      response_count: responses.length,
      ui_error_visible: false,
      detail: null,
    };
  }

  const errorVisible = await page.locator("p.text-xs.text-destructive").first().isVisible().catch(() => false);
  return {
    ok: false,
    status: response.status(),
    response_count: responses.length,
    ui_error_visible: errorVisible,
    detail: compactWhitespace(payload?.detail || payload?.message || ""),
  };
}

async function runGroupChatProbe(page, segmentButtonName, promptText) {
  await page.getByRole("button", { name: segmentButtonName }).first().click();
  await waitForChatSendReady(page, 60_000);
  const input = page.getByPlaceholder("Ask the group a question...").first();
  await input.fill(promptText);
  await input.press("Enter");
  return expectChatOutcome(page, /\/api\/v2\/console\/session\/[^/]+\/chat\/group$/i);
}

async function runOneToOneChatProbe(page, promptText) {
  await page.getByRole("button", { name: "1:1 Chat" }).first().click();
  const search = page.getByPlaceholder("Search agents...").first();
  await search.fill("a");

  const firstCandidate = page.locator("div.max-h-36 button").first();
  await firstCandidate.waitFor({ state: "visible", timeout: 60_000 });
  await firstCandidate.click();

  await waitForChatSendReady(page, 60_000);
  const directInput = page.locator('input[placeholder^="Ask "]').first();
  await directInput.waitFor({ state: "visible", timeout: 30_000 });
  await directInput.fill(promptText);
  await directInput.press("Enter");

  return expectChatOutcome(page, /\/api\/v2\/console\/session\/[^/]+\/chat\/agent\//i);
}

async function navigateSidebar(page, labelPattern, timeoutMs = 60_000) {
  const button = page.getByRole("button", { name: labelPattern }).first();
  await button.waitFor({ state: "visible", timeout: timeoutMs });
  await button.click();
}

async function run() {
  const startedAt = new Date().toISOString();
  let sessionId = null;
  let createdSessionId = null;
  const observedSessionIds = new Set();

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();
  page.setDefaultTimeout(120_000);

  page.on("request", (request) => {
    const match = request.url().match(/\/api\/v2\/console\/session\/([^/]+)/);
    if (match?.[1]) {
      const id = decodeURIComponent(match[1]).trim();
      if (/^(session|demo)-[a-z0-9]+$/i.test(id)) {
        observedSessionIds.add(id);
        sessionId = id;
      }
    }
  });

  page.on("response", async (response) => {
    const url = response.url();
    if (!url.includes("/api/v2/session/create") || !response.ok()) return;
    try {
      const payload = await response.json();
      if (payload?.session_id) {
        const id = String(payload.session_id).trim();
        if (/^(session|demo)-[a-z0-9]+$/i.test(id)) {
          createdSessionId = id;
          observedSessionIds.add(id);
          sessionId = id;
        }
      }
    } catch {
      // Ignore response parsing failures from non-JSON error payloads.
    }
  });

  try {
    await patchProviderCatalog(page);
    await page.goto(APP_URL, { waitUntil: "domcontentloaded" });

    await page.getByText("Configure your simulation environment", { exact: false }).waitFor({ timeout: ONBOARDING_TIMEOUT });

    const providerSelect = page.locator('label:has-text("Provider") + select').first();
    const modelSelect = page.locator('label:has-text("Model") + select').first();

    await providerSelect.selectOption("gemini");

    const modelOptions = await modelSelect.locator("option").allTextContents();
    const preferredModel = modelOptions.find((option) => option.includes("gemini-2.5-flash-lite")) || modelOptions[0];
    if (preferredModel) {
      await modelSelect.selectOption({ label: preferredModel });
    }

    const policyTemplateButton = page.getByRole("button", { name: /Public Policy Testing/i });
    if (await policyTemplateButton.count()) {
      await policyTemplateButton.first().click();
    }

    await clickWhenEnabled(page, /Launch Simulation Environment/i, ONBOARDING_TIMEOUT);

    let onboardingClosed = await page
      .getByText("Configure your simulation environment", { exact: false })
      .waitFor({ state: "hidden", timeout: 15_000 })
      .then(() => true)
      .catch(() => false);

    if (!onboardingClosed) {
      const launchError = await page
        .locator("p.text-xs.text-destructive")
        .first()
        .textContent()
        .then((value) => compactWhitespace(value || ""))
        .catch(() => "");

      if (/api key is required|select a provider and model|provider catalog/i.test(launchError)) {
        await providerSelect.selectOption("ollama").catch(() => undefined);

        const fallbackModelValue = await modelSelect.locator("option").first().getAttribute("value");
        if (fallbackModelValue) {
          await modelSelect.selectOption(fallbackModelValue);
        }

        await clickWhenEnabled(page, /Launch Simulation Environment/i, ONBOARDING_TIMEOUT);
        onboardingClosed = await page
          .getByText("Configure your simulation environment", { exact: false })
          .waitFor({ state: "hidden", timeout: ONBOARDING_TIMEOUT })
          .then(() => true)
          .catch(() => false);
      }

      if (!onboardingClosed) {
        throw new Error(`Onboarding did not close after launch attempt. Error=${launchError || "unknown"}`);
      }
    }

    await page.getByText("NEW SIMULATION RUN", { exact: false }).waitFor({ timeout: 60_000 });

    await clickWhenEnabled(page, /^URL$/i, 60_000);
    await page.getByPlaceholder("https://example.com/policy-doc").fill(BUDGET_URL);
    await clickWhenEnabled(page, /^Scrape$/i, 60_000);

    await waitForVisibleButton(page, /Start Extraction/i, 120_000);
    await clickWhenEnabled(page, /Start Extraction/i, 120_000);

    await clickWhenEnabled(page, /^Proceed\b/i, EXTRACTION_TIMEOUT);

    await page.getByText("Agent Configuration", { exact: false }).waitFor({ timeout: 120_000 });
    await clickWhenEnabled(page, /Sample Population/i, 120_000);
    await clickWhenEnabled(page, /^Proceed\b/i, POPULATION_TIMEOUT);

    await page.getByText("Live Social Simulation", { exact: false }).waitFor({ timeout: 120_000 });
    await clickWhenEnabled(page, /Start Simulation/i, 120_000);

    await waitForEnabledButton(page, /Generate Report/i, SIMULATION_TIMEOUT);

    const uiPosts = await page.evaluate(() => {
      const cards = Array.from(document.querySelectorAll("h4.text-sm.font-semibold.text-foreground.mb-2.leading-tight"));
      return cards.slice(0, 80).map((titleNode) => {
        const title = (titleNode.textContent || "").trim();
        const card = titleNode.closest("div.group") || titleNode.closest("div");
        const contentNode = card?.querySelector("p.text-xs.text-muted-foreground.leading-relaxed");
        const content = (contentNode?.textContent || "").trim();
        return { title, content };
      }).filter((item) => item.title || item.content);
    });

    await clickWhenEnabled(page, /Generate Report/i, 30_000);

    await page.getByText("Analysis Report", { exact: false }).waitFor({ timeout: 120_000 });
    await page.waitForFunction(() => !document.body.innerText.includes("Generating report..."), { timeout: REPORT_TIMEOUT });

    const groupDissenters = await runGroupChatProbe(
      page,
      /Top dissenters/i,
      `E2E dissenters check ${Date.now()}: what is your main concern?`,
    );
    const groupSupporters = await runGroupChatProbe(
      page,
      /Top supporters/i,
      `E2E supporters check ${Date.now()}: what should be prioritized next?`,
    );
    const oneToOne = await runOneToOneChatProbe(
      page,
      `E2E 1:1 check ${Date.now()}: summarize your position in one paragraph.`,
    );

    await clickWhenEnabled(page, /^Proceed\b/i, 120_000);
    await page.getByText("Simulation Analytics", { exact: false }).waitFor({ timeout: 120_000 });

    const firstAnalyticsWarningVisible = await page.getByText("Live analytics returned incomplete data.", { exact: false }).first().isVisible().catch(() => false);
    const firstAnalyticsEmptyPolar = await page.getByText("No polarization data yet.", { exact: false }).first().isVisible().catch(() => false);
    const firstAnalyticsEmptyFlow = await page.getByText("No opinion flow data yet.", { exact: false }).first().isVisible().catch(() => false);

    await navigateSidebar(page, /\bReport\b/i);
    await page.getByText("Analysis Report", { exact: false }).waitFor({ timeout: 120_000 });

    const reportHasExecutiveSummary = await page.getByText("Executive Summary", { exact: false }).first().isVisible().catch(() => false);
    const reportFailedFetchVisible = await page.getByText("Failed to fetch", { exact: false }).first().isVisible().catch(() => false);

    await navigateSidebar(page, /\bAnalytics\b/i);
    await page.getByText("Simulation Analytics", { exact: false }).waitFor({ timeout: 120_000 });

    const secondAnalyticsWarningVisible = await page.getByText("Live analytics returned incomplete data.", { exact: false }).first().isVisible().catch(() => false);
    const secondAnalyticsEmptyPolar = await page.getByText("No polarization data yet.", { exact: false }).first().isVisible().catch(() => false);
    const secondAnalyticsEmptyFlow = await page.getByText("No opinion flow data yet.", { exact: false }).first().isVisible().catch(() => false);

    const resolvedSessionId = createdSessionId || sessionId || Array.from(observedSessionIds).at(-1) || null;
    if (!resolvedSessionId) {
      throw new Error("Could not resolve session_id from network activity.");
    }

    const simulationStateRes = await fetch(`${API_BASE}/api/v2/console/session/${resolvedSessionId}/simulation/state`);
    if (!simulationStateRes.ok) {
      throw new Error(`Failed to fetch simulation state: ${simulationStateRes.status} ${simulationStateRes.statusText}`);
    }
    const simulationState = await simulationStateRes.json();

    const reportUrl = `${API_BASE}/api/v2/console/session/${resolvedSessionId}/report`;
    const reportRes = await fetch(reportUrl);
    if (!reportRes.ok) {
      const responseBody = await reportRes.text();
      throw new Error(
        `Failed to fetch report payload for ${resolvedSessionId} (${reportUrl}): ` +
          `${reportRes.status} ${reportRes.statusText} body=${responseBody.slice(0, 240)}`,
      );
    }
    const report = await reportRes.json();

    const eventText = (Array.isArray(simulationState?.recent_events) ? simulationState.recent_events : [])
      .map((event) => compactWhitespace(event?.content || event?.title || ""))
      .filter(Boolean);

    const postText = uiPosts
      .map((post) => compactWhitespace(`${post.title} ${post.content}`))
      .filter(Boolean)
      .concat(eventText);

    const reportSections = Array.isArray(report?.sections) ? report.sections : [];
    const reportAnswers = reportSections
      .map((section) => compactWhitespace(section?.answer || ""))
      .filter(Boolean);
    const executiveSummary = compactWhitespace(report?.executive_summary || "");

    const duplicatePosts = findDuplicateEntries(postText);
    const refusalMatches = collectRefusalMatches(postText.concat(reportAnswers, executiveSummary));
    const firstPersonMatches = collectFirstPersonMatches(reportAnswers);

    const artifact = {
      started_at: startedAt,
      finished_at: new Date().toISOString(),
      app_url: APP_URL,
      api_base: API_BASE,
      session_id: resolvedSessionId,
      budget_url: BUDGET_URL,
      observed_session_ids: Array.from(observedSessionIds),
      ui_posts: uiPosts,
      simulation_state: simulationState,
      report,
      checks: {
        duplicate_posts: {
          duplicate_count: duplicatePosts.length,
          examples: duplicatePosts,
        },
        refusal_language: {
          match_count: refusalMatches.length,
          examples: refusalMatches.slice(0, 20),
        },
        report_first_person_voice: {
          match_count: firstPersonMatches.length,
          examples: firstPersonMatches.slice(0, 20),
        },
        live_chat: {
          group_dissenters: groupDissenters,
          group_supporters: groupSupporters,
          one_to_one: oneToOne,
        },
        report_analytics_navigation: {
          report_has_executive_summary_after_return: reportHasExecutiveSummary,
          report_failed_to_fetch_visible_after_return: reportFailedFetchVisible,
          analytics_warning_visible_before_return: firstAnalyticsWarningVisible,
          analytics_warning_visible_after_return: secondAnalyticsWarningVisible,
          analytics_empty_polar_before_return: firstAnalyticsEmptyPolar,
          analytics_empty_flow_before_return: firstAnalyticsEmptyFlow,
          analytics_empty_polar_after_return: secondAnalyticsEmptyPolar,
          analytics_empty_flow_after_return: secondAnalyticsEmptyFlow,
        },
      },
    };

    await fs.mkdir(OUTPUT_DIR, { recursive: true });
    const outPath = path.join(OUTPUT_DIR, "live-e2e-artifact.json");
    await fs.writeFile(outPath, JSON.stringify(artifact, null, 2), "utf8");

    process.stdout.write(`${JSON.stringify({
      status: "ok",
      output_file: outPath,
      session_id: resolvedSessionId,
      duplicate_post_examples: duplicatePosts.slice(0, 5),
      refusal_match_count: refusalMatches.length,
      report_first_person_match_count: firstPersonMatches.length,
      group_chat_dissenters_ok: groupDissenters.ok,
      group_chat_supporters_ok: groupSupporters.ok,
      one_to_one_chat_ok: oneToOne.ok,
      report_persisted_after_return: reportHasExecutiveSummary && !reportFailedFetchVisible,
      analytics_empty_after_return: secondAnalyticsEmptyPolar && secondAnalyticsEmptyFlow,
      ui_post_count: uiPosts.length,
      report_section_count: reportSections.length,
    })}\n`);
  } finally {
    await context.close();
    await browser.close();
  }
}

run().catch((error) => {
  process.stderr.write(`playwright-live-e2e failed: ${error instanceof Error ? error.stack || error.message : String(error)}\n`);
  process.exitCode = 1;
});
