import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useEffect, useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AppProvider, useApp } from "@/contexts/AppContext";
import { OnboardingModal } from "@/components/OnboardingModal";
import { resetBundledDemoState } from "@/lib/console-api";

const countriesResponse = [
  { name: "Singapore", code: "sg", flag_emoji: "🇸🇬", dataset_path: "configs/countries/singapore.yaml", available: true },
  { name: "USA", code: "usa", flag_emoji: "🇺🇸", dataset_path: "configs/countries/usa.yaml", available: true },
  { name: "India", code: "india", flag_emoji: "🇮🇳", dataset_path: "configs/countries/india.yaml", available: false },
  { name: "Japan", code: "japan", flag_emoji: "🇯🇵", dataset_path: "configs/countries/japan.yaml", available: false },
];

const providersResponse = [
  { name: "gemini", models: ["gemini-2.0-flash-lite", "gemini-2.5-flash-lite", "gemini-2.5-flash"], requires_api_key: true },
  { name: "openai", models: ["gpt-4o", "gpt-4o-mini"], requires_api_key: true },
  { name: "ollama", models: ["qwen3:4b-instruct-2507-q4_K_M"], requires_api_key: false },
];

function Harness({ openInitially = true }: { openInitially?: boolean }) {
  const [open, setOpen] = useState(openInitially);
  const { sessionId } = useApp();

  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>
        reopen modal
      </button>
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

describe("OnboardingModal", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    window.sessionStorage.clear();
    resetBundledDemoState();
    global.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);

      if (url.endsWith("/api/v2/countries")) {
        return makeResponse(countriesResponse);
      }

      if (url.endsWith("/api/v2/providers")) {
        return makeResponse(providersResponse);
      }

      if (url.endsWith("/api/v2/session/create")) {
        const body = JSON.parse(String(init?.body));
        return makeResponse({ session_id: "session-screen0", received: body });
      }

      throw new Error(`Unexpected fetch: ${url}`);
    }) as typeof fetch;
  });

  afterEach(() => {
    window.sessionStorage.clear();
    resetBundledDemoState();
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("defaults demo-static onboarding to Ollama so launch does not require an API key", async () => {
    vi.stubEnv("VITE_BOOT_MODE", "demo-static");
    global.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);

      if (url.endsWith("/demo-output.json")) {
        return makeResponse({
          session: { session_id: "demo-session" },
          source_run: {
            country: "singapore",
            use_case: "public-policy-testing",
            provider: "google",
            model: "gemini-2.5-flash",
            rounds: 20,
          },
          analysis_questions: [],
          population: {
            session_id: "demo-session",
            sample_count: 1,
            sample_seed: 7,
            sampled_personas: [],
          },
          simulationState: {
            session_id: "demo-session",
            status: "completed",
            planned_rounds: 20,
            current_round: 20,
            counters: {
              posts: 0,
              comments: 0,
              reactions: 0,
              active_authors: 0,
            },
            top_threads: [],
          },
        });
      }

      throw new Error(`Unexpected fetch: ${url}`);
    }) as typeof fetch;

    render(
      <AppProvider>
        <Harness />
      </AppProvider>,
    );

    await waitFor(() => expect(screen.getByTestId("session-id")).toHaveTextContent("demo-session"));
    const [providerSelect, modelSelect] = await screen.findAllByRole("combobox");
    expect(providerSelect).toHaveValue("ollama");
    expect(modelSelect).toHaveValue("qwen3:4b-instruct-2507-q4_K_M");
    expect(screen.queryByPlaceholderText("sk-...")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /launch simulation environment/i }));
    expect(screen.queryByText(/api key is required/i)).not.toBeInTheDocument();
  });

  it("loads live catalogs, hides the API key for Ollama, and creates a canonical session", async () => {
    render(
      <AppProvider>
        <Harness />
      </AppProvider>,
    );

    expect(screen.getByText("Configure your simulation environment")).toBeInTheDocument();

    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(2));
    expect(String(vi.mocked(global.fetch).mock.calls[0][0])).toContain("/api/v2/countries");
    expect(String(vi.mocked(global.fetch).mock.calls[1][0])).toContain("/api/v2/providers");
    const [providerSelect, modelSelect] = screen.getAllByRole("combobox");
    await waitFor(() => expect(modelSelect).toHaveValue("qwen3:4b-instruct-2507-q4_K_M"));
    const singaporeCard = screen.getByRole("button", { name: /singapore/i });
    expect(singaporeCard).toHaveClass("border-[hsl(var(--data-blue))]");
    expect(screen.getByRole("button", { name: /india/i })).toHaveAttribute("title", "Coming soon");
    expect(screen.getByRole("button", { name: /japan/i })).toHaveAttribute("title", "Coming soon");

    fireEvent.click(screen.getByRole("button", { name: /usa/i }));
    expect(screen.getByRole("button", { name: /usa/i })).toHaveClass("border-[hsl(var(--data-blue))]");
    fireEvent.change(providerSelect, { target: { value: "gemini" } });

    expect(screen.getByPlaceholderText("sk-...")).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText("sk-..."), { target: { value: "test-key" } });
    await waitFor(() => expect(modelSelect).toHaveValue("gemini-2.5-flash-lite"));

    fireEvent.change(providerSelect, { target: { value: "ollama" } });
    expect(screen.queryByPlaceholderText("sk-...")).not.toBeInTheDocument();

    fireEvent.change(providerSelect, { target: { value: "gemini" } });
    await waitFor(() => expect(modelSelect).toHaveValue("gemini-2.5-flash-lite"));

    fireEvent.click(screen.getByRole("button", { name: /product & market research/i }));
    fireEvent.click(screen.getByRole("button", { name: /launch simulation environment/i }));

    await waitFor(() => expect(screen.getByTestId("session-id")).toHaveTextContent("session-screen0"));

    const sessionCreateCall = vi.mocked(global.fetch).mock.calls.find(([url]) => String(url).endsWith("/api/v2/session/create"));
    expect(sessionCreateCall).toBeDefined();

    const payload = JSON.parse(String(sessionCreateCall?.[1]?.body));
    expect(payload.country).toBe("usa");
    expect(payload.provider).toBe("google");
    expect(payload.use_case).toBe("product-market-research");
    expect(payload.model).toBe("gemini-2.5-flash-lite");
  });

  it("shows India and Japan as unavailable in live mode and keeps them unselectable", async () => {
    vi.stubEnv("VITE_BOOT_MODE", "live");
    global.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);

      if (url.endsWith("/api/v2/countries")) {
        return makeResponse(countriesResponse.slice(0, 2));
      }

      if (url.endsWith("/api/v2/providers")) {
        return makeResponse(providersResponse);
      }

      if (url.endsWith("/api/v2/session/create")) {
        const body = JSON.parse(String(init?.body));
        return makeResponse({ session_id: "session-screen0", received: body });
      }

      throw new Error(`Unexpected fetch: ${url}`);
    }) as typeof fetch;

    render(
      <AppProvider>
        <Harness />
      </AppProvider>,
    );

    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(2));

    const indiaCard = await screen.findByRole("button", { name: /india/i });
    const japanCard = screen.getByRole("button", { name: /japan/i });
    expect(indiaCard).toHaveAttribute("title", "Coming soon");
    expect(japanCard).toHaveAttribute("title", "Coming soon");
    expect(indiaCard).not.toHaveAttribute("aria-disabled");
    expect(japanCard).not.toHaveAttribute("aria-disabled");

    fireEvent.click(indiaCard);
    expect(await screen.findByText("Coming soon")).toBeInTheDocument();
    fireEvent.click(japanCard);
    expect(screen.getByText("Coming soon")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /singapore/i })).toHaveClass("border-[hsl(var(--data-blue))]");
    expect(indiaCard).not.toHaveClass("border-[hsl(var(--data-blue))]");
    expect(japanCard).not.toHaveClass("border-[hsl(var(--data-blue))]");
  });

  it("does not auto-switch from Ollama to hosted providers when hosted providers require user keys", async () => {
    vi.stubEnv("VITE_BOOT_MODE", "live");
    global.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);

      if (url.endsWith("/api/v2/countries")) {
        return makeResponse(countriesResponse);
      }

      if (url.endsWith("/api/v2/providers")) {
        return makeResponse([
          { name: "gemini", models: ["gemini-2.5-flash-lite"], requires_api_key: true },
          { name: "openai", models: ["gpt-4o"], requires_api_key: true },
          { name: "ollama", models: ["qwen3:4b-instruct-2507-q4_K_M"], requires_api_key: false },
        ]);
      }

      if (url.endsWith("/api/v2/session/create")) {
        const body = JSON.parse(String(init?.body));
        return makeResponse({ session_id: "session-live-hosted", received: body });
      }

      throw new Error(`Unexpected fetch: ${url}`);
    }) as typeof fetch;

    render(
      <AppProvider>
        <Harness />
      </AppProvider>,
    );

    const [providerSelect, modelSelect] = await screen.findAllByRole("combobox");
    await waitFor(() => expect(providerSelect).toHaveValue("ollama"));
    expect(modelSelect).toHaveValue("qwen3:4b-instruct-2507-q4_K_M");
    expect(screen.queryByPlaceholderText("sk-...")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /launch simulation environment/i }));

    await waitFor(() => expect(screen.getByTestId("session-id")).toHaveTextContent("session-live-hosted"));

    const sessionCreateCall = vi.mocked(global.fetch).mock.calls.find(([url]) => String(url).endsWith("/api/v2/session/create"));
    expect(sessionCreateCall).toBeDefined();

    const payload = JSON.parse(String(sessionCreateCall?.[1]?.body));
    expect(payload.provider).toBe("ollama");
    expect(payload.model).toBe("qwen3:4b-instruct-2507-q4_K_M");
    expect(payload.api_key).toBeUndefined();
  });

  it("blocks launch until required provider credentials are provided", async () => {
    render(
      <AppProvider>
        <Harness />
      </AppProvider>,
    );

    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(2));
    fireEvent.change(screen.getAllByRole("combobox")[0], { target: { value: "gemini" } });
    fireEvent.click(screen.getByRole("button", { name: /launch simulation environment/i }));

    await waitFor(() => expect(screen.getByText(/api key is required/i)).toBeInTheDocument());
    expect(screen.getByTestId("session-id")).toHaveTextContent("none");
    expect(
      vi.mocked(global.fetch).mock.calls.some(([url]) => String(url).endsWith("/api/v2/session/create")),
    ).toBe(false);
  });

  it("re-synchronizes the modal from AppContext when it is reopened", async () => {
    function SeededHarness() {
      const [open, setOpen] = useState(true);
      const { setCountry, setModelProvider, setModelName, setModelApiKey, setUseCase } = useApp();

      useEffect(() => {
        setCountry("usa");
        setModelProvider("openai");
        setModelName("gpt-4o-mini");
        setModelApiKey("test-key");
        setUseCase("public-policy-testing");
      }, [setCountry, setModelApiKey, setModelName, setModelProvider, setUseCase]);

      return (
        <>
          <button type="button" onClick={() => setOpen(true)}>
            reopen modal
          </button>
          <OnboardingModal isOpen={open} onClose={() => setOpen(false)} />
        </>
      );
    }

    render(
      <AppProvider>
        <SeededHarness />
      </AppProvider>,
    );

    await waitFor(() => expect(screen.getAllByRole("combobox")[0]).toHaveValue("openai"));

    fireEvent.click(screen.getByRole("button", { name: /launch simulation environment/i }));
    await waitFor(() => expect(screen.queryByText("Configure your simulation environment")).not.toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "reopen modal" }));

    const [providerSelect, modelSelect] = screen.getAllByRole("combobox");
    await waitFor(() => expect(providerSelect).toHaveValue("openai"));
    expect(modelSelect).toHaveValue("gpt-4o-mini");
    expect(screen.getByPlaceholderText("sk-...")).toBeInTheDocument();
  });

  it("shows a live catalog error instead of falling back to local provider lists", async () => {
    vi.stubEnv("VITE_BOOT_MODE", "live");
    global.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);

      if (url.endsWith("/api/v2/countries")) {
        return {
          ok: false,
          status: 502,
          statusText: "Bad Gateway",
          json: async () => ({ detail: "countries unavailable" }),
        } as Response;
      }

      if (url.endsWith("/api/v2/providers")) {
        return {
          ok: false,
          status: 502,
          statusText: "Bad Gateway",
          json: async () => ({ detail: "providers unavailable" }),
        } as Response;
      }

      throw new Error(`Unexpected fetch: ${url}`);
    }) as typeof fetch;

    render(
      <AppProvider>
        <Harness />
      </AppProvider>,
    );

    expect(await screen.findByText(/live provider catalog is unavailable/i)).toBeInTheDocument();
    expect(screen.queryByText("Google Gemini")).not.toBeInTheDocument();
    expect(screen.queryByText("Ollama (Local)")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /launch simulation environment/i }));
    expect(screen.getByText(/select a provider and model before launching/i)).toBeInTheDocument();
  });

  it("shows an inline error when live session creation fails", async () => {
    vi.stubEnv("VITE_BOOT_MODE", "live");
    global.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);

      if (url.endsWith("/api/v2/countries")) {
        return makeResponse(countriesResponse);
      }

      if (url.endsWith("/api/v2/providers")) {
        return makeResponse(providersResponse);
      }

      if (url.endsWith("/api/v2/session/create")) {
        return {
          ok: false,
          status: 502,
          statusText: "Bad Gateway",
          json: async () => ({ detail: "session creation unavailable" }),
        } as Response;
      }

      throw new Error(`Unexpected fetch: ${url}`);
    }) as typeof fetch;

    render(
      <AppProvider>
        <Harness />
      </AppProvider>,
    );

    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(2));
    fireEvent.click(screen.getByRole("button", { name: /launch simulation environment/i }));

    expect(await screen.findByText("session creation unavailable")).toBeInTheDocument();
    expect(screen.getByText("Configure your simulation environment")).toBeInTheDocument();
    expect(screen.getByTestId("session-id")).toHaveTextContent("none");
    expect(screen.queryByText(/demo/i)).not.toBeInTheDocument();
  });
});
