import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { forwardRef } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import PolicyUpload from "@/pages/PolicyUpload";
import { AppProvider } from "@/contexts/AppContext";

const { forceGraphSpy } = vi.hoisted(() => ({
  forceGraphSpy: vi.fn(),
}));

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

  beforeEach(() => {
    forceGraphSpy.mockClear();
    global.fetch = vi.fn().mockImplementation(createPolicyFetch({
      processArtifact: baseKnowledgeArtifact(),
    })) as typeof fetch;
  });

  afterEach(() => {
    global.fetch = originalFetch;
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

    fireEvent.change(screen.getByPlaceholderText("What should the system extract from this document?"), {
      target: { value: "Extract institutions, policies, and who they target." },
    });

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

  it("seeds the guiding prompt from the default use-case config", async () => {
    render(
      <AppProvider>
        <PolicyUpload />
      </AppProvider>,
    );

    expect(
      await screen.findByDisplayValue(
        /Identify all entities, locations, organizations, and the specific impact mechanisms described in this policy document/i,
      ),
    ).toBeInTheDocument();
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
    expect(await screen.findByRole("progressbar", { name: /brief\.txt upload progress/i })).toBeInTheDocument();

    resolveProcess?.({
      ok: true,
      json: async () => baseKnowledgeArtifact(),
    } as Response);
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

    fireEvent.change(screen.getByPlaceholderText("What should the system extract from this document?"), {
      target: { value: "Extract the policy effects." },
    });
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
