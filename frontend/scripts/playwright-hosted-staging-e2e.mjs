import fs from "node:fs/promises";
import path from "node:path";
import { chromium } from "@playwright/test";

const APP_URL = process.env.APP_URL || "https://dp9zh8guag18x.cloudfront.net";
const OUTPUT_DIR =
  process.env.OUTPUT_DIR ||
  "/Users/pebblepaw/Documents/CODING_PROJECTS/Nemotron_Consult/output/hosted-staging-e2e-final";
const SAMPLE_FILE =
  process.env.SAMPLE_FILE ||
  "/Users/pebblepaw/Documents/CODING_PROJECTS/Nemotron_Consult/.worktrees/hosted-supabase-zep/backend/Sample_Inputs/singapore_budget_ai_strategic_advantage.md";
const HOSTED_EMAIL_PREFIX = process.env.HOSTED_EMAIL_PREFIX || "codex-hosted";
const HOSTED_EMAIL_DOMAIN = process.env.HOSTED_EMAIL_DOMAIN || "example.com";
const HOSTED_PASSWORD = process.env.HOSTED_PASSWORD || "HostedPassw0rd!";
const COUNTRY_LABEL = process.env.COUNTRY_LABEL || "Singapore";
const USE_CASE_LABEL = process.env.USE_CASE_LABEL || "Public Policy Testing";
const SAMPLE_COUNT = Number(process.env.SAMPLE_COUNT || 20);
const SIMULATION_ROUNDS = Number(process.env.SIMULATION_ROUNDS || 3);

const AUTH_TIMEOUT = 120_000;
const ONBOARDING_TIMEOUT = 240_000;
const EXTRACTION_TIMEOUT = 900_000;
const POPULATION_TIMEOUT = 600_000;
const SIMULATION_TIMEOUT = 1_200_000;
const REPORT_TIMEOUT = 600_000;

function log(message) {
  process.stderr.write(`[hosted-e2e] ${message}\n`);
}

function compactWhitespace(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

async function clickWhenEnabled(page, name, timeoutMs) {
  const locator = page.getByRole("button", { name }).first();
  await locator.waitFor({ state: "visible", timeout: timeoutMs });
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await locator.isEnabled()) {
      await locator.click();
      return;
    }
    await page.waitForTimeout(300);
  }
  throw new Error(`Button ${String(name)} did not become enabled within ${timeoutMs}ms`);
}

async function waitForEnabledButton(page, name, timeoutMs) {
  const locator = page.getByRole("button", { name }).first();
  await locator.waitFor({ state: "visible", timeout: timeoutMs });
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await locator.isEnabled()) {
      return locator;
    }
    await page.waitForTimeout(300);
  }
  throw new Error(`Button ${String(name)} did not become enabled within ${timeoutMs}ms`);
}

async function setSliderValue(locator, value, step = 10) {
  await locator.waitFor({ state: "visible", timeout: 60_000 });
  await locator.focus();
  const currentValue = Number(await locator.getAttribute("aria-valuenow"));
  const presses = Math.max(0, Math.round(Math.abs(value - currentValue) / step));
  const key = value >= currentValue ? "ArrowRight" : "ArrowLeft";
  for (let index = 0; index < presses; index += 1) {
    await locator.press(key);
  }
}

async function setSimulationRounds(page, rounds) {
  const roundsCard = page.locator("h3", { hasText: "Simulation Rounds" }).locator("..").locator("..");
  const markButton = roundsCard.getByRole("button", { name: String(rounds), exact: true }).first();
  const visible = await markButton.isVisible().catch(() => false);
  if (!visible) {
    log(`Simulation rounds control for ${rounds} not visible; using the current default.`);
    return;
  }
  await markButton.click({ force: true });
}

async function maybeDownloadDataset(page) {
  const downloadButton = page.getByRole("button", { name: /Download .* dataset/i }).first();
  if (!(await downloadButton.isVisible().catch(() => false))) {
    return;
  }
  log("Dataset download required; starting hosted dataset download.");
  await clickWhenEnabled(page, /Download .* dataset/i, ONBOARDING_TIMEOUT);
  await page.waitForFunction(
    () => {
      const buttons = [...document.querySelectorAll("button")];
      return buttons.some((button) => /Launch Simulation Environment/i.test(button.textContent || "") && !button.hasAttribute("disabled"));
    },
    { timeout: 20 * 60_000 },
  );
}

async function saveDownload(download, outputDir) {
  const suggestedName = download.suggestedFilename() || `hosted-report-${Date.now()}.docx`;
  const filePath = path.join(outputDir, suggestedName);
  await download.saveAs(filePath);
  return filePath;
}

async function fetchJson(page, url, options = {}) {
  const payload = await page.evaluate(
    async ({ inputUrl, inputOptions }) => {
      const response = await fetch(inputUrl, inputOptions);
      const text = await response.text();
      return {
        ok: response.ok,
        status: response.status,
        statusText: response.statusText,
        text,
      };
    },
    { inputUrl: url, inputOptions: options },
  );

  if (!payload.ok) {
    throw new Error(`Fetch failed for ${url}: ${payload.status} ${payload.statusText} body=${payload.text.slice(0, 400)}`);
  }
  return payload.text ? JSON.parse(payload.text) : null;
}

async function run() {
  await fs.mkdir(OUTPUT_DIR, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    acceptDownloads: true,
    viewport: { width: 1600, height: 1100 },
  });
  const page = await context.newPage();
  let sessionId = null;

  page.on("response", async (response) => {
    if (!response.url().includes("/api/v2/session/create")) {
      return;
    }
    try {
      const payload = await response.json();
      if (payload?.session_id) {
        sessionId = String(payload.session_id);
      }
    } catch {
      // ignore
    }
  });

  const startedAt = new Date().toISOString();
  const email = `${HOSTED_EMAIL_PREFIX}+${Date.now()}@${HOSTED_EMAIL_DOMAIN}`;

  try {
    await page.goto(APP_URL, { waitUntil: "domcontentloaded" });
    await page.getByText("Supabase + Zep hosted preview", { exact: false }).waitFor({ timeout: AUTH_TIMEOUT });
    await page.screenshot({ path: path.join(OUTPUT_DIR, "00-entry.png"), fullPage: true });

    await page.getByRole("link", { name: /Review the hosted pricing preview/i }).click();
    await page.getByText("Hosted pricing preview", { exact: false }).waitFor({ timeout: AUTH_TIMEOUT });
    await page.screenshot({ path: path.join(OUTPUT_DIR, "01-pricing.png"), fullPage: true });
    await page.getByRole("link", { name: /Return to sign up/i }).click();
    await page.getByText("Create your hosted account", { exact: false }).waitFor({ timeout: AUTH_TIMEOUT });

    log(`Creating hosted account ${email}.`);
    await page.locator("#hosted-auth-email").fill(email);
    await page.locator("#hosted-auth-password").fill(HOSTED_PASSWORD);
    await clickWhenEnabled(page, /^Create account$/i, AUTH_TIMEOUT);

    await page.getByText("Configure your simulation environment", { exact: false }).waitFor({ timeout: ONBOARDING_TIMEOUT });
    await page.screenshot({ path: path.join(OUTPUT_DIR, "02-onboarding.png"), fullPage: true });

    await page.getByRole("button", { name: new RegExp(COUNTRY_LABEL, "i") }).click();
    await page.getByRole("button", { name: new RegExp(USE_CASE_LABEL, "i") }).first().click();
    await page.screenshot({ path: path.join(OUTPUT_DIR, "02b-onboarding-selected.png"), fullPage: true });
    await maybeDownloadDataset(page);

    const createSessionResponse = page.waitForResponse(
      (response) => response.url().includes("/api/v2/session/create") && response.request().method() === "POST",
      { timeout: ONBOARDING_TIMEOUT },
    );
    await clickWhenEnabled(page, /Launch Simulation Environment/i, ONBOARDING_TIMEOUT);
    const createSessionResult = await createSessionResponse;
    if (!createSessionResult.ok()) {
      throw new Error(`Session creation failed: ${createSessionResult.status()} ${createSessionResult.statusText()}`);
    }

    await page.getByText("New Simulation Run", { exact: false }).waitFor({ timeout: 120_000 });
    if (!sessionId) {
      throw new Error("Session ID was not observed after launching the hosted environment.");
    }
    log(`Hosted session created: ${sessionId}`);

    await page.locator('input[type="file"]').setInputFiles(SAMPLE_FILE);
    await page.getByText(path.basename(SAMPLE_FILE), { exact: false }).waitFor({ timeout: 60_000 });
    await page.screenshot({ path: path.join(OUTPUT_DIR, "03-upload.png"), fullPage: true });

    await clickWhenEnabled(page, /Start Extraction/i, 30_000);
    await clickWhenEnabled(page, /^Proceed\b/i, EXTRACTION_TIMEOUT);
    await page.screenshot({ path: path.join(OUTPUT_DIR, "04-graph-ready.png"), fullPage: true });

    await page.getByText("Agent Configuration", { exact: false }).waitFor({ timeout: 120_000 });
    const agentSlider = page.getByRole("slider").first();
    await setSliderValue(agentSlider, SAMPLE_COUNT);
    await page.screenshot({ path: path.join(OUTPUT_DIR, "05-agent-config.png"), fullPage: true });

    const previewResponse = page.waitForResponse(
      (response) =>
        response.url().includes(`/api/v2/console/session/${sessionId}/sampling/preview`) &&
        response.request().method() === "POST",
      { timeout: POPULATION_TIMEOUT },
    );
    await clickWhenEnabled(page, /Sample Population/i, 60_000);
    const previewResult = await previewResponse;
    if (!previewResult.ok()) {
      throw new Error(`Population preview failed: ${previewResult.status()} ${previewResult.statusText()}`);
    }
    const populationArtifact = await previewResult.json();
    if (Number(populationArtifact?.sample_count) !== SAMPLE_COUNT) {
      throw new Error(`Population preview returned ${populationArtifact?.sample_count} agents instead of ${SAMPLE_COUNT}.`);
    }
    await clickWhenEnabled(page, /^Proceed\b/i, POPULATION_TIMEOUT);
    await page.screenshot({ path: path.join(OUTPUT_DIR, "06-population-ready.png"), fullPage: true });

    await page.getByText("Live Social Simulation", { exact: false }).waitFor({ timeout: 120_000 });
    await setSimulationRounds(page, SIMULATION_ROUNDS);
    await clickWhenEnabled(page, /Start Simulation/i, 60_000);
    await waitForEnabledButton(page, /Generate Report/i, SIMULATION_TIMEOUT);
    await page.screenshot({ path: path.join(OUTPUT_DIR, "07-simulation-complete.png"), fullPage: true });

    await clickWhenEnabled(page, /Generate Report/i, 30_000);
    await page.getByText("Analysis Report", { exact: false }).waitFor({ timeout: 120_000 });
    await page.waitForFunction(() => !document.body.innerText.includes("Generating report..."), { timeout: REPORT_TIMEOUT });
    await page.screenshot({ path: path.join(OUTPUT_DIR, "08-report.png"), fullPage: true });

    const reportHeadings = (await page.locator("h2, h3").allInnerTexts())
      .map((value) => compactWhitespace(value))
      .filter(Boolean);
    const renderedReportText = compactWhitespace(
      await page.evaluate(() => document.body.innerText || ""),
    );
    const groupCandidates = await fetchJson(
      page,
      `/api/v2/console/session/${sessionId}/chat/group/agents?segment=supporter&top_n=1`,
    );
    const firstAgentId = groupCandidates?.agents?.[0]?.agent_id || groupCandidates?.agents?.[0]?.id || null;
    let agentChatPayload = null;
    if (firstAgentId) {
      agentChatPayload = await fetchJson(page, `/api/v2/console/session/${sessionId}/chat/agent/${firstAgentId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: "What shaped your final position in this simulation?" }),
      });
    }

    const downloadPromise = page.waitForEvent("download", { timeout: 120_000 });
    await clickWhenEnabled(page, /^Export$/i, 30_000);
    const download = await downloadPromise;
    const docxPath = await saveDownload(download, OUTPUT_DIR);

    await clickWhenEnabled(page, /^Proceed\b/i, 60_000);
    await page.getByText("Simulation Analytics", { exact: false }).waitFor({ timeout: 120_000 });
    await page.screenshot({ path: path.join(OUTPUT_DIR, "09-analytics.png"), fullPage: true });

    const artifact = {
      started_at: startedAt,
      finished_at: new Date().toISOString(),
      app_url: APP_URL,
      session_id: sessionId,
      sample_file: SAMPLE_FILE,
      email,
      sample_count: SAMPLE_COUNT,
      simulation_rounds: SIMULATION_ROUNDS,
      exported_docx: docxPath,
      report_summary: {
        rendered_excerpt: renderedReportText.slice(0, 2000),
        section_titles: reportHeadings,
      },
      agent_chat_probe: agentChatPayload,
      screenshots: [
        "00-entry.png",
        "01-pricing.png",
        "02-onboarding.png",
        "02b-onboarding-selected.png",
        "03-upload.png",
        "04-graph-ready.png",
        "05-agent-config.png",
        "06-population-ready.png",
        "07-simulation-complete.png",
        "08-report.png",
        "09-analytics.png",
      ].map((name) => path.join(OUTPUT_DIR, name)),
    };

    const artifactPath = path.join(OUTPUT_DIR, "hosted-staging-e2e-artifact.json");
    await fs.writeFile(artifactPath, JSON.stringify(artifact, null, 2), "utf8");
    process.stdout.write(`${JSON.stringify({ status: "ok", artifact: artifactPath, session_id: sessionId, docx: docxPath })}\n`);
  } finally {
    await context.close();
    await browser.close();
  }
}

run().catch((error) => {
  process.stderr.write("[hosted-e2e] Failure.\n");
  process.stderr.write(`${error instanceof Error ? error.stack || error.message : String(error)}\n`);
  process.exitCode = 1;
});
