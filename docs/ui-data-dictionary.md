# UI Data Dictionary — Every Visible Number and Its Source

## How to Read This Document

Each entry follows this format:
- **Where**: Which panel/view shows this
- **Label**: What the user sees
- **Calculation**: Exact formula
- **Source**: Where the input data comes from
- **Code**: Where in index.html it's computed (approximate line)

---

## City View (Mapbox Map)

### Park Cards

| Label | Calculation | Source |
|-------|------------|--------|
| Park Name | Direct display | `CITY_PARKS_DATA.parks[].name` — hardcoded in data.js/gurgaon-data.js |
| Sub-location | Direct display | `parks[].subLocation` — hardcoded |
| Buildings count | Direct display | `parks[].buildings` — hardcoded |
| Total Area | Direct display | `parks[].totalArea` — hardcoded (e.g. "15.5L sqft") |
| Avg Rent Range | Direct display | `parks[].avgRent` — hardcoded (e.g. "₹57-90/sqft") |

### Distance Labels

| Label | Calculation | Source |
|-------|------------|--------|
| X.X km | Haversine distance between two lat/lng points | `haversineKm(centerPark.lat, centerPark.lng, park.lat, park.lng)` — coordinates from data files |

### Landmark Tooltips

| Label | Calculation | Source |
|-------|------------|--------|
| Distance | Same haversine formula | Lat/lng from `CITY_PARKS_DATA.landmarks[]` |
| Info text | Direct display | `landmarks[].info` — hardcoded |

---

## Park View — Building Panel (Panel 1)

### Header

| Label | Calculation | Source |
|-------|------------|--------|
| Building Name | Direct display | `building.name` — from enrich-data.py config |
| Subtitle (year, floors, area) | `yearBuilt · totalFloors floors · totalArea/1000 K sqft` | Sales team CSV via enrichment script |
| Grade badge | Direct display | `building.grade` — from CRE Matrix `dt-grade` (first transaction for building). Falls back to config if CRE empty |
| Building Category badge | Direct display | `building.buildingCategory` — from CRE Matrix `dt-building-category` |
| Developer badge | Direct display | `building.developer` — from CRE Matrix `dt-developer` |
| Micro-market badge | Direct display | `building.microMarketCRE` or `building.microMarket` — CRE Matrix `dt-micro-market`, falls back to config |

### Stats Grid

| Label | Calculation | Source |
|-------|------------|--------|
| Occupancy | `avg(all floors occupancy) rounded` | Each floor's `occupancy` from CRE Matrix (0 for vacant, derived from active lease status) |
| Avg Rent | `avg(effectiveRent or rentPerSqft) for occupied floors only` | `effectiveRent` from CRE `dt-effective-rent`. Falls back to `rentPerSqft` from `dt-current-rent-chargeable`. Excludes vacant floors (occupancy=0) |
| CAM | Direct display | `building.camCharges` — from Sales team CSV |
| Parking | Direct display | `building.parkingRatio` — from config (hardcoded) |
| Efficiency | Direct display | `building.efficiencyRatio` — from Sales team CSV or config |
| Escalation | Direct display | `building.escalation` — from Sales team CSV (text like "15% every 3 years") |
| Power | Direct display | `building.powerBackup` — from Sales team CSV |
| Yield | `avg(all floors rentalYield)` | Only shown when `capitalValuePerSqft > 0`. Hidden for Gurgaon. |

### Market Context

| Label | Calculation | Source |
|-------|------------|--------|
| Market Avg Rent | `avg(effectiveRent or currentRent) across ALL CRE transactions in same dt-micro-market` | Calculated in enrich-data.py from all transactions matching the building's micro-market. Was hardcoded ₹80, now ₹83 from real CRE data |

---

## Park View — Building Panel (Panel 2)

### Sector Mix

| Label | Calculation | Source |
|-------|------------|--------|
| Sector name | Grouped from floor tenants | CRE Matrix `dt-sector` on each transaction |
| Percentage | `sector_area / total_occupied_area × 100` | Aggregated in enrich-data.py `build_sector_mix()` from all transactions for this building |

### Deal Flow Chart

| Label | Calculation | Source |
|-------|------------|--------|
| Year | Direct display | Aggregated from CRE transaction `dt-commencement-date` years |
| Deals count | Count of transactions in that year for this building | `build_deal_history()` in enrich-data.py |
| New deals | Transactions where `dt-newrenewal` = "New" | CRE Matrix |
| Renewals | Transactions where `dt-newrenewal` = "Renewal" | CRE Matrix |
| Avg Rent | `avg(dt-current-rent-chargeable)` for deals in that year | CRE Matrix |

### Lease Expiry Alert

| Label | Calculation | Source |
|-------|------------|--------|
| X floors expired | Count where `leaseExpiryDate < today` | `leaseExpiryDate` from CRE `dt-lease-expiry-date` |
| X floors expiring <6mo | Count where `0 < months_until_expiry <= 6` | Same source |
| X floors expiring 6-12mo | Count where `6 < months_until_expiry <= 12` | Same source |

---

## Park View — Floor Cards (Panel 3)

### Floor Card Header (collapsed)

| Label | Calculation | Source |
|-------|------------|--------|
| Floor number | Direct display | `floor.floor` — from CRE/CSV floor numbering |
| Tenant name | Direct display, title-cased | `floor.tenant` — from CRE `dt-tenant-parent-entity--brand`. Multi-tenant shows "Name + X more" |
| Occupancy pill | Direct display | `floor.occupancy` — 0 for vacant, derived from CRE active lease status |
| Rent pill (occupied) | `effectiveRent` or `rentPerSqft` | CRE `dt-effective-rent` or `dt-current-rent-chargeable` |
| Est. Rent pill (vacant) | Building avg effective rent | Calculated in enrich-data.py: `avg(effectiveRent or rentPerSqft)` across occupied floors in same building. Flagged as `rentEstimated: true` |
| Sector pill | Direct display | CRE `dt-sector`. Hidden for vacant floors |
| Condition pill | Direct display | CRE `dt-property-condition` (Bare Shell / Warm Shell / Fitted Out) |
| Expiry pill | Months until `leaseExpiryDate` | CRE `dt-lease-expiry-date`. Shows "Expired", "Exp Mon YYYY", or hidden if >12mo |
| Deal Type badge | Direct display | CRE `dt-newrenewal` (New / Renewal). Hidden for vacant |

### Overview Tab

| Label | Calculation | Source |
|-------|------------|--------|
| Tenant | Direct display | CRE `dt-tenant-parent-entity--brand` |
| Carpet Area | `area × efficiencyRatio / 100` | Area from CRE `dt-chargeable-area`, efficiency from CRE `dt-efficiency` or config |
| Super Built-up | Direct display | CRE `dt-chargeable-area` |
| Fit-out | Direct display | CRE `dt-property-condition` |
| Lock-in | Direct display + formatted end date | CRE `dt-lockin-period` and `dt-lockin-expiry-date` |
| Lease Period | `fmtDate(leaseStart) to fmtDate(leaseEnd)` | CRE `dt-commencement-date` and lease end |
| Move-in Date | Direct display | CRE `dt-absorption-date` (when available) |

### Tenants Tab (multi-tenant floors only)

| Label | Calculation | Source |
|-------|------------|--------|
| Per-tenant cards | Each tenant from `floor.tenants[]` array | Grouped from all CRE transactions on same floor in enrich-data.py |
| Tenant occupancy % | From CRE transaction area / total floor area, normalized to 100% | enrich-data.py normalizes when sum > 100% |
| Per-tenant rent, escalation, expiry | Direct from each tenant's CRE transaction | Individual CRE `dt-*` fields per transaction |

### Financial Tab

| Label | Calculation | Source |
|-------|------------|--------|
| Rent/sqft | Direct display | CRE `dt-current-rent-chargeable` |
| Effective Rent | Direct display | CRE `dt-effective-rent` |
| Est. Rent (vacant) | Building avg effective rent | Calculated in enrich-data.py (see above). Labeled "(bldg avg)" |
| Monthly Revenue | `(effectiveRent or rentPerSqft) × carpetArea` | Calculated in enrich-data.py. 0 for vacant |
| Annual Revenue | `monthlyRevenue × 12` | Calculated in enrich-data.py |
| Security Deposit | Direct display (months) | CRE `dt-security-deposit` |
| CAM Charges | Direct display | Building-level from Sales team CSV |
| Escalation | `rentEscalation% every escalationPeriod months` | CRE `dt-rent-escalation` and `dt-first-rent-escalation-period`. Only shown for occupied floors |
| Property Tax | Direct display (who pays) | CRE `dt-property-tax-payer` (when available) |
| Carpet Rent | Direct display | CRE `dt-current-rent-carpet` (when available) |
| Rent Progression | `startingRent → effectiveRent → leaseExpiryRent` | CRE `dt-starting-rent-chargeable`, `dt-effective-rent`, `dt-lease-expiry-rent-chargeable` |

### Deal Intel Tab

| Label | Calculation | Source |
|-------|------------|--------|
| Landlord | Direct display | CRE `dt-landlord` |
| Landlord Contact | Direct display | CRE `dt-landlord-representative` |
| Deal Memo | Direct display | CRE `dt-deal-memo` |
| Agreement Type | Direct display | CRE `dt-agreement-type` |
| All Landlords | Unique list from all transactions on this floor | Aggregated in enrich-data.py `find_all_landlords()` |
| Multi-tenant disclaimer | Shown when `tenants.length > 1` | — |

### History Tab

| Label | Calculation | Source |
|-------|------------|--------|
| Transaction cards | Each entry from `floor.floorDealHistory[]` | All CRE transactions matching this building+floor, sorted by date desc |
| Date | `dt-commencement-date` formatted as Mon YYYY | CRE Matrix |
| Tenant | `dt-tenant-parent-entity--brand` | CRE Matrix |
| Deal Type badge | `dt-newrenewal` | CRE Matrix |
| Rent | `dt-starting-rent-chargeable` | CRE Matrix |
| Area | `dt-chargeable-area` | CRE Matrix |
| Sector | `dt-sector` | CRE Matrix |

---

## Compare Modal

### Floor Comparison Cards

| Label | Calculation | Source |
|-------|------------|--------|
| All floor fields | Same as floor card (rent, occupancy, sector, etc.) | Same sources as above |

### Cost of Occupancy Table

| Label | Calculation | Source |
|-------|------------|--------|
| Monthly Rent | `(effectiveRent or rentPerSqft) × carpetArea` | CRE rent × floor area. 0 for vacant |
| Monthly CAM | `building.camCharges × carpetArea` | Sales team CAM × floor area |
| Monthly Total | `Monthly Rent + Monthly CAM` | Derived |
| Security Deposit | `floor.securityDeposit × Monthly Rent` | CRE deposit months × monthly rent. Null for vacant |
| Escalation | `rentEscalation% / escalationPeriod mo` | CRE `dt-rent-escalation` + `dt-first-rent-escalation-period`. Only when both exist. No defaults used |
| Annual Cost (Yr 1) | `Monthly Total × 12` | Derived |

**Removed (were assumptions, not data):**
- Fit-out Estimate (was ₹2500/sqft assumed)
- 5-Year Total Cost (used assumed escalation defaults)
- Upfront Total (included assumed fit-out)

---

## Park Overview Panel (press P)

| Label | Calculation | Source |
|-------|------------|--------|
| Total Occupancy | `avg(all floors occupancy)` | All floor occupancy values |
| Avg Eff. Rent | `avg(effectiveRent or rentPerSqft) for occupied floors` | CRE effective/asking rent, occupied only |
| Vacant Floors | Count where `occupancy === 0` | — |
| Vacant Area | `sum(carpetArea) for vacant floors` | — |
| Monthly Revenue | `sum(all floors monthlyRevenue)` | Derived from rent × area |
| Revenue at Risk | `sum(monthlyRevenue) for floors expiring in 12 months` | Floors where `leaseExpiryDate` is within 12 months of today |
| Sector Breakdown | `sector_area / total_occupied_area × 100` per sector | CRE `dt-sector` aggregated across all floors |
| Building Scoreboard | Per-building: avg occupancy, avg rent, floor count, vacant count | Same formulas as building panel, calculated per building |
| Top 5 Tenants | Sorted by total `carpetArea` across all floors | Grouped by tenant name from all floors |

---

## Deal Flow Time Slider (press T)

| Label | Calculation | Source |
|-------|------------|--------|
| Year | Slider value 2008-2025 | User-controlled |
| Deals | `sum(building.dealHistory[year].deals)` across all buildings | Aggregated from CRE transactions by year |
| Avg Rent | `weighted avg of dealHistory[year].avgRent` across buildings | CRE `dt-current-rent-chargeable` per year |
| New | `sum(dealHistory[year].newDeals)` | CRE `dt-newrenewal` = "New" |
| Renewed | `sum(dealHistory[year].renewals)` | CRE `dt-newrenewal` = "Renewal" |
| Floor colors | Green = active lease in that year, Red = expired, Grey = no data | Based on `floorDealHistory[].date` and `.expiry` compared to slider year |

---

## Heatmap Modes (keys 1-5)

| Mode | Key | Color Logic | Source |
|------|-----|-------------|--------|
| Occupancy | 1 | Red (0%) → Yellow (50%) → Green (100%) | `floor.occupancy` |
| Rent | 2 | Green (low) → Yellow (mid) → Red (high), relative to building | `floor.rentPerSqft` |
| Lease Expiry | 4 | Red (expired/< 6mo) → Yellow (6-12mo) → Green (>12mo) | `floor.leaseExpiryDate` vs today |
| Sector | 5 | Unique color per sector from preset palette | `floor.sector` mapped to `sectorHeatColors` |
| Reset | 0 | Original building phase colors | `originalMaterialColors` stored at creation |

---

## Data Conflict Banner

| Label | Calculation | Source |
|-------|------------|--------|
| Warning text | Direct display from `floor.dataConflict` | Set in enrich-data.py `detect_vacancy_conflict()` when Sales CSV says Vacant but CRE has active lease with `leaseExpiryDate > today` |

---

## What Is NOT From Real Data (Assumptions/Hardcoded)

| Item | Current Value | Why |
|------|--------------|-----|
| Building positions (x, z) | Hand-tuned via visual editor | No geospatial conversion — placed on satellite by eye |
| Building dimensions (width, depth, height) | Measured from satellite + adjusted | Approximate, not surveyed |
| Building colors | Preset palette per building | Design choice |
| Building shapes (box, L, podium) | Set in config | Approximate match to satellite footprint |
| Amenities list | From broker sites | Sales team should provide actual list |
| Capital Value (Unitech) | 0 (unknown) | Sales team or broker needed |
| PTP floor data | Dummy with assumed enrichment | sector from tenant name mapping, effectiveRent = 92% of asking, escalation = 15%/36mo |
