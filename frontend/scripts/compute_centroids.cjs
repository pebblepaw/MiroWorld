const fs = require('fs');
const path = require('path');

const geojsonPath = path.join(__dirname, '../public/maps/singapore_planning_areas.geojson');
const outPath = path.join(__dirname, '../public/maps/centroids.json');

const data = JSON.parse(fs.readFileSync(geojsonPath, 'utf8'));

const centroids = {};

data.features.forEach((feature) => {
  const name = feature.properties.name.toUpperCase();
  
  let minLon = Infinity;
  let maxLon = -Infinity;
  let minLat = Infinity;
  let maxLat = -Infinity;
  
  const extractCoords = (coords) => {
    if (typeof coords[0] === 'number') {
      const [lon, lat] = coords;
      if (lon < minLon) minLon = lon;
      if (lon > maxLon) maxLon = lon;
      if (lat < minLat) minLat = lat;
      if (lat > maxLat) maxLat = lat;
    } else {
      coords.forEach(extractCoords);
    }
  };
  
  if (feature.geometry && feature.geometry.coordinates) {
    extractCoords(feature.geometry.coordinates);
    const centerLon = (minLon + maxLon) / 2;
    const centerLat = (minLat + maxLat) / 2;
    centroids[name] = [centerLat, centerLon];
  }
});

fs.writeFileSync(outPath, JSON.stringify(centroids, null, 2));
console.log('Centroids computed successfully:', Object.keys(centroids).length, 'areas');
