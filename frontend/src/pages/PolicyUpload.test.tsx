import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { forwardRef, useEffect } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import PolicyUpload from "@/pages/PolicyUpload";
import { AppProvider, useApp } from "@/contexts/AppContext";

const { forceGraphSpy } = vi.hoisted(() => ({
  forceGraphSpy: vi.fn(),
}));

class MockEventSource {
  static instances: MockEventSource[] = [];
  static onCreate: ((url: string) => void) | null = null;

  url: string;
  listeners = new Map<string, Set<(event: MessageEvent) => void>>();
  onerror: ((event: Event) => void) | null = null;
  onopen: ((event: Event) => void) | null = null;
  close = vi.fn();

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
    MockEventSource.onCreate?.(url);
  }

  addEventListener(type: string, listener: (event: MessageEvent) => void) {
    const set = this.listeners.get(type) ?? new Set();
    set.add(listener);
    this.listeners.set(type, set);
  }

  removeEventListener(type: string, listener: (event: MessageEvent) => void) {
    const set = this.listeners.get(type);
    set?.delete(listener);
  }

  emit(type: string, payload: unknown) {
    const event = { data: JSON.stringify(payload) } as MessageEvent;
    for (const listener of this.listeners.get(type) ?? []) {
      listener(event);
    }
  }

  triggerOpen() {
    this.onopen?.(new Event("open"));
  }

  triggerError() {
    this.onerror?.(new Event("error"));
  }

  static reset() {
    MockEventSource.instances = [];
    MockEventSource.onCreate = null;
  }
}

vi.mock("react-force-graph-2d", () => ({
  default: forwardRef((props: { graphData: { nodes: Array<{ name?: string }>; links: Array<unknown> } }, _ref) => {
    forceGraphSpy(props);
    return (
      <div data-testid="graph-canvas">
        <span data-testid="graph-node-count">{props.graphData.nodes.length}</span>
        <span data-testid="graph-link-count">{props.graphData.links.length}</span>
        {props.graphData.nodes.map((node) => (
          <span key={node.name}>{node.name}</span>
        ))}
      </div>
    );
  }),
}));

describe("PolicyUpload", () => {
  const originalFetch = global.fetch;
  const originalEventSource = global.EventSource;

  beforeEach(() => {
    forceGraphSpy.mockClear();
    MockEventSource.reset();
    vi.stubGlobal("EventSource", MockEventSource as unknown as typeof EventSource);
    global.fetch = vi.fn().mockImplementation(createPolicyFetch({
      processArtifact: baseKnowledgeArtifact(),
    })) as typeof fetch;
  });

  afterEach(() => {
    global.fetch = originalFetch;
    global.EventSource = originalEventSource;
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("queues uploaded files, scraped text, and pasted text into a merged backend process request", async () => {
    global.fetch = vi.fn().mockImplementation(
      createPolicyFetch({
        processArtifact: baseKnowledgeArtifact(),
        scrapePayload: {
          url: "https://example.com/policy",
          title: "Policy Update",
          text: "Scraped policy text about transport support.",
          length: 44,
        },
      }),
    ) as typeof fetch;

    render(
      <AppProvider>
        <PolicyUpload />
      </AppProvider>,
    );

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["transport subsidies for seniors"], "budget.txt", { type: "text/plain" });
    fireEvent.change(fileInput, { target: { files: [file] } });
    await screen.findByText("budget.txt");

    fireEvent.click(screen.getByRole("button", { name: /^url$/i }));
    fireEvent.change(screen.getByPlaceholderText("https://example.com/policy-doc"), {
      target: { value: "https://example.com/policy" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^scrape$/i }));

    await waitFor(() => expect(screen.getByText("policy-update.txt")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /^paste$/i }));
    fireEvent.change(screen.getByPlaceholderText("Paste document text here..."), {
      target: { value: "Pasted text about households and fare relief." },
    });
    fireEvent.click(screen.getByRole("button", { name: /add as document/i }));
    await screen.findByText("pasted-text.txt");

    fireEvent.click(screen.getByRole("button", { name: /start extraction/i }));

    await waitFor(() => expect(global.fetch).toHaveBeenCalled());

    await waitFor(() => expect(screen.getByTestId("graph-node-count")).toHaveTextContent("7"));
    expect(screen.getByText("Paragraphs")).toBeInTheDocument();
    expect(screen.getByText("Top Entities")).toBeInTheDocument();
    expect(screen.getAllByText("Transport Subsidy").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Seniors").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Transport Authority").length).toBeGreaterThan(0);
    expect(screen.getByTestId("graph-node-count")).toHaveTextContent("7");
    expect(screen.getByTestId("graph-link-count")).toHaveTextContent("5");

    const topEntitiesCard = screen.getByRole("button", { name: "Top Entities" }).closest(".p-5");
    expect(topEntitiesCard).not.toBeNull();
    expect(within(topEntitiesCard as HTMLElement).getByText("Transport Subsidy")).toBeInTheDocument();
    expect(within(topEntitiesCard as HTMLElement).getByText("Seniors")).toBeInTheDocument();
    expect(within(topEntitiesCard as HTMLElement).getByText("Transport Authority")).toBeInTheDocument();
  });

  it("loads preset analysis questions as soon as a V2 session exists", async () => {
    function SeedAnalysisSession() {
      const { setSessionId, setUseCase, analysisQuestions } = useApp();

      useEffect(() => {
        setSessionId("session-screen1");
        setUseCase("public-policy-testing");
      }, [setSessionId, setUseCase]);

      return <span data-testid="question-count">{analysisQuestions.length}</span>;
    }

    global.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);

      if (url.endsWith("/api/v2/session/session-screen1/analysis-questions")) {
        return {
          ok: true,
          json: async () => ({
            session_id: "session-screen1",
            use_case: "public-policy-testing",
            questions: [
              {
                question: "Do you approve of this policy? Rate 1-10.",
                type: "scale",
                metric_name: "approval_rate",
                metric_label: "Approval Rate",
                metric_unit: "%",
                threshold: 7,
                threshold_direction: "gte",
                report_title: "Policy Approval",
                tooltip: "Percentage of agents who rated approval >= 7/10.",
              },
            ],
          }),
        } as Response;
      }

      if (url.endsWith("/api/v2/console/session")) {
        return {
          ok: true,
          json: async () => ({
            session_id: "session-screen1",
            mode: "live",
            status: "created",
            model_provider: "ollama",
            model_name: "qwen3:4b-instruct-2507-q4_K_M",
            embed_model_name: "nomic-embed-text",
            base_url: "http://127.0.0.1:11434/v1/",
            api_key_configured: true,
            api_key_masked: "ol...ama",
          }),
        } as Response;
      }

      return {
        ok: false,
        status: 404,
        statusText: "Not Found",
        json: async () => ({ detail: `Unhandled fetch: ${url}` }),
      } as Response;
    }) as typeof fetch;

    render(
      <AppProvider>
        <SeedAnalysisSession />
        <PolicyUpload />
      </AppProvider>,
    );

    expect(await screen.findByText("Analysis Questions")).toBeInTheDocument();
    expect(await screen.findByText("Do you approve of this policy? Rate 1-10.")).toBeInTheDocument();
    expect(screen.getByText("PRESET")).toBeInTheDocument();
    expect(screen.getByTestId("question-count")).toHaveTextContent("1");
  });

  it("persists edited analysis questions through the V2 config path and generates metadata while extracting", async () => {
    function SeedAnalysisSession() {
      const { setSessionId, setUseCase } = useApp();

      useEffect(() => {
        setSessionId("session-screen1");
        setUseCase("product-market-research");
      }, [setSessionId, setUseCase]);

      return null;
    }

    const fetchSpy = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);

      if (url.endsWith("/api/v2/session/session-screen1/analysis-questions")) {
        return {
          ok: true,
          json: async () => ({
            session_id: "session-screen1",
            use_case: "product-market-research",
            questions: [
              {
                question: "How interested are you in this product? Rate 1-10.",
                type: "scale",
                metric_name: "product_interest",
                metric_label: "Product Interest",
                metric_unit: "%",
                threshold: 7,
                threshold_direction: "gte",
                report_title: "Product Interest",
                tooltip: "Percentage of agents who rated interest >= 7/10.",
              },
            ],
          }),
        } as Response;
      }

      if (url.endsWith("/api/v2/console/session")) {
        return {
          ok: true,
          json: async () => ({
            session_id: "session-screen1",
            mode: "live",
            status: "created",
            model_provider: "ollama",
            model_name: "qwen3:4b-instruct-2507-q4_K_M",
            embed_model_name: "nomic-embed-text",
            base_url: "http://127.0.0.1:11434/v1/",
            api_key_configured: true,
            api_key_masked: "ol...ama",
          }),
        } as Response;
      }

      if (url.endsWith("/api/v2/questions/generate-metadata")) {
        const body = JSON.parse(String(init?.body));
        expect(body.question).toBe("What would you improve about this product?");
        return {
          ok: true,
          json: async () => ({
            type: "open-ended",
            metric_name: "product_feedback",
            report_title: "Product Feedback",
          }),
        } as Response;
      }

      if (url.endsWith("/api/v2/console/session/session-screen1/config")) {
        const body = JSON.parse(String(init?.body));
        expect(Array.isArray(body.analysis_questions)).toBe(true);
        expect(body.analysis_questions.some((item: { question?: string }) => item.question === "What would you improve about this product?")).toBe(true);
        return {
          ok: true,
          json: async () => ({
            session_id: "session-screen1",
            country: "singapore",
            use_case: "product-market-research",
            provider: "ollama",
            model: "qwen3:4b-instruct-2507-q4_K_M",
            api_key_configured: true,
            guiding_prompt: null,
          }),
        } as Response;
      }

      if (url.includes("/knowledge/process")) {
        return {
          ok: true,
          json: async () => baseKnowledgeArtifact(),
        } as Response;
      }

      if (url.endsWith("/demo-output.json")) {
        return {
          ok: true,
          json: async () => ({ knowledge: { ...baseKnowledgeArtifact(), session_id: "demo-session" } }),
        } as Response;
      }

      return {
        ok: false,
        status: 404,
        statusText: "Not Found",
        json: async () => ({ detail: `Unhandled fetch: ${url}` }),
      } as Response;
    });
    global.fetch = fetchSpy as typeof fetch;

    render(
      <AppProvider>
        <SeedAnalysisSession />
        <PolicyUpload />
      </AppProvider>,
    );

    await screen.findByText("How interested are you in this product? Rate 1-10.");
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(fileInput, {
      target: { files: [new File(["customer feedback"], "brief.txt", { type: "text/plain" })] },
    });
    fireEvent.click(screen.getByRole("button", { name: /add question/i }));

    const questionEditors = await screen.findAllByPlaceholderText("Type your analysis question...");
    const newQuestion = questionEditors[questionEditors.length - 1];
    fireEvent.change(newQuestion, { target: { value: "What would you improve about this product?" } });

    fireEvent.click(screen.getByRole("button", { name: /start extraction/i }));
    await waitFor(() =>
      expect(
        vi.mocked(global.fetch).mock.calls.some(([url]) => String(url).endsWith("/api/v2/questions/generate-metadata")),
      ).toBe(true),
    );
    await waitFor(() =>
      expect(
        vi.mocked(global.fetch).mock.calls.some(([url]) => String(url).endsWith("/api/v2/console/session/session-screen1/config")),
      ).toBe(true),
    );
    await waitFor(() => expect(screen.getAllByText("Ready").length).toBeGreaterThan(1));
  });

  it("accepts drag-and-drop uploads into the file list", async () => {
    render(
      <AppProvider>
        <PolicyUpload />
      </AppProvider>,
    );

    const uploadZone = screen.getByText("Drop documents here").closest("label");
    expect(uploadZone).not.toBeNull();

    fireEvent.drop(uploadZone as HTMLElement, {
      dataTransfer: {
        files: [new File(["dragged transport brief"], "dragged.pdf", { type: "application/pdf" })],
      },
    });

    expect(await screen.findByText("dragged.pdf")).toBeInTheDocument();
  });

  it("shows per-file progress bars while extraction is running", async () => {
    let resolveProcess: ((value: Response) => void) | null = null;
    global.fetch = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/v2/console/session")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            session_id: "session-screen1",
            mode: "live",
            status: "created",
            model_provider: "ollama",
            model_name: "qwen3:4b-instruct-2507-q4_K_M",
            embed_model_name: "nomic-embed-text",
            base_url: "http://127.0.0.1:11434/v1/",
            api_key_configured: true,
            api_key_masked: "ol...ama",
          }),
        } as Response);
      }
      if (url.includes("/knowledge/process")) {
        return new Promise<Response>((resolve) => {
          resolveProcess = resolve;
        });
      }
      return Promise.resolve({
        ok: false,
        status: 404,
        statusText: "Not Found",
        json: async () => ({ detail: `Unhandled fetch: ${url}` }),
      } as Response);
    }) as typeof fetch;

    render(
      <AppProvider>
        <PolicyUpload />
      </AppProvider>,
    );

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(fileInput, {
      target: {
        files: [new File(["progress payload"], "brief.txt", { type: "text/plain" })],
      },
    });
    await screen.findByText("brief.txt");

    fireEvent.click(screen.getByRole("button", { name: /start extraction/i }));
    expect(await screen.findByRole("progressbar", { name: /brief\.txt extraction progress/i })).toBeInTheDocument();

    resolveProcess?.({
      ok: true,
      json: async () => baseKnowledgeArtifact(),
    } as Response);
  });

  it("streams incremental graph updates and chunk progress before the final artifact resolves", async () => {
    vi.stubEnv("VITE_BOOT_MODE", "live");

    const callOrder: string[] = [];
    let resolveProcess: ((value: Response) => void) | null = null;
    MockEventSource.onCreate = () => callOrder.push("stream");

    global.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);

      if (url.endsWith("/api/v2/console/session")) {
        callOrder.push("session");
        return {
          ok: true,
          json: async () => ({
            session_id: "session-screen1",
            mode: "live",
            status: "created",
            model_provider: "ollama",
            model_name: "qwen3:4b-instruct-2507-q4_K_M",
            embed_model_name: "nomic-embed-text",
            base_url: "http://127.0.0.1:11434/v1/",
            api_key_configured: true,
            api_key_masked: "ol...ama",
          }),
        } as Response;
      }

      if (url.includes("/knowledge/process")) {
        callOrder.push("process");
        return new Promise<Response>((resolve) => {
          resolveProcess = resolve;
        });
      }

      return {
        ok: false,
        status: 404,
        statusText: "Not Found",
        json: async () => ({ detail: `Unhandled fetch: ${url}` }),
      } as Response;
    }) as typeof fetch;

    render(
      <AppProvider>
        <PolicyUpload />
      </AppProvider>,
    );

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(fileInput, {
      target: {
        files: [new File(["streamed policy"], "brief.txt", { type: "text/plain" })],
      },
    });
    await screen.findByText("brief.txt");

    fireEvent.click(screen.getByRole("button", { name: /start extraction/i }));

    await waitFor(() => expect(MockEventSource.instances.length).toBe(1));
    await waitFor(() => expect(callOrder).toContain("process"));
    expect(callOrder).toContain("session");
    expect(MockEventSource.instances[0].url).toContain("/knowledge/stream");

    const source = MockEventSource.instances[0];
    act(() => {
      source.emit("knowledge_started", {
        message: "Streaming knowledge extraction",
        progress: 8,
      });
      source.emit("knowledge_chunk_started", {
        chunk_index: 1,
        chunk_count: 2,
        document_name: "brief.txt",
      });
      source.emit("knowledge_partial", {
        entity_nodes: [
          {
            id: "policy:streamed",
            label: "Streamed Subsidy",
            type: "policy",
            summary: "Streaming partial graph.",
            importance_score: 0.66,
          },
          {
            id: "group:streamed",
            label: "Streamed Group",
            type: "group",
            summary: "Streaming partial graph.",
            importance_score: 0.42,
          },
        ],
        relationship_edges: [
          {
            source: "policy:streamed",
            target: "group:streamed",
            type: "relates_to",
            label: "relates to",
            summary: "Partial relation.",
          },
        ],
        processing_logs: ["Chunk 1 processed"],
      });
    });

    await waitFor(() => expect(screen.getByTestId("graph-node-count")).toHaveTextContent("2"));
    expect(screen.getByRole("progressbar", { name: /knowledge extraction progress/i })).toBeInTheDocument();

    resolveProcess?.({
      ok: true,
      json: async () => baseKnowledgeArtifact(),
    } as Response);

    act(() => {
      source.emit("knowledge_chunk_completed", {
        chunk_index: 1,
        chunk_count: 2,
        progress: 55,
      });
      source.emit("knowledge_completed", {
        ...baseKnowledgeArtifact(),
      });
    });

    await waitFor(() => expect(screen.getByTestId("graph-node-count")).toHaveTextContent("7"));
    expect(screen.getByRole("button", { name: /proceed/i })).toBeInTheDocument();
    expect(source.close).toHaveBeenCalled();
  });

  it("sends uploaded files through the backend upload parser path instead of browser-decoded document text", async () => {
    const fetchSpy = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);

      if (url.endsWith("/api/v2/console/session")) {
        return {
          ok: true,
          json: async () => ({
            session_id: "session-screen1",
            mode: "live",
            status: "created",
            model_provider: "ollama",
            model_name: "qwen3:4b-instruct-2507-q4_K_M",
            embed_model_name: "nomic-embed-text",
            base_url: "http://127.0.0.1:11434/v1/",
            api_key_configured: true,
            api_key_masked: "ol...ama",
          }),
        } as Response;
      }

      if (url.endsWith("/knowledge/upload")) {
        expect(init?.body).toBeInstanceOf(FormData);
        const formData = init?.body as FormData;
        const uploadedFile = formData.get("file");
        expect(uploadedFile).toBeInstanceOf(File);
        expect((uploadedFile as File).name).toBe("budget.pdf");
        expect(formData.get("guiding_prompt")).toBe("Extract the policy effects.");
        return {
          ok: true,
          json: async () => baseKnowledgeArtifact(),
        } as Response;
      }

      if (url.endsWith("/knowledge/process")) {
        throw new Error("Uploaded files should not be sent through /knowledge/process");
      }

      return {
        ok: false,
        status: 404,
        statusText: "Not Found",
        json: async () => ({ detail: `Unhandled fetch: ${url}` }),
      } as Response;
    });
    global.fetch = fetchSpy as typeof fetch;

    render(
      <AppProvider>
        <PolicyUpload />
      </AppProvider>,
    );

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(fileInput, {
      target: {
        files: [new File(["binary-looking-payload"], "budget.pdf", { type: "application/pdf" })],
      },
    });
    await screen.findByText("budget.pdf");
    fireEvent.click(screen.getByRole("button", { name: /start extraction/i }));

    await waitFor(() => expect(fetchSpy).toHaveBeenCalled());
    expect(fetchSpy.mock.calls.some(([url]) => String(url).endsWith("/knowledge/upload"))).toBe(true);
  });

  it("renders the new segmented family control, requested display-bucket filters, and hides relationship labels by default", async () => {
    global.fetch = vi.fn().mockImplementation(createPolicyFetch({
      processArtifact: baseKnowledgeArtifact(),
    })) as typeof fetch;

    const { container } = render(
      <AppProvider>
        <PolicyUpload />
      </AppProvider>,
    );

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(fileInput, {
      target: {
        files: [new File(["graph labels"], "brief.txt", { type: "text/plain" })],
      },
    });
    await screen.findByText("brief.txt");

    fireEvent.click(screen.getByRole("button", { name: /start extraction/i }));

    await waitFor(() => expect(screen.getByTestId("graph-node-count")).toHaveTextContent("7"));

    const forceGraphProps = forceGraphSpy.mock.calls.at(-1)?.[0];
    expect(forceGraphProps.nodeRelSize).toBe(1);
    expect(forceGraphProps.enableNodeDrag).toBe(true);
    expect(forceGraphProps.nodeCanvasObjectMode({})).toBe("replace");
    expect(forceGraphProps.linkCanvasObjectMode({})).toBe("after");
    expect(typeof forceGraphProps.linkCanvasObject).toBe("function");

    expect(screen.getByRole("button", { name: "All" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Nemotron" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Other" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Document" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Facet" })).not.toBeInTheDocument();

    expect(screen.getByRole("button", { name: "Organization" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Persons" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Location" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Age Group" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Event" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Concept" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Industry" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Other" })).toBeInTheDocument();

    expect(screen.getByRole("button", { name: "Labels" })).toBeInTheDocument();

    const textCalls: Array<{ text: string; x: number; y: number }> = [];
    const ctx = {
      beginPath: vi.fn(),
      arc: vi.fn(),
      fill: vi.fn(),
      stroke: vi.fn(),
      fillText: vi.fn((text: string, x: number, y: number) => textCalls.push({ text, x, y })),
      measureText: vi.fn((text: string) => ({ width: text.length * 7 })),
      save: vi.fn(),
      restore: vi.fn(),
      translate: vi.fn(),
      rotate: vi.fn(),
      clearRect: vi.fn(),
      fillRect: vi.fn(),
      font: "",
      textAlign: "",
      textBaseline: "",
      globalAlpha: 1,
      lineWidth: 1,
      strokeStyle: "",
      fillStyle: "",
    } as any;

    forceGraphProps.nodeCanvasObject(
      { name: "Transport Subsidy", x: 100, y: 80, val: 0.93 },
      ctx,
      1,
    );

    expect(ctx.arc).toHaveBeenCalledWith(expect.any(Number), expect.any(Number), 12, 0, Math.PI * 2);
    expect(textCalls.some((call) => call.text === "Transport Subsidy" && call.x > 100)).toBe(true);

    expect(container.firstElementChild?.className).toContain("lg:grid-cols-[420px_1fr]");
  });

  it("filters the graph by entity family and display bucket, and toggles relationship labels on demand", async () => {
    global.fetch = vi.fn().mockImplementation(createPolicyFetch({
      processArtifact: baseKnowledgeArtifact(),
    })) as typeof fetch;

    render(
      <AppProvider>
        <PolicyUpload />
      </AppProvider>,
    );

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(fileInput, {
      target: {
        files: [new File(["facet graph"], "brief.txt", { type: "text/plain" })],
      },
    });

    fireEvent.click(screen.getByRole("button", { name: /start extraction/i }));

    await waitFor(() => expect(screen.getByTestId("graph-node-count")).toHaveTextContent("7"));
    expect(screen.getByTestId("graph-node-count")).toHaveTextContent("7");
    expect(forceGraphSpy.mock.calls.at(-1)?.[0].graphData.nodes.find((node: { name: string }) => node.name === "Transport Subsidy")?.val).toBe(0.93);
    expect(forceGraphSpy.mock.calls.at(-1)?.[0].graphData.nodes.find((node: { name: string }) => node.name === "Concept")).toBeUndefined();

    fireEvent.click(screen.getByRole("button", { name: "Nemotron" }));
    expect(screen.getByTestId("graph-node-count")).toHaveTextContent("3");

    fireEvent.click(screen.getByRole("button", { name: "Location" }));
    expect(screen.getByTestId("graph-node-count")).toHaveTextContent("1");
    expect(screen.getByText("Woodlands")).toBeInTheDocument();

    const initialProps = forceGraphSpy.mock.calls.at(-1)?.[0];
    const quietCtx = {
      save: vi.fn(),
      restore: vi.fn(),
      fillRect: vi.fn(),
      fillText: vi.fn(),
      measureText: vi.fn(() => ({ width: 40 })),
      font: "",
      textAlign: "",
      textBaseline: "",
      fillStyle: "",
    } as any;
    initialProps.linkCanvasObject(
      {
        label: "targets",
        type: "targets",
        source: { x: 0, y: 0 },
        target: { x: 100, y: 0 },
      },
      quietCtx,
      1,
    );
    expect(quietCtx.fillText).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Labels" }));
    expect(screen.getByRole("button", { name: "Labels" })).toBeInTheDocument();

    const labeledProps = forceGraphSpy.mock.calls.at(-1)?.[0];
    expect(labeledProps.linkCanvasObjectMode({})).toBe("after");
    const labelCtx = {
      save: vi.fn(),
      restore: vi.fn(),
      fillRect: vi.fn(),
      fillText: vi.fn(),
      measureText: vi.fn(() => ({ width: 40 })),
      font: "",
      textAlign: "",
      textBaseline: "",
      fillStyle: "",
    } as any;
    labeledProps.linkCanvasObject(
      {
        label: "targets",
        type: "targets",
        source: { x: 0, y: 0 },
        target: { x: 100, y: 0 },
      },
      labelCtx,
      1,
    );
    expect(labelCtx.fillText).toHaveBeenCalled();
  });

  it("shows an inline error when upload extraction fails", async () => {
    global.fetch = vi.fn().mockImplementation(
      createPolicyFetch({
        processError: "Gemini extraction failed",
        demoAvailable: false,
      }),
    ) as typeof fetch;

    render(
      <AppProvider>
        <PolicyUpload />
      </AppProvider>,
    );

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(fileInput, {
      target: {
        files: [new File(["small payload"], "note.txt", { type: "text/plain" })],
      },
    });
    await screen.findByText("note.txt");

    fireEvent.click(screen.getByRole("button", { name: /start extraction/i }));

    await waitFor(() =>
      expect(
        vi.mocked(global.fetch).mock.calls.some(([url]) => String(url).includes("/knowledge/process")),
      ).toBe(true),
    );
    expect(await screen.findByText("Gemini extraction failed")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /proceed/i })).not.toBeInTheDocument();
  });

  it("shows a live extraction error instead of loading bundled demo knowledge", async () => {
    vi.stubEnv("VITE_BOOT_MODE", "live");
    global.fetch = vi.fn().mockImplementation(
      createPolicyFetch({
        processError: "Gemini extraction failed",
        demoAvailable: true,
      }),
    ) as typeof fetch;

    render(
      <AppProvider>
        <PolicyUpload />
      </AppProvider>,
    );

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(fileInput, {
      target: {
        files: [new File(["small payload"], "note.txt", { type: "text/plain" })],
      },
    });
    await screen.findByText("note.txt");

    fireEvent.click(screen.getByRole("button", { name: /start extraction/i }));

    expect(await screen.findByText("Gemini extraction failed")).toBeInTheDocument();
    expect(
      vi.mocked(global.fetch).mock.calls.some(([url]) => String(url).endsWith("/demo-output.json")),
    ).toBe(false);
    expect(screen.queryByText("Demo mode")).not.toBeInTheDocument();
  });

  it("shows a live URL scrape error instead of queuing a synthetic fallback file", async () => {
    vi.stubEnv("VITE_BOOT_MODE", "live");
    global.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);

      if (url.endsWith("/api/v2/console/session")) {
        return {
          ok: true,
          json: async () => ({
            session_id: "session-screen1",
            mode: "live",
            status: "created",
            model_provider: "ollama",
            model_name: "qwen3:4b-instruct-2507-q4_K_M",
            embed_model_name: "nomic-embed-text",
            base_url: "http://127.0.0.1:11434/v1/",
            api_key_configured: true,
            api_key_masked: "ol...ama",
          }),
        } as Response;
      }

      if (url.includes("/scrape")) {
        return {
          ok: false,
          status: 502,
          statusText: "Bad Gateway",
          json: async () => ({ detail: "live scrape unavailable" }),
        } as Response;
      }

      if (url.endsWith("/demo-output.json")) {
        return {
          ok: true,
          json: async () => ({
            knowledge: {
              ...baseKnowledgeArtifact(),
              session_id: "demo-session",
            },
          }),
        } as Response;
      }

      return {
        ok: false,
        status: 404,
        statusText: "Not Found",
        json: async () => ({ detail: `Unhandled fetch: ${url}` }),
      } as Response;
    }) as typeof fetch;

    render(
      <AppProvider>
        <PolicyUpload />
      </AppProvider>,
    );

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(fileInput, {
      target: {
        files: [new File(["transport brief"], "budget.pdf", { type: "application/pdf" })],
      },
    });
    await screen.findByText("budget.pdf");

    fireEvent.click(screen.getByRole("button", { name: /^url$/i }));
    fireEvent.change(screen.getByPlaceholderText("https://example.com/policy-doc"), {
      target: { value: "https://example.com/policy" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^scrape$/i }));

    expect(await screen.findByText("live scrape unavailable")).toBeInTheDocument();
    expect(screen.queryByText(/https-example-com-policy\.txt/i)).not.toBeInTheDocument();
    expect(screen.queryByText("Demo mode")).not.toBeInTheDocument();
  });
});

function baseKnowledgeArtifact() {
  return {
    session_id: "session-screen1",
    document: {
      document_id: "merged-3-documents",
      source_path: "merged://knowledge-documents",
      source_count: 3,
      sources: [],
      text_length: 1832,
      paragraph_count: 9,
    },
    summary: "Budget measures target transport and senior households.",
    entity_nodes: [
      {
        id: "policy:transport",
        label: "Transport Subsidy",
        type: "policy",
        description: "Fare support.<SEP>Fare support.",
        summary: "Fare support.",
        weight: 0.8,
        families: ["document"],
        display_bucket: "concept",
        support_count: 4,
        degree_count: 3,
        importance_score: 0.93,
      },
      {
        id: "person:residents",
        label: "Residents",
        type: "group",
        description: "Local residents.<SEP>Local residents.",
        summary: "Local residents.",
        weight: 0.55,
        families: ["document"],
        support_count: 2,
        degree_count: 1,
        importance_score: 0.47,
      },
      {
        id: "group:seniors",
        label: "Seniors",
        type: "demographic",
        description: "Older households.<SEP>Older households.",
        summary: "Older households.",
        weight: 0.6,
        families: ["document", "facet"],
        facet_kind: "age_cohort",
        canonical_key: "age_cohort:senior",
        display_bucket: "age_group",
        support_count: 3,
        degree_count: 2,
        importance_score: 0.72,
      },
      {
        id: "org:transport",
        label: "Transport Authority",
        type: "organization",
        description: "Government transport body.<SEP>Government transport body.",
        summary: "Government transport body.",
        weight: 0.5,
        families: ["document"],
        display_bucket: "organization",
        support_count: 3,
        degree_count: 2,
        importance_score: 0.69,
      },
      {
        id: "loc:woodlands",
        label: "Woodlands",
        type: "location",
        description: "Planning area.<SEP>Planning area.",
        summary: "Planning area.",
        weight: 0.4,
        families: ["document", "facet"],
        facet_kind: "planning_area",
        canonical_key: "planning_area:woodlands",
        display_bucket: "location",
        support_count: 2,
        degree_count: 1,
        importance_score: 0.44,
      },
      {
        id: "event:launch",
        label: "Launch Event",
        type: "event",
        description: "Announcement moment.<SEP>Announcement moment.",
        summary: "Announcement moment.",
        weight: 0.3,
        families: ["document"],
        display_bucket: "event",
        support_count: 1,
        degree_count: 1,
        importance_score: 0.29,
      },
      {
        id: "industry:transport",
        label: "Transportation & Storage",
        type: "industry",
        description: "Industry vertical affected by the policy.",
        summary: "Industry vertical affected by the policy.",
        weight: 0.45,
        families: ["document", "facet"],
        facet_kind: "industry",
        canonical_key: "industry:transportation_storage",
        display_bucket: "industry",
        support_count: 2,
        degree_count: 1,
        importance_score: 0.43,
      },
      {
        id: "metric:tfr",
        label: "TFR",
        type: "metric",
        description: "Total fertility rate.",
        summary: "Total fertility rate.",
        weight: 0.21,
        families: ["document"],
        display_bucket: "other",
        support_count: 1,
        degree_count: 0,
        importance_score: 0.18,
        low_value_orphan: true,
        ui_default_hidden: true,
      },
      {
        id: "concept:placeholder",
        label: "Concept",
        type: "entity",
        description: "Generic placeholder text.",
        summary: "Generic placeholder text.",
        weight: 0.99,
        families: ["document"],
        display_bucket: "other",
        support_count: 1,
        degree_count: 8,
        importance_score: 0.96,
        generic_placeholder: true,
        ui_default_hidden: true,
      },
    ],
    relationship_edges: [
      { source: "policy:transport", target: "group:seniors", type: "targets", label: "targets", summary: "targets older households.<SEP>targets older households." },
      { source: "org:transport", target: "policy:transport", type: "implements", label: "implements", summary: "implements the subsidy." },
      { source: "policy:transport", target: "loc:woodlands", type: "located_in", label: "located in", summary: "piloted in woodlands." },
      { source: "policy:transport", target: "person:residents", type: "affects", label: "affects", summary: "affects local residents." },
      { source: "policy:transport", target: "industry:transport", type: "affects", label: "affects", summary: "affects transport operators." },
    ],
    entity_type_counts: {
      policy: 1,
    },
    processing_logs: ["Inserted document", "Extracted graph"],
    guiding_prompt: null,
    demographic_focus_summary: null,
  };
}

function createPolicyFetch({
  processArtifact,
  scrapePayload,
  processError,
  demoAvailable = true,
}: {
  processArtifact?: Record<string, unknown>;
  scrapePayload?: { url: string; title: string; text: string; length: number };
  processError?: string;
  demoAvailable?: boolean;
}) {
  return async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);

    if (url.endsWith("/api/v2/console/session")) {
      return {
        ok: true,
        json: async () => ({
          session_id: "session-screen1",
          mode: "live",
          status: "created",
          model_provider: "ollama",
          model_name: "qwen3:4b-instruct-2507-q4_K_M",
          embed_model_name: "nomic-embed-text",
          base_url: "http://127.0.0.1:11434/v1/",
          api_key_configured: true,
          api_key_masked: "ol...ama",
        }),
      };
    }

    if (url.includes("/scrape")) {
      return {
        ok: true,
        json: async () => scrapePayload ?? {
          url: "https://example.com/policy",
          title: "Policy Update",
          text: "Scraped policy text about transport support.",
          length: 44,
        },
      };
    }

    if (url.includes("/knowledge/upload")) {
      return {
        ok: true,
        json: async () => processArtifact ?? baseKnowledgeArtifact(),
      };
    }

    if (url.includes("/knowledge/process")) {
      if (processError) {
        return {
          ok: false,
          status: 502,
          statusText: "Bad Gateway",
          json: async () => ({ detail: processError }),
        };
      }
      return {
        ok: true,
        json: async () => processArtifact ?? baseKnowledgeArtifact(),
      };
    }

    if (url.endsWith("/demo-output.json") && demoAvailable) {
      return {
        ok: true,
        json: async () => ({
          knowledge: {
            ...baseKnowledgeArtifact(),
            session_id: "demo-session",
          },
        }),
      };
    }

    if (url.endsWith("/demo-output.json")) {
      return {
        ok: false,
        status: 404,
        statusText: "Not Found",
        json: async () => ({ detail: "demo unavailable" }),
      };
    }

    return {
      ok: false,
      status: 404,
      statusText: "Not Found",
      json: async () => ({ detail: `Unhandled fetch: ${url}` }),
    };
  };
}
