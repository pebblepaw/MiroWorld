import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SingaporeMap } from "@/components/SingaporeMap";

vi.mock("react-leaflet", () => ({
  MapContainer: ({ children }: { children: ReactNode }) => <div data-testid="map-container">{children}</div>,
  TileLayer: () => null,
  GeoJSON: () => null,
  Tooltip: () => null,
}));

describe("SingaporeMap", () => {
  const originalFetch = global.fetch;

  it("fetches the Singapore planning-area geojson by default", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ type: "FeatureCollection", features: [] }),
    }) as typeof fetch;

    render(<SingaporeMap areaData={[]} />);

    expect(await screen.findByTestId("map-container")).toBeInTheDocument();
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith("/maps/singapore_planning_areas.geojson");
    });
  });

  it("fetches the USA state geojson when requested", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ type: "FeatureCollection", features: [] }),
    }) as typeof fetch;

    render(<SingaporeMap country="usa" areaData={[]} />);

    expect(await screen.findByTestId("map-container")).toBeInTheDocument();
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith("/maps/usa_states.geojson");
    });
  });

  afterEach(() => {
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });
});
