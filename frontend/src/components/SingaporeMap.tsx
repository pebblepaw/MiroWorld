import { useEffect, useState, useMemo } from 'react';
import { MapContainer, TileLayer, GeoJSON, Tooltip } from 'react-leaflet';
import type { FeatureCollection, Geometry, Feature } from 'geojson';
import 'leaflet/dist/leaflet.css';

interface SingaporeMapProps {
  areaData: Array<{ name: string; count: number }>;
}

export function SingaporeMap({ areaData }: SingaporeMapProps) {
  const [geoData, setGeoData] = useState<FeatureCollection | null>(null);

  useEffect(() => {
    fetch('/maps/singapore_planning_areas.geojson')
      .then((res) => res.json())
      .then((data) => setGeoData(data))
      .catch((err) => console.error('Failed to load Singapore GeoJSON:', err));
  }, []);

  const dataMap = useMemo(() => {
    const map = new Map<string, number>();
    areaData.forEach((row) => {
      map.set(row.name.toUpperCase(), row.count);
    });
    return map;
  }, [areaData]);

  const maxCount = useMemo(() => {
    return Math.max(1, ...areaData.map((d) => d.count));
  }, [areaData]);

  if (!geoData) {
    return (
      <div className="w-full h-[160px] flex items-center justify-center bg-white/[0.02] rounded-md">
        <span className="text-xs text-muted-foreground animate-pulse">Loading Map Data...</span>
      </div>
    );
  }

  // Calculate style based on density
  const getStyle = (feature?: Feature<Geometry, any>) => {
    const name = feature?.properties?.name?.toUpperCase() || '';
    const rawName = name.replace(/ /g, '_');
    
    // We try to match exactly, or with spaces replaced by underscores
    let count = dataMap.get(name) || dataMap.get(rawName) || 0;
    
    // If no exact match, try partial match (e.g. "JURONG_WEST" vs "JURONG WEST")
    if (count === 0) {
      for (const [key, val] of dataMap.entries()) {
        if (key.includes(name) || name.includes(key)) {
          count = val;
          break;
        }
      }
    }

    const intensity = count > 0 ? 0.3 + (count / maxCount) * 0.7 : 0.05;
    
    return {
      fillColor: count > 0 ? `hsl(38, 92%, ${15 + intensity * 40}%)` : 'hsl(215, 20%, 30%)',
      weight: 1,
      opacity: 0.6,
      color: 'rgba(255,255,255,0.1)',
      fillOpacity: intensity > 0.1 ? 0.8 : 0.1,
    };
  };

  return (
    <div className="w-full h-[160px] rounded-md overflow-hidden bg-[#0A0A0A] relative isolate">
      <MapContainer
        center={[1.3521, 103.8198]} // Singapore center
        zoom={10}
        zoomControl={false}
        scrollWheelZoom={false}
        dragging={true}
        doubleClickZoom={false}
        attributionControl={false}
        className="w-full h-full z-0"
        style={{ background: '#0A0A0A' }}
      >
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          opacity={0.6}
        />
        <GeoJSON
          data={geoData}
          style={getStyle}
          onEachFeature={(feature, layer) => {
            const name = feature.properties?.name || '';
            const key = name.toUpperCase();
            
            // Try to resolve matching agent count
            let count = dataMap.get(key) || dataMap.get(key.replace(/ /g, '_')) || 0;
            if (count === 0) {
              for (const [k, v] of dataMap.entries()) {
                if (k.includes(key) || key.includes(k)) {
                  count = v;
                  break;
                }
              }
            }

            layer.bindTooltip(
              `<div style="background: hsl(225,40%,8%); border: 1px solid hsl(225,20%,18%); border-radius: 6px; padding: 6px 10px; color: hsl(210,40%,93%); font-family: Inter, sans-serif; font-size: 11px;">
                <div style="font-weight: 600; margin-bottom: 2px;">${name.replace(/_/g, ' ')}</div>
                <div style="color: hsl(38, 92%, 50%);">${count} Agents</div>
              </div>`,
              { sticky: true, className: 'custom-leaflet-tooltip' }
            );
          }}
        />
      </MapContainer>
      
      {/* Custom styles to override leaflet tooltip default white background */}
      <style>{`
        .custom-leaflet-tooltip {
          background: transparent !important;
          border: none !important;
          box-shadow: none !important;
          padding: 0 !important;
        }
        .custom-leaflet-tooltip::before {
          display: none !important;
        }
      `}</style>
    </div>
  );
}
