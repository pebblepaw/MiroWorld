import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        session_id: "session-screen1",
        document: {
          document_id: "doc-1",
          file_name: "budget.pdf",
          file_type: "application/pdf",
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
          },
        ],
        relationship_edges: [
          { source: "policy:transport", target: "group:seniors", type: "targets", label: "targets", summary: "targets older households.<SEP>targets older households." },
          { source: "org:transport", target: "policy:transport", type: "implements", label: "implements", summary: "implements the subsidy." },
          { source: "policy:transport", target: "loc:woodlands", type: "located_in", label: "located in", summary: "piloted in woodlands." },
          { source: "policy:transport", target: "person:residents", type: "affects", label: "affects", summary: "affects local residents." },
          { source: "policy:transport", target: "industry:transport", type: "affects", label: "affects", summary: "affects transport operators." },
        ],
        processing_logs: ["Inserted document", "Extracted graph"],
      }),
    }) as typeof fetch;
  });

  afterEach(() => {
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("uploads the selected file with guiding_prompt and renders backend-driven metrics and top entities", async () => {
    render(
      <AppProvider>
        <PolicyUpload />
      </AppProvider>,
    );

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["transport subsidies for seniors"], "budget.pdf", { type: "application/pdf" });
    fireEvent.change(fileInput, { target: { files: [file] } });

    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "Extract institutions, policies, and who they target." },
    });

    fireEvent.click(screen.getByRole("button", { name: /extract knowledge graph/i }));

    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(2));

    const uploadCall = vi.mocked(global.fetch).mock.calls[1];
    expect(uploadCall[0]).toContain("/api/v2/console/session/session-screen1/knowledge/upload");
    expect(uploadCall[1]?.method).toBe("POST");
    const formData = uploadCall[1]?.body as FormData;
    expect(formData.get("guiding_prompt")).toBe("Extract institutions, policies, and who they target.");
    expect(formData.get("file")).toBeInstanceOf(File);

    await waitFor(() => expect(screen.getByTestId("graph-node-count")).toHaveTextContent("8"));
    expect(screen.getByText("Paragraph Count")).toBeInTheDocument();
    expect(screen.getByText("9")).toBeInTheDocument();
    expect(screen.getByText("Top 3 Entities")).toBeInTheDocument();
    expect(screen.getAllByText("Transport Subsidy").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Seniors").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Transport Authority").length).toBeGreaterThan(0);
    expect(screen.getByTestId("graph-node-count")).toHaveTextContent("8");
    expect(screen.getByTestId("graph-link-count")).toHaveTextContent("5");
  });

  it("renders the new segmented family control, requested display-bucket filters, and hides relationship labels by default", async () => {
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

    fireEvent.click(screen.getByRole("button", { name: /extract knowledge graph/i }));

    await waitFor(() => expect(screen.getByTestId("graph-node-count")).toHaveTextContent("8"));

    const forceGraphProps = forceGraphSpy.mock.calls.at(-1)?.[0];
    expect(forceGraphProps.nodeRelSize).toBe(1);
    expect(forceGraphProps.nodeCanvasObjectMode({})).toBe("replace");
    expect(forceGraphProps.linkCanvasObjectMode).toBeUndefined();
    expect(typeof forceGraphProps.linkCanvasObject).toBe("function");

    expect(screen.getByRole("button", { name: "All" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Nemotron Entities" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Other Entities" })).toBeInTheDocument();
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

    expect(screen.getByRole("button", { name: /relationship labels off/i })).toBeInTheDocument();

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

    expect(container.firstElementChild?.className).toContain("lg:grid-cols-[0.88fr_1.12fr]");
  });

  it("filters the graph by entity family and display bucket, and toggles relationship labels on demand", async () => {
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

    fireEvent.click(screen.getByRole("button", { name: /extract knowledge graph/i }));

    await waitFor(() => expect(screen.getByTestId("graph-node-count")).toHaveTextContent("8"));
    expect(screen.getByTestId("graph-node-count")).toHaveTextContent("8");
    expect(forceGraphSpy.mock.calls.at(-1)?.[0].graphData.nodes.find((node: { name: string }) => node.name === "Transport Subsidy")?.val).toBe(0.93);

    fireEvent.click(screen.getByRole("button", { name: "Nemotron Entities" }));
    expect(screen.getByTestId("graph-node-count")).toHaveTextContent("3");

    fireEvent.click(screen.getByRole("button", { name: "Location" }));
    expect(screen.getByTestId("graph-node-count")).toHaveTextContent("1");
    expect(screen.getByText("Woodlands")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /relationship labels off/i }));
    expect(screen.getByRole("button", { name: /relationship labels on/i })).toBeInTheDocument();
  });

  it("shows an inline error when upload extraction fails", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ session_id: "session-screen1", mode: "live", status: "created" }),
      })
      .mockResolvedValueOnce({
        ok: false,
        json: async () => ({ detail: "Gemini extraction failed" }),
      }) as typeof fetch;

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

    fireEvent.click(screen.getByRole("button", { name: /extract knowledge graph/i }));

    expect(await screen.findByText("Gemini extraction failed")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /proceed/i })).not.toBeInTheDocument();
  });
});
