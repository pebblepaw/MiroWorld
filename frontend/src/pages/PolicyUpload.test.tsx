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
        },
        summary: "Budget measures target transport and senior households.",
        entity_nodes: [
          { id: "policy:transport", label: "Transport Subsidy", type: "policy", description: "Fare support", weight: 0.8, families: ["document"] },
          { id: "group:seniors", label: "Seniors", type: "demographic", description: "Older households", weight: 0.6, families: ["document", "facet"], facet_kind: "age_cohort", canonical_key: "age_cohort:senior" },
          { id: "org:transport", label: "Transport Authority", type: "organization", description: "Government transport body", weight: 0.5 },
          { id: "loc:woodlands", label: "Woodlands", type: "location", description: "Planning area", weight: 0.4, families: ["document", "facet"], facet_kind: "planning_area", canonical_key: "planning_area:woodlands" },
          { id: "event:launch", label: "Launch Event", type: "event", description: "Announcement moment", weight: 0.3 },
        ],
        relationship_edges: [
          { source: "policy:transport", target: "group:seniors", type: "targets", label: "targets" },
          { source: "org:transport", target: "policy:transport", type: "implements", label: "implements" },
          { source: "policy:transport", target: "loc:woodlands", type: "located_in", label: "located in" },
        ],
        processing_logs: ["Inserted document", "Extracted graph"],
      }),
    }) as typeof fetch;
  });

  afterEach(() => {
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("uploads the selected file with guiding_prompt and renders backend-driven stats", async () => {
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

    await screen.findByText("Transport Subsidy");
    expect(screen.getByText("Text Length")).toBeInTheDocument();
    expect(screen.getByText("1832")).toBeInTheDocument();
    expect(screen.getByTestId("graph-node-count")).toHaveTextContent("5");
    expect(screen.getByTestId("graph-link-count")).toHaveTextContent("3");
  });

  it("renders compact dots, side labels, dynamic legend entries, and visible link labels", async () => {
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

    await screen.findByText("Transport Subsidy");

    const forceGraphProps = forceGraphSpy.mock.calls.at(-1)?.[0];
    expect(forceGraphProps.nodeRelSize).toBe(2);
    expect(forceGraphProps.nodeCanvasObjectMode({})).toBe("replace");
    expect(forceGraphProps.linkCanvasObjectMode({})).toBe("after");
    expect(typeof forceGraphProps.linkCanvasObject).toBe("function");

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
      { name: "Transport Subsidy", x: 100, y: 80, val: 1 },
      ctx,
      1,
    );

    expect(ctx.arc).toHaveBeenCalledWith(expect.any(Number), expect.any(Number), 4, 0, Math.PI * 2);
    expect(textCalls.some((call) => call.text === "Transport Subsidy" && call.x > 100)).toBe(true);

    expect(screen.getAllByText("Policy").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Organization").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Planning Area").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Age Cohort").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Event").length).toBeGreaterThan(0);

    expect(container.firstElementChild?.className).toContain("lg:grid-cols-[0.92fr_1.08fr]");
  });

  it("filters the graph by family and node type without changing the layout shell", async () => {
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

    await screen.findByText("Transport Subsidy");
    expect(screen.getByTestId("graph-node-count")).toHaveTextContent("5");

    fireEvent.click(screen.getByRole("button", { name: "Facet" }));
    expect(screen.getByTestId("graph-node-count")).toHaveTextContent("2");

    fireEvent.click(screen.getByRole("button", { name: "Planning Area" }));
    expect(screen.getByTestId("graph-node-count")).toHaveTextContent("1");
    expect(screen.getByText("Woodlands")).toBeInTheDocument();
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
