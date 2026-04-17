import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { OnboardingModal } from "@/components/OnboardingModal";
import { AppProvider, useApp } from "@/contexts/AppContext";

const countriesResponse = [
  {
    name: "Singapore",
    code: "sg",
    flag_emoji: "🇸🇬",
    dataset_path: "configs/countries/singapore.yaml",
    available: true,
    dataset_ready: true,
    download_required: false,
    download_status: "ready",
    download_error: null,
    missing_dependency: null,
  },
  {
    name: "USA",
    code: "usa",
    flag_emoji: "🇺🇸",
    dataset_path: "configs/countries/usa.yaml",
    available: true,
    dataset_ready: true,
    download_required: false,
    download_status: "ready",
    download_error: null,
    missing_dependency: null,
  },
];

const countriesDownloadRequiredResponse = [
  {
    name: "Singapore",
    code: "sg",
    flag_emoji: "🇸🇬",
    dataset_path: "configs/countries/singapore.yaml",
    available: true,
    dataset_ready: true,
    download_required: false,
    download_status: "ready",
    download_error: null,
    missing_dependency: null,
  },
  {
    name: "United States",
    code: "usa",
    flag_emoji: "🇺🇸",
    dataset_path: "configs/countries/usa.yaml",
    available: true,
    dataset_ready: false,
    download_required: true,
    download_status: "missing",
    download_error: null,
    missing_dependency: null,
  },
];

function Harness() {
  const [open, setOpen] = useState(true);
  const { sessionId } = useApp();

  return (
    <>
      <span data-testid="session-id">{sessionId ?? "none"}</span>
      <OnboardingModal isOpen={open} onClose={() => setOpen(false)} />
    </>
  );
}

function makeResponse(body: unknown) {
  return {
    ok: true,
    json: async () => body,
  } as Response;
}

describe("Hosted OnboardingModal", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    window.sessionStorage.clear();
    global.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);

      if (url.endsWith("/api/v2/countries")) {
        return makeResponse(countriesResponse);
      }

      if (url.endsWith("/api/v2/session/create")) {
        return makeResponse({
          session_id: "hosted-session-1",
          received: JSON.parse(String(init?.body ?? "{}")),
        });
      }

      throw new Error(`Unexpected fetch: ${url}`);
    }) as typeof fetch;
  });

  afterEach(() => {
    window.sessionStorage.clear();
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("hides BYOK engine controls and launches a hosted Gemini session", async () => {
    render(
      <AppProvider>
        <Harness />
      </AppProvider>,
    );

    expect(screen.getByText("Configure your simulation environment")).toBeInTheDocument();

    await waitFor(() =>
      expect(
        vi.mocked(global.fetch).mock.calls.some(([url]) => String(url).includes("/api/v2/countries")),
      ).toBe(true),
    );
    expect(screen.queryByText(/^provider$/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/^model$/i)).not.toBeInTheDocument();
    expect(screen.queryByPlaceholderText("sk-...")).not.toBeInTheDocument();
    expect(screen.getAllByText(/shared gemini runtime/i).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: /usa/i }));
    fireEvent.click(screen.getByRole("button", { name: /product & market research/i }));
    fireEvent.click(screen.getByRole("button", { name: /launch simulation environment/i }));

    await waitFor(() => expect(screen.getByTestId("session-id")).toHaveTextContent("hosted-session-1"));

    const createCall = vi
      .mocked(global.fetch)
      .mock.calls.find(([url]) => String(url).endsWith("/api/v2/session/create"));

    expect(createCall).toBeDefined();
    expect(JSON.parse(String(createCall?.[1]?.body))).toMatchObject({
      country: "usa",
      provider: "google",
      model: "gemini-2.5-flash-lite",
      use_case: "product-market-research",
    });
  });

  it("downloads a required hosted dataset before launch", async () => {
    let downloadStatusCalls = 0;
    let createRequestBody: Record<string, unknown> | null = null;
    const missingCatalog = [
      {
        ...countriesDownloadRequiredResponse[0],
        dataset_ready: false,
        download_required: true,
        download_status: "missing",
      },
      countriesDownloadRequiredResponse[1],
    ];

    global.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);

      if (url.endsWith("/api/v2/countries")) {
        return makeResponse(missingCatalog);
      }

      if (url.endsWith("/api/v2/countries/usa/download")) {
        return makeResponse({ status: "started" });
      }

      if (url.endsWith("/api/v2/countries/usa/download-status")) {
        downloadStatusCalls += 1;
        return makeResponse({
          ...missingCatalog[1],
          dataset_ready: true,
          download_required: false,
          download_status: "ready",
        });
      }

      if (url.endsWith("/api/v2/session/create")) {
        createRequestBody = JSON.parse(String(init?.body ?? "{}"));
        return makeResponse({
          session_id: "hosted-session-download",
          received: createRequestBody,
        });
      }

      throw new Error(`Unexpected fetch: ${url}`);
    }) as typeof fetch;

    render(
      <AppProvider>
        <Harness />
      </AppProvider>,
    );

    const usaButton = await screen.findByRole("button", { name: /download required.*united states/i });
    fireEvent.click(usaButton);
    const launchButton = screen.getByRole("button", { name: /launch simulation environment/i });
    await waitFor(() => expect(launchButton).toBeDisabled());

    fireEvent.click(await screen.findByRole("button", { name: /download united states dataset/i }));

    await waitFor(() => expect(downloadStatusCalls).toBeGreaterThan(0));
    await waitFor(() => expect(launchButton).not.toBeDisabled());

    fireEvent.click(launchButton);

    await waitFor(() => expect(screen.getByTestId("session-id")).toHaveTextContent("hosted-session-download"));
    expect(createRequestBody).toMatchObject({
      country: "usa",
      provider: "google",
      model: "gemini-2.5-flash-lite",
      use_case: "public-policy-testing",
    });
  });
});
