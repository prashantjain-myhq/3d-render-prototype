# Data Pipeline — How to Add a New Tech Park

## Overview

Adding a new tech park requires data from 3 sources:

| Source | Who Provides | What | Format |
|--------|-------------|------|--------|
| Sales Team CSV | Sales/BD team | Building-level specs (18 fields) | `sales-team-template.csv` |
| CRE Matrix Export | Judha | Floor-level transaction data (35 columns) | Standard CRE dump |
| City View Data | Prashant | Park/landmark coordinates | `city-view-data-template.csv` |

## Step-by-Step

### Step 1: Sales Team fills `sales-team-template.csv`
- One row per building in the tech park
- Required fields: Name, Floors, Area, Year, Grade, CAM, Power, Parking, Efficiency, Amenities, Micro-market, Address
- Optional but valuable: Capital Value, Certification, Avg Rent

### Step 2: Judha exports CRE Matrix transactions
- Export ALL transactions for the tech park (historical + active)
- Standard CRE Matrix export with `dt-` prefixed columns
- One row per transaction (a floor may have multiple rows for different lease periods)
- See `field-mapping.csv` for the 35 columns we use

### Step 3: Place files in `tools/` folder
```
tools/
  new-park-buildings.csv     ← Sales team CSV
  new-park-cre-matrix.csv    ← CRE Matrix export
```

### Step 4: Run enrichment script
```bash
python3 tools/enrich-data.py \
  --buildings tools/new-park-buildings.csv \
  --cre tools/new-park-cre-matrix.csv \
  --output prototype/new-park-data.js \
  --park-name "New Park Name"
```

### Step 5: Add city view coordinates
- Get lat/lng from Google Maps (right-click → copy coordinates)
- Add park entry to the city parks data in the output JS file
- Add landmark entries if needed

### Step 6: Wire up in `index.html`
- Add `<script src="new-park-data.js"></script>` 
- Add city config entry in the `cityConfigs` object
- Add city option in the switcher dropdown

## Field Mapping Reference
See `field-mapping.csv` for the complete mapping between:
- Our prototype fields ↔ Sales team CSV columns ↔ CRE Matrix column names
- Which fields are required vs optional
- Which fields are auto-derived by the script

## Data Quality Rules
- CRE Matrix is the source of truth for all floor-level data
- Sales team CSV is ONLY for building-level specs
- If CRE says a floor has an active tenant but CSV says Vacant → CRE wins (auto-flagged as `dataConflict`)
- Vacant floors: occupancy=0, no rent/escalation/deposit shown in UI
- Multi-tenant floors: script groups all CRE transactions for same floor into `tenants[]` array

## Troubleshooting
- **Missing CRE data for a floor**: Floor shows with sales team data only, no deal intel
- **Duplicate tenants**: Script uses fuzzy matching (strips Pvt, Ltd, Private, Limited, India)
- **Occupancy >100%**: Script normalizes multi-tenant occupancy to sum to 100%
- **Wrong floor mapping**: Check `dt-floor` column in CRE export matches building floor numbering
