import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { forwardRef } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import PolicyUpload from "@/pages/PolicyUpload";
import { AppProvider } from "@/contexts/AppContext";

vi.mock("react-force-graph-2d", () => ({
  default: forwardRef(({ graphData }: { graphData: { nodes: Array<{ name?: string }>; links: Array<unknown> } }, _ref) => (
    <div data-testid="graph-canvas">
      <span data-testid="graph-node-count">{graphData.nodes.length}</span>
      <span data-testid="graph-link-count">{graphData.links.length}</span>
      {graphData.nodes.map((node) => (
        <span key={node.name}>{node.name}</span>
      ))}
    </div>
  )),
}));

describe("PolicyUpload", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
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
          { id: "policy:transport", label: "Transport Subsidy", type: "policy", description: "Fare support", weight: 0.8 },
          { id: "group:seniors", label: "Seniors", type: "demographic", description: "Older households", weight: 0.6 },
        ],
        relationship_edges: [
          { source: "policy:transport", target: "group:seniors", type: "targets", label: "targets" },
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
    expect(screen.getByTestId("graph-node-count")).toHaveTextContent("2");
    expect(screen.getByTestId("graph-link-count")).toHaveTextContent("1");
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
