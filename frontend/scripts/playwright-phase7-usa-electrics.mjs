import fs from "node:fs/promises";
import path from "node:path";
import { chromium } from "@playwright/test";

const APP_URL = process.env.APP_URL || "http://127.0.0.1:5174";
const API_BASE = process.env.API_BASE || "http://127.0.0.1:8010";
const GEMINI_API_KEY =
  process.env.GEMINI_API ||
  process.env.GOOGLE_API_KEY ||
  process.env.GEMINI_API_KEY ||
  "";
const OUTPUT_DIR =
  process.env.OUTPUT_DIR ||
  "/Users/pebblepaw/Documents/CODING_PROJECTS/Nemotron_Consult/output/phase7-local-usa-electrics";

const URLS = [
  "https://bridgemi.com/michigan-government/michigan-elections-faq-where-trump-harris-stand-health-care-drug-prices/?_gl=1*t6446x*_gcl_au*NTk0MjM4MjQwLjE3NzY0NDUwODc.*_ga*OTA3NDI0ODc2LjE3NzY0NDUwODc.*_ga_SDMLQHFB10*czE3NzY0NDUwODgkbzEkZzEkdDE3NzY0NDUxMzIkajE2JGwwJGgw*_ga_1E2G9MSHX5*czE3NzY0NDUwODYkbzEkZzEkdDE3NzY0NDUxMzIkajE0JGwwJGgw*_ga_KX5CRZVP9F*czE3NzY0NDUwODckbzEkZzEkdDE3NzY0NDUxMzIkajE1JGwwJGgw",
  "https://bridgemi.com/michigan-government/michigan-elections-faq-where-trump-harris-stand-immigration-border-security/?_gl=1*t6446x*_gcl_au*NTk0MjM4MjQwLjE3NzY0NDUwODc.*_ga*OTA3NDI0ODc2LjE3NzY0NDUwODc.*_ga_SDMLQHFB10*czE3NzY0NDUwODgkbzEkZzEkdDE3NzY0NDUxMzIkajE2JGwwJGgw*_ga_1E2G9MSHX5*czE3NzY0NDUwODYkbzEkZzEkdDE3NzY0NDUxMzIkajE0JGwwJGgw*_ga_KX5CRZVP9F*czE3NzY0NDUwODckbzEkZzEkdDE3NzY0NDUxMzIkajE1JGwwJGgw",
  "https://bridgemi.com/michigan-government/michigan-elections-faq-where-trump-harris-stand-economy-and-taxes/?_gl=1*t6446x*_gcl_au*NTk0MjM4MjQwLjE3NzY0NDUwODc.*_ga*OTA3NDI0ODc2LjE3NzY0NDUwODc.*_ga_SDMLQHFB10*czE3NzY0NDUwODgkbzEkZzEkdDE3NzY0NDUxMzIkajE2JGwwJGgw*_ga_1E2G9MSHX5*czE3NzY0NDUwODYkbzEkZzEkdDE3NzY0NDUxMzIkajE0JGwwJGgw*_ga_KX5CRZVP9F*czE3NzY0NDUwODckbzEkZzEkdDE3NzY0NDUxMzIkajE1JGwwJGgw",
];

const QUESTIONS = [
  "On immigration policies, do you support Trump or Kamala? Yes for Trump, No for Kamala",
  "On economic policies, do you support Trump or Kamala? Yes for Trump, No for Kamala",
  "On healthcare policies, do you support Trump or Kamala? Yes for Trump, No for Kamala",
  "Overall would you vote for Trump or Kamala in the 2024 elections? Yes for Trump, No for Kamala",
];

const SAMPLING_INSTRUCTIONS = "Only citizens from Michigan state.";
const ONBOARDING_TIMEOUT = 120_000;
const EXTRACTION_TIMEOUT = 900_000;
const POPULATION_TIMEOUT = 600_000;
const SIMULATION_TIMEOUT = 1_200_000;
const REPORT_TIMEOUT = 600_000;

function compactWhitespace(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function normalizeText(value) {
  return compactWhitespace(value).toLowerCase();
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
  throw new Error(`Button ${name} did not become enabled within ${timeoutMs}ms`);
}

async function clickWhenEnabled(page, name, timeoutMs) {
  const button = await waitForEnabledButton(page, name, timeoutMs);
  await button.click();
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
  await markButton.waitFor({ state: "visible", timeout: 60_000 });
  await markButton.click({ force: true });
}

function extractMichiganSignals(populationArtifact) {
  const coverageValues = [
    ...(Array.isArray(populationArtifact?.coverage?.geographies) ? populationArtifact.coverage.geographies : []),
    ...(Array.isArray(populationArtifact?.coverage?.planning_areas) ? populationArtifact.coverage.planning_areas : []),
  ]
    .map((value) => normalizeText(value))
    .filter(Boolean);

  const sampleStateValues = (Array.isArray(populationArtifact?.sampled_personas) ? populationArtifact.sampled_personas : [])
    .map((row) => normalizeText(row?.persona?.state))
    .filter(Boolean);

  const notes = (Array.isArray(populationArtifact?.parsed_sampling_instructions?.notes_for_ui)
    ? populationArtifact.parsed_sampling_instructions.notes_for_ui
    : [])
    .map((value) => normalizeText(value));

  return {
    coverage_values: [...new Set(coverageValues)],
    sample_state_values: [...new Set(sampleStateValues)],
    notes,
    all_sample_states_are_michigan:
      sampleStateValues.length > 0 && sampleStateValues.every((value) => value === "michigan" || value === "mi"),
    notes_reference_michigan: notes.some((value) => value.includes("michigan")),
  };
}

async function saveExportedDocx(sessionId) {
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/report/export`);
  if (!response.ok) {
    throw new Error(`DOCX export failed: ${response.status} ${response.statusText}`);
  }
  const buffer = Buffer.from(await response.arrayBuffer());
  const filePath = path.join(OUTPUT_DIR, `miroworld-${sessionId}-report.docx`);
  await fs.writeFile(filePath, buffer);
  return filePath;
}

async function scrapeSourcesToFiles(sessionId) {
  const filePaths = [];
  for (const [index, url] of URLS.entries()) {
    const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/scrape`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    if (!response.ok) {
      const detail = await response.text();
      throw new Error(`Scrape ${index + 1} failed: ${response.status} ${response.statusText} body=${detail.slice(0, 400)}`);
    }
    const payload = await response.json();
    const filePath = path.join(OUTPUT_DIR, `source-${String(index + 1).padStart(2, "0")}.txt`);
    const contents = `${payload.title || url}\n\n${payload.text || ""}`.trim();
    await fs.writeFile(filePath, contents, "utf8");
    filePaths.push(filePath);
    process.stderr.write(`[phase7-e2e] Scraped source ${index + 1}/3.\n`);
  }
  return filePaths;
}

async function ensureCountryDatasetReady(countryId) {
  const statusUrl = `${API_BASE}/api/v2/countries/${countryId}/download-status`;
  const downloadUrl = `${API_BASE}/api/v2/countries/${countryId}/download`;

  let statusResponse = await fetch(statusUrl);
  if (!statusResponse.ok) {
    throw new Error(`Country status check failed for ${countryId}: ${statusResponse.status} ${statusResponse.statusText}`);
  }
  let status = await statusResponse.json();
  if (status?.dataset_ready) {
    return status;
  }

  const downloadResponse = await fetch(downloadUrl, { method: "POST" });
  if (!downloadResponse.ok) {
    throw new Error(`Country download trigger failed for ${countryId}: ${downloadResponse.status} ${downloadResponse.statusText}`);
  }

  const deadline = Date.now() + 20 * 60_000;
  while (Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, 3000));
    statusResponse = await fetch(statusUrl);
    if (!statusResponse.ok) {
      throw new Error(`Country status poll failed for ${countryId}: ${statusResponse.status} ${statusResponse.statusText}`);
    }
    status = await statusResponse.json();
    if (status?.dataset_ready) {
      return status;
    }
    if (status?.download_status === "error") {
      throw new Error(`Country dataset download failed for ${countryId}: ${status?.download_error || "unknown error"}`);
    }
  }

  throw new Error(`Timed out waiting for ${countryId} dataset download to complete.`);
}

async function run() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ acceptDownloads: true, viewport: { width: 1600, height: 1100 } });
  const page = await context.newPage();
  const startedAt = new Date().toISOString();
  let sessionId = null;
  let populationArtifact = null;

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
      // Ignore non-JSON responses.
    }
  });

  await fs.mkdir(OUTPUT_DIR, { recursive: true });

  try {
    if (!GEMINI_API_KEY.trim()) {
      throw new Error("Missing GEMINI_API / GOOGLE_API_KEY in environment.");
    }
    process.stderr.write("[phase7-e2e] Opening app.\n");
    process.stderr.write("[phase7-e2e] Ensuring USA dataset is ready.\n");
    await ensureCountryDatasetReady("usa");
    await page.goto(APP_URL, { waitUntil: "domcontentloaded" });
    await page.getByText("Configure your simulation environment", { exact: false }).waitFor({ timeout: ONBOARDING_TIMEOUT });

    const providerSelect = page.locator('label:has-text("Provider") + select').first();
    const modelSelect = page.locator('label:has-text("Model") + select').first();

    await page.getByRole("button", { name: /United States/i }).click();
    await providerSelect.selectOption("gemini");
    await page.getByPlaceholder("sk-...").fill(GEMINI_API_KEY);
    const modelOptions = await modelSelect.locator("option").allTextContents();
    const preferredModel = modelOptions.find((option) => option.includes("gemini-2.5-flash-lite")) || modelOptions[0];
    if (preferredModel) {
      await modelSelect.selectOption({ label: preferredModel });
    }
    await page.getByRole("button", { name: /Public Policy Testing/i }).first().click();
    const launchButton = page.getByRole("button", { name: /Launch Simulation Environment/i }).first();
    const launchState = await launchButton.evaluate((button) => ({
      disabled: button.hasAttribute("disabled"),
      text: button.textContent,
    }));
    process.stderr.write(`[phase7-e2e] Launch button state before click: ${JSON.stringify(launchState)}\n`);
    process.stderr.write(
      `[phase7-e2e] Provider=${await providerSelect.inputValue()} Model=${await modelSelect.inputValue()}\n`,
    );
    await page.screenshot({ path: path.join(OUTPUT_DIR, "onboarding-before-launch.png"), fullPage: true });

    const createSessionResponse = page.waitForResponse(
      (response) => response.url().includes("/api/v2/session/create") && response.request().method() === "POST",
      { timeout: ONBOARDING_TIMEOUT },
    );
    process.stderr.write("[phase7-e2e] Launching live environment.\n");
    await clickWhenEnabled(page, /Launch Simulation Environment/i, ONBOARDING_TIMEOUT);
    const createSessionResult = await createSessionResponse;
    if (!createSessionResult.ok()) {
      throw new Error(`Session creation failed: ${createSessionResult.status()} ${createSessionResult.statusText()}`);
    }

    await page.getByText("New Simulation Run", { exact: false }).waitFor({ timeout: 60_000 });
    process.stderr.write(`[phase7-e2e] Session created: ${sessionId}\n`);
    if (!sessionId) {
      throw new Error("Session ID was not observed after onboarding.");
    }

    const questionAreas = page.locator('textarea[placeholder="Type your analysis question..."]');
    await page.waitForFunction(
      () => document.querySelectorAll('textarea[placeholder="Type your analysis question..."]').length >= 3,
      { timeout: 60_000 },
    );
    for (let index = 0; index < 3; index += 1) {
      await questionAreas.nth(index).fill(QUESTIONS[index]);
    }
    await clickWhenEnabled(page, /Add Question/i, 30_000);
    await page.waitForFunction(
      () => document.querySelectorAll('textarea[placeholder="Type your analysis question..."]').length >= 4,
      { timeout: 30_000 },
    );
    await questionAreas.nth(3).fill(QUESTIONS[3]);

    const uploadedPaths = await scrapeSourcesToFiles(sessionId);
    await page.locator('input[type="file"]').setInputFiles(uploadedPaths);
    await page.getByText("source-01.txt").waitFor({ timeout: 60_000 });

    await page.screenshot({ path: path.join(OUTPUT_DIR, "screen1-configured.png"), fullPage: true });
    process.stderr.write("[phase7-e2e] Starting extraction.\n");
    await clickWhenEnabled(page, /Start Extraction/i, 30_000);
    await clickWhenEnabled(page, /^Proceed\b/i, EXTRACTION_TIMEOUT);
    await page.screenshot({ path: path.join(OUTPUT_DIR, "screen1-extracted.png"), fullPage: true });

    await page.getByText("Agent Configuration", { exact: false }).waitFor({ timeout: 120_000 });
    const agentSlider = page.getByRole("slider").first();
    await setSliderValue(agentSlider, 30);
    await page.getByText(/^30$/).first().waitFor({ timeout: 30_000 });
    await page.locator("#sampling-instructions").fill(SAMPLING_INSTRUCTIONS);
    await page.screenshot({ path: path.join(OUTPUT_DIR, "screen2-configured.png"), fullPage: true });

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
    populationArtifact = await previewResult.json();
    const michiganSignals = extractMichiganSignals(populationArtifact);
    if (Number(populationArtifact?.sample_count) !== 30) {
      throw new Error(`Population preview returned ${populationArtifact?.sample_count} agents instead of 30.`);
    }
    if (!michiganSignals.all_sample_states_are_michigan && !michiganSignals.notes_reference_michigan) {
      throw new Error(`Population preview did not clearly resolve to Michigan-only sampling: ${JSON.stringify(michiganSignals)}`);
    }
    process.stderr.write("[phase7-e2e] Population sampled successfully.\n");
    await clickWhenEnabled(page, /^Proceed\b/i, POPULATION_TIMEOUT);
    await page.screenshot({ path: path.join(OUTPUT_DIR, "screen2-sampled.png"), fullPage: true });

    await page.getByText("Live Social Simulation", { exact: false }).waitFor({ timeout: 120_000 });
    await setSimulationRounds(page, 5);
    await page.getByText(/×\s*5 rounds/i).waitFor({ timeout: 30_000 });
    await clickWhenEnabled(page, /Start Simulation/i, 60_000);
    await waitForEnabledButton(page, /Generate Report/i, SIMULATION_TIMEOUT);
    process.stderr.write("[phase7-e2e] Simulation completed.\n");
    await page.screenshot({ path: path.join(OUTPUT_DIR, "screen3-simulated.png"), fullPage: true });

    await clickWhenEnabled(page, /Generate Report/i, 30_000);
    await page.getByText("Analysis Report", { exact: false }).waitFor({ timeout: 120_000 });
    await page.waitForFunction(() => !document.body.innerText.includes("Generating report..."), { timeout: REPORT_TIMEOUT });
    process.stderr.write("[phase7-e2e] Report generated.\n");
    await page.screenshot({ path: path.join(OUTPUT_DIR, "screen4-report.png"), fullPage: true });

    const reportResponse = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/report`);
    if (!reportResponse.ok) {
      throw new Error(`Report fetch failed: ${reportResponse.status} ${reportResponse.statusText}`);
    }
    const reportPayload = await reportResponse.json();
    const docxPath = await saveExportedDocx(sessionId);

    await clickWhenEnabled(page, /^Proceed\b/i, 60_000);
    await page.getByText("Simulation Analytics", { exact: false }).waitFor({ timeout: 120_000 });
    process.stderr.write("[phase7-e2e] Analytics loaded.\n");
    await page.screenshot({ path: path.join(OUTPUT_DIR, "screen5-analytics.png"), fullPage: true });

    const artifact = {
      started_at: startedAt,
      finished_at: new Date().toISOString(),
      app_url: APP_URL,
      api_base: API_BASE,
      session_id: sessionId,
      urls: URLS,
      questions: QUESTIONS,
      sampling_instructions: SAMPLING_INSTRUCTIONS,
      population_summary: {
        sample_count: populationArtifact?.sample_count,
        coverage: populationArtifact?.coverage,
        parsed_sampling_instructions: populationArtifact?.parsed_sampling_instructions,
        michigan_signals: extractMichiganSignals(populationArtifact),
      },
      report_summary: {
        executive_summary: reportPayload?.executive_summary || "",
        section_titles: Array.isArray(reportPayload?.sections) ? reportPayload.sections.map((section) => section.title) : [],
      },
      exported_docx: docxPath,
      screenshots: [
        "screen1-configured.png",
        "screen1-extracted.png",
        "screen2-configured.png",
        "screen2-sampled.png",
        "screen3-simulated.png",
        "screen4-report.png",
        "screen5-analytics.png",
      ].map((name) => path.join(OUTPUT_DIR, name)),
    };

    const artifactPath = path.join(OUTPUT_DIR, "phase7-usa-electrics-artifact.json");
    await fs.writeFile(artifactPath, JSON.stringify(artifact, null, 2), "utf8");
    process.stdout.write(`${JSON.stringify({ status: "ok", artifact: artifactPath, docx: docxPath, session_id: sessionId })}\n`);
  } finally {
    await context.close();
    await browser.close();
  }
}

run().catch((error) => {
  process.stderr.write("[phase7-e2e] Failure.\n");
  process.stderr.write(`playwright-phase7-usa-electrics failed: ${error instanceof Error ? error.stack || error.message : String(error)}\n`);
  process.exitCode = 1;
});
