import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SingaporeMap } from "@/components/SingaporeMap";
import { ThemeProvider } from "@/contexts/ThemeContext";

vi.mock("react-leaflet", () => ({
  MapContainer: ({ children }: { children: ReactNode }) => <div data-testid="map-container">{children}</div>,
  TileLayer: () => null,
  GeoJSON: () => null,
  Tooltip: () => null,
}));

describe("SingaporeMap", () => {
  const originalFetch = global.fetch;
  const originalBaseUrl = import.meta.env.BASE_URL;

  function renderWithTheme(children: ReactNode) {
    return render(<ThemeProvider>{children}</ThemeProvider>);
  }

  it("fetches the Singapore planning-area geojson by default", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ type: "FeatureCollection", features: [] }),
    }) as typeof fetch;

    renderWithTheme(<SingaporeMap areaData={[]} />);

    expect(await screen.findByTestId("map-container")).toBeInTheDocument();
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(`${originalBaseUrl}maps/singapore_planning_areas.geojson`);
    });
  });

  it("fetches the USA state geojson when requested", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ type: "FeatureCollection", features: [] }),
    }) as typeof fetch;

    renderWithTheme(<SingaporeMap country="usa" areaData={[]} />);

    expect(await screen.findByTestId("map-container")).toBeInTheDocument();
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(`${originalBaseUrl}maps/usa_states.geojson`);
    });
  });

  afterEach(() => {
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });
});
