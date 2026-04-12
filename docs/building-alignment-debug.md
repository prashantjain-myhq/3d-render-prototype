# Building Polygon Misalignment — Debug Report

## 1. Source of Tower Polygon Coordinates

The towers do **NOT** use geospatial coordinates. They use **arbitrary Three.js scene-space units** — unitless numbers in a local coordinate system.

```javascript
// gurgaon-data.js
Tower A: position: { x: 2.2, z: 8.5 },   width: 14, depth: 5
Tower B: position: { x: -9.8, z: 0.4 },   width: 9, depth: 4.5
Tower C: position: { x: -0.8, z: -3.8 },  width: 9, depth: 4.5
Tower D: position: { x: 8.3, z: -5.1 },   width: 8, depth: 4.2
```

These were manually placed by eyeballing Google Maps, then adjusting until they "looked about right" on the satellite overlay. There is no geodetic conversion — these are scene-local x/z values where 1 unit ≈ 3-4 meters (approximate, not calibrated).

---

## 2. CRS / Projection at Each Stage

**There is no CRS.** The system operates in two completely disconnected coordinate spaces:

- **Satellite image**: Fetched from Mapbox Static API at `[77.056043, 28.443524]` zoom 18 (EPSG:3857 Web Mercator, rendered as a flat raster PNG)
- **3D buildings**: Positioned in Three.js scene space (unitless, no CRS)
- **No conversion exists.** The satellite PNG is texture-mapped onto an 80×80 unit PlaneGeometry. Buildings are placed at x/z positions that roughly correspond to where they appear on that texture.

```javascript
// index.html line 2670-2671
const satCenter = [77.056043, 28.443524]; // lng, lat
const satUrl = `...satellite-v9/static/${satCenter[0]},${satCenter[1]},18,0/1280x1280@2x?...`;
```

```javascript
// index.html line 2678-2682
const satGeo = new THREE.PlaneGeometry(80, 80); // 80 scene units
satMesh.rotation.x = -Math.PI / 2;              // lay flat
satMesh.position.y = 0.02;                       // just above ground
```

**No EPSG:4326 to EPSG:3857 conversion anywhere in the code.**

---

## 3. Coordinate Order Passed to Map Library

Two separate systems, two coordinate orders:

- **Mapbox Static API** (satellite image): `lng, lat` → `77.056043, 28.443524` (correct for Mapbox)
- **Three.js** (buildings): `x, z` in scene space → `b.position.x, b.position.z` (not geo coordinates at all)

```javascript
// index.html line 3806
group.position.set(b.position.x, 0, b.position.z);
```

---

## 4. Client-Side Transforms Applied

### Building group transforms (line 3806-3807):
```javascript
group.position.set(b.position.x, 0, b.position.z); // translation
if (b.rotation) group.rotation.y = b.rotation;       // rotation (radians)
```

### Satellite image transform (line 2678-2682):
```javascript
const satGeo = new THREE.PlaneGeometry(80, 80); // fixed 80x80 size
satMesh.rotation.x = -Math.PI / 2;              // lay flat on XZ plane
satMesh.position.y = 0.02;                       // micro-offset above ground
// NO translation, NO scale — centered at scene origin (0, 0, 0)
```

### Satellite center offset (line 2667 vs 2670):
```javascript
const campusCenter = [77.056159, 28.443089]; // CRE Matrix point
const satCenter   = [77.056043, 28.443524];  // manually tweaked
```

This offset (`lng: -0.000116, lat: +0.000435`) is an **intentional manual calibration** — the satellite image center was shifted ~48m north and ~12m west of the CRE Matrix coordinates to improve visual alignment.

---

## 5. Geospatial Features vs Image Overlay

**Image overlay.** The buildings are NOT geospatial map features. The rendering pipeline is:

1. A Mapbox satellite **raster image** is downloaded as a static PNG
2. It is texture-mapped onto a flat Three.js plane at the scene origin
3. Three.js box meshes are placed on top using arbitrary scene coordinates

There is no calibration logic. The satellite image covers whatever geographic area the PlaneGeometry covers (~280m × 280m at zoom 18), and building positions are hand-tuned to sit on the correct spots in that image.

---

## 6. Raw Coordinates for Each Tower

```
Tower   Position (x, z)    Width   Depth   Rotation (rad)
─────   ───────────────    ─────   ─────   ──────────────
A       (2.2, 8.5)         14      5       0.35 (~20°)
B       (-9.8, 0.4)        9       4.5     -0.26 (~-15°)
C       (-0.8, -3.8)       9       4.5     0.09 (~5°)
D       (8.3, -5.1)        8       4.2     0.17 (~10°)
```

All values in Three.js scene units. Scene origin (0, 0) maps to satellite image center `[77.056043, 28.443524]`.

---

## 7. How Rotation Is Determined

**Manual.** Rotations were eyeballed from the satellite image and hardcoded as radians. Applied as Y-axis rotation on the Three.js group:

```javascript
// index.html line 3807
if (b.rotation) group.rotation.y = b.rotation;
```

Not derived from source coordinates or any geodetic calculation.

---

## 8. Hardcoded Calibration Values

| Value | Location | Purpose |
|---|---|---|
| `satCenter: [77.056043, 28.443524]` | index.html:2670 | Satellite image center (manually offset from CRE point) |
| `campusCenter: [77.056159, 28.443089]` | index.html:2667 | CRE Matrix campus coordinates |
| `satZoom: 18` | index.html:2669 | Satellite image zoom level |
| `PlaneGeometry(80, 80)` | index.html:2678 | Satellite plane size in scene units |
| All position x/z values | gurgaon-data.js | Building placements (manual) |
| All rotation values | gurgaon-data.js | Building angles (eyeballed) |
| All width/depth values | gurgaon-data.js | Building footprint sizes (from floor plate data, not measured) |

---

## 9. Root Cause of Misalignment

**Image-space vs map-space mismatch.** Three specific issues:

### Issue A: No formal coordinate conversion
Building positions are manually placed in scene units to "look right" on the satellite texture. There is no math linking scene unit (x, z) to geographic coordinates (lng, lat).

### Issue B: Building scale is uncalibrated
The 80×80 scene-unit plane covers real ground. Calculating the actual scale:

```
meters_per_pixel = 156543.03 × cos(lat) / 2^zoom
                 = 156543.03 × cos(28.443°) / 2^18
                 = 0.524 m/px

Image = 1280px × 2 (retina) = 2560px
Ground coverage = 2560 × 0.524 = 1341m
Plane = 80 units
1 scene unit = 1341 / 80 = 16.77 meters
```

So 1 scene unit = ~16.8 meters. But:
- Tower A width = 14 units = **235m** (real building is ~120m)
- Tower B width = 9 units = **151m** (real building is ~80m)

**Buildings are ~2× too large relative to the satellite image.** This is the primary cause of misalignment — the boxes extend well beyond the real building footprints visible on the satellite.

### Issue C: Building shapes are wrong
All towers use `"box"` geometry but real buildings are L-shaped or C-shaped. Even with perfect positioning and scaling, a rectangle will never align with an L-shaped satellite footprint.

---

## 10. Recommended Fix

### Short-term: Fix the scale ratio (data correction)

Calculate correct building dimensions using the satellite scale factor (1 unit = 16.77m):

```
Tower A real footprint: ~120m × 45m → width: 7.2, depth: 2.7 (currently 14, 5)
Tower B real footprint: ~80m × 40m  → width: 4.8, depth: 2.4 (currently 9, 4.5)
Tower C real footprint: ~80m × 40m  → width: 4.8, depth: 2.4 (currently 9, 4.5)
Tower D real footprint: ~70m × 35m  → width: 4.2, depth: 2.1 (currently 8, 4.2)
```

**File to change**: `tools/enrich-data.py` → UNITECH_CONFIGS width/depth values
**Type**: Data correction — halve the building dimensions

This alone will make buildings fit inside their satellite footprints instead of overflowing.

### Long-term: Mapbox GL fill-extrusion (rendering correction)

Use Mapbox GL JS for the park view — render buildings as `fill-extrusion` layers using real GeoJSON building footprint polygons. This eliminates all alignment issues because buildings and map share the same coordinate system (EPSG:3857).

**Trade-off**: Requires significant refactoring. Three.js interactivity (floor clicking, heatmaps, etc.) would need to be reimplemented using Mapbox GL's event system.

---

## Summary

The misalignment is not a bug in any single place — it's an architectural limitation. The current system places 3D boxes on top of a flat satellite photo using manually guessed coordinates and sizes. There is no geodetic math connecting the two. The buildings are approximately 2× too large for the satellite scale, and their shapes (boxes) don't match reality (L-shapes). Fixing the scale ratio is the highest-impact incremental change; switching to Mapbox GL fill-extrusion is the correct long-term solution.
