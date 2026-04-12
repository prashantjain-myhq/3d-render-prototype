#!/usr/bin/env python3
"""
Enrich gurgaon-data.js with CREMatrix transaction data + PTP CSV fixes.
Reads 3 CSVs from Downloads, merges with existing prototype data, outputs enriched JS.
"""

import csv
import json
import re
from collections import defaultdict
from datetime import datetime

# --- File paths ---
DOWNLOADS = "/Users/prashantjain/Downloads"
BUILDING_CSV = f"{DOWNLOADS}/Copy of PTP Data Template - Building.csv"
FLOOR_CSV = f"{DOWNLOADS}/Copy of PTP Data Template - Floor.csv"
TRANSACTIONS_CSV = f"{DOWNLOADS}/Copy of PTP Data Template - transactions.csv"
OUTPUT_JS = "/Users/prashantjain/Desktop/Claude-code/prototype/gurgaon-data.js"

# --- Building name mapping: CREMatrix short names -> full CSV names ---
BUILDING_MAP = {
    "Tower A": "Unitech Cyber Park Tower A",
    "Tower B": "Unitech Cyber Park Tower B",
    "Tower C": "Unitech Cyber Park Tower C",
    "Tower D": "Unitech Cyber Park Tower D",
    "Block 1": "Vatika Business Park Building 1",
    "Block 2": "Vatika Business Park Building 2",
    "Block 3": "Vatika Business Park Building 3",
}

# Reverse map for JS output (full name -> short name for display)
BUILDING_SHORT = {v: k for k, v in BUILDING_MAP.items()}

# Park assignment
UNITECH_BUILDINGS = ["Tower A", "Tower B", "Tower C", "Tower D"]
VATIKA_BUILDINGS = ["Building 1", "Building 2", "Building 3"]


def parse_date_to_yyyymm(date_str):
    """Normalize various date formats to YYYY-MM."""
    if not date_str or date_str.strip() in ('', '-'):
        return None
    date_str = date_str.strip()

    # Try: "31-Dec-24" or "24-Jan-17"
    for fmt in ("%d-%b-%y", "%b-%y", "%d-%b-%Y", "%B-%y", "%Y-%m"):
        try:
            dt = datetime.strptime(date_str, fmt)
            # Fix 2-digit years: 00-29 -> 2000s, 30-99 -> 1900s (Python default)
            if dt.year < 100:
                dt = dt.replace(year=dt.year + 2000 if dt.year < 50 else dt.year + 1900)
            return dt.strftime("%Y-%m")
        except ValueError:
            continue

    # Try: "April-24" or "9-April-33"
    for fmt in ("%B-%y", "%d-%B-%y"):
        try:
            dt = datetime.strptime(date_str, fmt)
            if dt.year < 100:
                dt = dt.replace(year=dt.year + 2000 if dt.year < 50 else dt.year + 1900)
            return dt.strftime("%Y-%m")
        except ValueError:
            continue

    # Try CREMatrix format: "28-Feb-34", "31-May-34"
    for fmt in ("%d-%b-%y",):
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m")
        except ValueError:
            continue

    return None


def parse_number(val):
    """Parse number from string, removing commas."""
    if not val or val.strip() in ('', '-', 'NA', 'N/A'):
        return None
    val = val.strip().replace(',', '')
    # Remove 'psf' suffix from CAM charges
    val = re.sub(r'\s*psf\s*$', '', val, flags=re.IGNORECASE)
    try:
        return float(val)
    except ValueError:
        return None


def parse_int(val):
    """Parse integer from string."""
    n = parse_number(val)
    return int(n) if n is not None else None


# ============================================================
# STEP 1: Parse Building CSV
# ============================================================
def parse_buildings():
    buildings = {}
    with open(BUILDING_CSV, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get('Building Name', '').strip()
            if not name:
                continue
            buildings[name] = {
                'name': name,
                'basements': parse_int(row.get('Basement', '')),
                'totalFloors': parse_int(row.get('Total Floors', '')),
                'totalArea': parse_int(row.get('Total Area (sqft)', '')),
                'yearBuilt': parse_int(row.get('Year Built', '')),
                'grade': row.get('Grade', '').strip() or None,
                'certification': row.get('Certification', '').strip() or None,
                'camCharges': parse_number(row.get('CAM Charges (₹/sqft/mo)', '')),
                'escalation': row.get('Escalation', '').strip() or None,
                'powerBackup': row.get('Power Backup', '').strip() or None,
                'parkingRatio': row.get('Parking Ratio (per 1000 sqft)', '').strip() or None,
                'floorPlateSize': parse_int(row.get('Floor Plate Size (sqft)', '')),
                'efficiencyRatio': parse_number(row.get('Efficiency Ratio (%)', '')),
                'microMarketAvgRent': parse_number(row.get('Micro-market Avg Rent (₹/sqft)', '')),
            }
    return buildings


# ============================================================
# STEP 2: Parse Floor CSV
# ============================================================
def parse_floors():
    """Returns dict: building_name -> list of floor entries."""
    floors = defaultdict(list)
    with open(FLOOR_CSV, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            bldg = row.get('Building Name', '').strip()
            if not bldg:
                continue

            tenant = row.get('Tenant Name', '').strip()
            # Fix "Working" placeholder
            if tenant.lower() == 'working':
                tenant = 'Undisclosed Tenant'

            floor_num = row.get('Floor Number', '').strip()
            try:
                floor_num = int(floor_num)
            except ValueError:
                continue

            occupancy = parse_number(row.get('Occupancy (%)', ''))
            rent = parse_number(row.get('Rent (₹/sqft/mo)', ''))
            area = parse_int(row.get('Floor Area (Super Area) (sqft)', ''))
            lease_start = parse_date_to_yyyymm(row.get('Lease Start (YYYY-MM)', ''))
            lease_end = parse_date_to_yyyymm(row.get('Lease End (YYYY-MM)', ''))
            status = row.get('Status', '').strip()
            lock_in = row.get('Lock-in Period', '').strip() or None
            security_dep = parse_number(row.get('Security Deposit (months)', ''))

            floors[bldg].append({
                'building': bldg,
                'floor': floor_num,
                'tenant': tenant,
                'occupancy': occupancy,
                'rentPerSqft': rent,
                'area': area,
                'leaseStart': lease_start,
                'leaseEnd': lease_end,
                'status': status,
                'lockInPeriod': f"{int(parse_number(lock_in))} months" if lock_in and parse_number(lock_in) else lock_in,
                'securityDeposit': security_dep,
            })
    return floors


# ============================================================
# STEP 3: Parse CREMatrix Transactions
# ============================================================
def parse_transactions():
    """Returns list of transaction dicts and a lookup by building+floor."""
    transactions = []
    by_building_floor = defaultdict(list)

    with open(TRANSACTIONS_CSV, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            building_short = row.get('dt-building', '').strip()
            if not building_short:
                continue

            # Determine full building name from complex
            complex_name = row.get('class_complex_details', '').strip()
            if 'Unitech' in complex_name:
                full_building = f"Unitech Cyber Park {building_short}"
            elif 'Vatika' in complex_name:
                # CREMatrix uses "Block 1/2/3" but Floor.csv uses "Building 1/2/3"
                bldg_num = building_short.replace('Block ', '')
                full_building = f"Vatika Business Park Building {bldg_num}"
            else:
                full_building = building_short

            floor_str = row.get('dt-floor', '').strip()
            tenant_brand = row.get('dt-tenant-parent-entity--brand', '').strip()
            tenant_spv = row.get('dt-tenant-spv--subsidiary', '').strip()

            commencement = row.get('dt-commencement-date', '').strip()
            commencement_yyyymm = parse_date_to_yyyymm(commencement)

            txn = {
                'building': full_building,
                'buildingShort': building_short,
                'complex': complex_name,
                'floor': floor_str,
                'tenantBrand': tenant_brand,
                'tenantSPV': tenant_spv,
                'sector': row.get('dt-sector', '').strip() if row.get('dt-sector', '').strip() not in ('', '-') else None,
                'dealType': row.get('dt-newrenewal', '').strip() if row.get('dt-newrenewal', '').strip() not in ('', '-') else None,
                'landlord': row.get('dt-landlord', '').strip() or None,
                'landlordContact': row.get('dt-landlord-representative', '').strip() or None,
                'landlordLinkedIn': row.get('dt-landlord-profile href', '').strip() or None,
                'tenantContact': row.get('dt-tenant-representative', '').strip() or None,
                'tenantLinkedIn': row.get('dt-tenant-profile href', '').strip() or None,
                'agreementType': row.get('dt-agreement-type', '').strip() or None,
                'propertyCondition': row.get('dt-property-condition', '').strip() or None,
                'chargeableArea': parse_int(row.get('dt-chargeable-area', '')),
                'carpetArea': parse_int(row.get('dt-carpet-area', '')),
                'efficiency': parse_number(row.get('dt-efficiency', '')),
                'startingRent': parse_number(row.get('dt-starting-rent-chargeable', '')),
                'currentRent': parse_number(row.get('dt-current-rent-chargeable', '')),
                'effectiveRent': parse_number(row.get('dt-effective-rent', '')),
                'leaseExpiryRent': parse_number(row.get('dt-lease-expiry-rent-chargeable', '')),
                'leaseTerm': parse_int(row.get('dt-lease-term', '')),
                'leaseExpiryDate': parse_date_to_yyyymm(row.get('dt-lease-expiry-date', '')),
                'rentFreePeriod': row.get('dt-rent-free-period', '').strip() or None,
                'lockInPeriod': parse_int(row.get('dt-lockin-period', '')),
                'lockInExpiryDate': parse_date_to_yyyymm(row.get('dt-lockin-expiry-date', '')),
                'noticePeriod': row.get('dt-notice-period', '').strip() or None,
                'freeCarParks': parse_int(row.get('dt-free-car-parks', '')),
                'paidCarParks': parse_int(row.get('dt-paid-car-parks', '')),
                'carParkingCharges': parse_number(row.get('dt-car-parking-charges', '')),
                'rentEscalation': parse_number(row.get('dt-rent-escalation', '')),
                'escalationPeriod': parse_int(row.get('dt-first-rent-escalation-period', '')),
                'nextEscalationDue': parse_int(row.get('dt-next-rent-escalation-due', '')),
                'camPayer': row.get('dt-cam-payer', '').strip() or None,
                'camCharges': row.get('dt-cam-charges', '').strip() or None,
                'securityDeposit': parse_int(row.get('dt-security-deposit', '')),
                'dealMemo': row.get('dt-deal-memo', '').strip() if row.get('dt-deal-memo', '').strip() not in ('', '-', 'CAM Charges Not Given.') else None,
                'commencementDate': commencement_yyyymm,
                'commencementRaw': commencement,
                'grade': row.get('dt-grade', '').strip() or None,
                'developer': row.get('dt-developer', '').strip() or None,
                'spaceType': row.get('dt-space-type', '').strip() or None,
                'endStatus': row.get('dt-end-status', '').strip() or None,
                'exitDate': parse_date_to_yyyymm(row.get('dt-exit-date', '')),
                # New CRE fields (Session 3)
                'absorptionDate': parse_date_to_yyyymm(row.get('dt-absorption-date', '')),
                'market': row.get('dt-market', '').strip() or None,
                'macroMarket': row.get('dt-macro-market', '').strip() or None,
                'microMarket': row.get('dt-micro-market', '').strip() or None,
                'complexDetails': complex_name or None,
                'pincode': row.get('dt-pincode', '').strip() or None,
                'buildingCategory': row.get('dt-building-category', '').strip() or None,
                'startingRentCarpet': parse_number(row.get('dt-starting-rent-carpet', '')),
                'currentRentCarpet': parse_number(row.get('dt-current-rent-carpet', '')),
                'propertyTaxPayer': row.get('dt-property-tax-payer', '').strip() or None,
            }
            transactions.append(txn)

            # Index by building + floor for matching
            try:
                floor_num = int(floor_str)
                by_building_floor[(full_building, floor_num)].append(txn)
            except ValueError:
                # Some floors are like "Lower Ground", "Mezzanine" etc.
                by_building_floor[(full_building, floor_str)].append(txn)

    return transactions, by_building_floor


def fuzzy_tenant_match(floor_tenant, txn_brand, txn_spv):
    """Check if tenant names match (case-insensitive, partial)."""
    if not floor_tenant or not txn_brand:
        return False
    ft = floor_tenant.lower().strip()
    tb = txn_brand.lower().strip()
    ts = txn_spv.lower().strip() if txn_spv else ''

    # Direct match
    if ft == tb or ft == ts:
        return True

    # Partial match — check if key words overlap
    ft_words = set(re.sub(r'[^a-z0-9\s]', '', ft).split())
    tb_words = set(re.sub(r'[^a-z0-9\s]', '', tb).split())
    ts_words = set(re.sub(r'[^a-z0-9\s]', '', ts).split())

    # Remove common words
    stop_words = {'pvt', 'ltd', 'private', 'limited', 'india', 'solutions', 'services', 'technologies', 'company', 'the', 'of', 'and'}
    ft_key = ft_words - stop_words
    tb_key = tb_words - stop_words
    ts_key = ts_words - stop_words

    if ft_key and tb_key and len(ft_key & tb_key) >= 1:
        return True
    if ft_key and ts_key and len(ft_key & ts_key) >= 1:
        return True

    return False


def find_best_transaction(floor_entry, txn_list):
    """Find the most recent matching transaction for a floor entry."""
    tenant = floor_entry.get('tenant', '')
    if not txn_list:
        return None

    # First try: exact tenant match, most recent
    matches = []
    for txn in txn_list:
        if fuzzy_tenant_match(tenant, txn['tenantBrand'], txn['tenantSPV']):
            matches.append(txn)

    if matches:
        # Sort by commencement date descending (most recent first)
        matches.sort(key=lambda t: t.get('commencementDate') or '0000-00', reverse=True)
        return matches[0]

    # Fallback: most recent transaction on this floor
    sorted_txns = sorted(txn_list, key=lambda t: t.get('commencementDate') or '0000-00', reverse=True)
    return sorted_txns[0] if sorted_txns else None


def find_all_landlords(txn_list):
    """Aggregate ALL unique landlords from all transactions on a floor."""
    if not txn_list:
        return []
    landlords = []
    seen = set()
    for txn in txn_list:
        ll = txn.get('landlord')
        if ll and ll not in seen:
            seen.add(ll)
            landlords.append(ll)
    return landlords


def detect_vacancy_conflict(floor_entry, txn_list):
    """Check if CSV says vacant but CREMatrix has active leases.
    Returns (is_conflict, active_tenant, active_txn) or (False, None, None)."""
    if not txn_list:
        return False, None, None

    tenant = floor_entry.get('tenant', '')
    status = floor_entry.get('status', '')

    # Only check for conflict if CSV says vacant
    if tenant.lower() != 'vacant' and 'vacant' not in status.lower():
        return False, None, None

    # Check if any CREMatrix transaction has lease expiry AFTER today
    now = datetime.now().strftime("%Y-%m")
    active_txns = []
    for txn in txn_list:
        expiry = txn.get('leaseExpiryDate')
        if expiry and expiry >= now:
            active_txns.append(txn)

    if active_txns:
        # Sort by commencement date, most recent first
        active_txns.sort(key=lambda t: t.get('commencementDate') or '0000-00', reverse=True)
        best = active_txns[0]
        active_tenant = best.get('tenantBrand') or best.get('tenantSPV') or 'Unclassified'
        return True, active_tenant, best

    return False, None, None


def calculate_vacancy_duration(txn):
    """Calculate how long a space has been vacant based on lease expiry."""
    expiry = txn.get('leaseExpiryDate')
    if not expiry:
        return None
    try:
        expiry_dt = datetime.strptime(expiry, "%Y-%m")
        now = datetime(2026, 4, 1)  # Current approximate date
        if expiry_dt < now:
            months = (now.year - expiry_dt.year) * 12 + (now.month - expiry_dt.month)
            if months <= 6:
                return f"{months} months"
            else:
                years = months // 12
                rem = months % 12
                if years > 0 and rem > 0:
                    return f"{years}y {rem}m"
                elif years > 0:
                    return f"{years} years"
                else:
                    return f"{rem} months"
    except:
        pass
    return None


# ============================================================
# STEP 4: Build enriched floor data
# ============================================================
def enrich_floor(floor_entry, txn_lookup):
    """Enrich a single floor entry with CREMatrix data."""
    bldg = floor_entry['building']
    floor_num = floor_entry['floor']

    # Get transactions for this building+floor
    txn_list = txn_lookup.get((bldg, floor_num), [])
    best_txn = find_best_transaction(floor_entry, txn_list)

    # Start with floor data
    enriched = dict(floor_entry)

    # --- CONFLICT DETECTION: CSV says vacant but CREMatrix has active leases ---
    is_conflict, active_tenant, active_txn = detect_vacancy_conflict(floor_entry, txn_list)
    if is_conflict:
        print(f"  ⚠️  CONFLICT: {bldg} F{floor_num} — CSV says Vacant but CREMatrix has active lease: {active_tenant} (expires {active_txn.get('leaseExpiryDate')})")
        # Override with CREMatrix data — CREMatrix is more recent
        enriched['tenant'] = active_tenant
        enriched['occupancy'] = 100
        enriched['status'] = 'Fully Occupied'
        enriched['dataConflict'] = f"Sales team CSV marked Vacant — CREMatrix shows active {active_tenant} lease expiring {active_txn.get('leaseExpiryDate')}. Data corrected from CREMatrix."
        # Use the active transaction as best_txn
        best_txn = active_txn
        # Backfill rent from active deal
        if not enriched.get('rentPerSqft') or enriched['rentPerSqft'] == 69:
            enriched['rentPerSqft'] = active_txn.get('startingRent') or active_txn.get('effectiveRent')
        enriched['leaseStart'] = active_txn.get('commencementDate')
        enriched['leaseEnd'] = active_txn.get('leaseExpiryDate')
        enriched['vacancyDuration'] = None
        # Recalculate revenue
        if enriched.get('rentPerSqft') and enriched.get('carpetArea'):
            enriched['monthlyRevenue'] = round(enriched['rentPerSqft'] * enriched['carpetArea'])
            enriched['annualRevenue'] = round(enriched['monthlyRevenue'] * 12)
        enriched['rentalYield'] = 0  # will be recalculated later
    else:
        enriched['dataConflict'] = None

    # --- MULTI-LANDLORD CAPTURE ---
    all_landlords = find_all_landlords(txn_list)
    if len(all_landlords) > 1:
        enriched['allLandlords'] = all_landlords
    else:
        enriched['allLandlords'] = None

    # Backfill rent from CREMatrix if missing
    if not enriched.get('rentPerSqft') and best_txn:
        enriched['rentPerSqft'] = best_txn.get('startingRent') or best_txn.get('effectiveRent')

    # Property condition: CREMatrix 5-tier > Status fallback
    if best_txn and best_txn.get('propertyCondition') and best_txn['propertyCondition'] != 'Not Given':
        enriched['propertyCondition'] = best_txn['propertyCondition']
    else:
        status = enriched.get('status', '').lower()
        if 'furnished' in status or enriched.get('status') == 'Fully Occupied':
            enriched['propertyCondition'] = 'Fitted Out'
        elif 'bare' in status:
            enriched['propertyCondition'] = 'Bare Shell'
        elif 'vacant' in status.lower():
            enriched['propertyCondition'] = 'Bare Shell'
        else:
            enriched['propertyCondition'] = 'Fitted Out'

    # Vacancy duration from CREMatrix (only if actually vacant)
    if not is_conflict and ('vacant' in enriched.get('tenant', '').lower() or enriched.get('occupancy', 100) == 0):
        if best_txn:
            enriched['vacancyDuration'] = calculate_vacancy_duration(best_txn)

    # Efficiency: use CREMatrix actual if available
    if best_txn and best_txn.get('efficiency'):
        enriched['efficiencyRatio'] = best_txn['efficiency']

    # CREMatrix enrichment fields
    if best_txn:
        enriched['sector'] = best_txn.get('sector')
        # Use aggregated landlords if multiple, else single from best txn
        if enriched.get('allLandlords') and len(enriched['allLandlords']) > 1:
            enriched['landlord'] = f"Multiple ({len(enriched['allLandlords'])} owners)"
            enriched['landlordContact'] = ', '.join(enriched['allLandlords'][:5])
            enriched['landlordLinkedIn'] = None
        else:
            enriched['landlord'] = best_txn.get('landlord')
            enriched['landlordContact'] = best_txn.get('landlordContact')
            enriched['landlordLinkedIn'] = best_txn.get('landlordLinkedIn')
        enriched['dealType'] = best_txn.get('dealType')
        if best_txn.get('dealType') in ('-', ''):
            enriched['dealType'] = None
        enriched['startingRent'] = best_txn.get('startingRent')
        enriched['effectiveRent'] = best_txn.get('effectiveRent')
        enriched['leaseExpiryRent'] = best_txn.get('leaseExpiryRent')
        enriched['agreementType'] = best_txn.get('agreementType')
        enriched['dealMemo'] = best_txn.get('dealMemo')
        enriched['rentFreeMonths'] = best_txn.get('rentFreePeriod')
        enriched['freeCarParks'] = best_txn.get('freeCarParks')
        enriched['paidCarParks'] = best_txn.get('paidCarParks')
        enriched['rentEscalation'] = best_txn.get('rentEscalation')
        enriched['escalationPeriod'] = best_txn.get('escalationPeriod')
        enriched['nextEscalationDue'] = best_txn.get('nextEscalationDue')
        enriched['leaseExpiryDate'] = best_txn.get('leaseExpiryDate')
        if best_txn.get('lockInPeriod') and not enriched.get('lockInPeriod'):
            enriched['lockInPeriod'] = f"{best_txn['lockInPeriod']} months"
        enriched['lockInExpiryDate'] = best_txn.get('lockInExpiryDate')
    else:
        # No CREMatrix match — set null for all enrichment fields
        for field in ['sector', 'landlord', 'landlordContact', 'landlordLinkedIn',
                      'dealType', 'startingRent', 'effectiveRent', 'leaseExpiryRent',
                      'agreementType', 'dealMemo', 'rentFreeMonths', 'freeCarParks',
                      'paidCarParks', 'rentEscalation', 'escalationPeriod',
                      'nextEscalationDue', 'leaseExpiryDate', 'lockInExpiryDate']:
            enriched[field] = None

    return enriched


# ============================================================
# STEP 5: Aggregate floor entries to per-floor summaries
# ============================================================
def aggregate_floors(floor_entries, building_info, txn_lookup=None):
    """Aggregate multiple tenant entries per floor into single floor objects."""
    by_floor = defaultdict(list)
    for entry in floor_entries:
        by_floor[entry['floor']].append(entry)

    aggregated = []
    for floor_num in sorted(by_floor.keys()):
        entries = by_floor[floor_num]
        floor_plate = building_info.get('floorPlateSize') or sum(e.get('area', 0) or 0 for e in entries)

        if len(entries) == 1:
            e = entries[0]
            agg = build_floor_object(e, floor_plate, entries, txn_lookup)
            aggregated.append(agg)
        else:
            # Multiple tenants on this floor — pick primary tenant (highest occupancy)
            entries.sort(key=lambda x: x.get('occupancy', 0) or 0, reverse=True)
            primary = entries[0]
            total_occ = sum(e.get('occupancy', 0) or 0 for e in entries)
            # Cap at 100
            total_occ = min(total_occ, 100)

            # Count vacant vs occupied
            vacant_entries = [e for e in entries if 'vacant' in (e.get('tenant', '') or '').lower()]
            occupied_entries = [e for e in entries if 'vacant' not in (e.get('tenant', '') or '').lower()]

            if not occupied_entries:
                primary_tenant = "Vacant"
                status = "Vacant"
                total_occ = 0  # vacant = 0% occupancy regardless of CSV
            elif len(occupied_entries) == 1:
                primary_tenant = occupied_entries[0]['tenant']
                status = "Fully Occupied" if not vacant_entries else "Partially Vacant"
            else:
                primary_tenant = f"{occupied_entries[0]['tenant']} + {len(occupied_entries)-1} more"
                status = "Multi-tenant"

            agg = build_floor_object(primary, floor_plate, entries, txn_lookup)
            agg['tenant'] = primary_tenant
            agg['occupancy'] = round(total_occ, 1)
            agg['status'] = status
            agg['area'] = floor_plate
            # Aggregate conflicts and landlords from all entries
            conflicts = [e.get('dataConflict') for e in entries if e.get('dataConflict')]
            if conflicts:
                agg['dataConflict'] = ' | '.join(conflicts)
            all_ll = []
            for e in entries:
                if e.get('allLandlords'):
                    for ll in e['allLandlords']:
                        if ll not in all_ll:
                            all_ll.append(ll)
            if len(all_ll) > 1:
                agg['allLandlords'] = all_ll
                agg['landlord'] = f"Multiple ({len(all_ll)} owners)"
                agg['landlordContact'] = ', '.join(all_ll[:5])
            # Build tenants array with FULL CRE enrichment per tenant
            # Fuzzy dedup key: strip common suffixes and normalize
            def tenant_key(name):
                import re
                k = name.lower().strip()
                for s in ['private limited', 'pvt. ltd.', 'pvt ltd', 'pvt. ltd', 'pvt', 'ltd', 'limited', 'llp', '(india)', 'india', '(p)']:
                    k = k.replace(s, '')
                k = re.sub(r'[^a-z0-9]', '', k)  # only alphanumeric
                return k

            seen_tenants = {}
            seen_keys = {}  # fuzzy key -> canonical name
            for e in entries:
                name = e.get('tenant', '')
                key = tenant_key(name)
                canonical = seen_keys.get(key, name)
                if key in seen_keys:
                    existing_occ = seen_tenants[canonical]['occupancy'] or 0
                    new_occ = e.get('occupancy') or 0
                    seen_tenants[canonical]['occupancy'] = min(round(max(existing_occ, new_occ), 1), 100)
                    seen_tenants[canonical]['area'] = (seen_tenants[canonical]['area'] or 0) + (e.get('area') or 0)
                else:
                    seen_keys[key] = name
                    seen_tenants[name] = {
                        'name': name,
                        'occupancy': e.get('occupancy'),
                        'area': e.get('area'),
                        'rentPerSqft': e.get('rentPerSqft'),
                        'sector': e.get('sector'),
                        'landlord': e.get('landlord'),
                        'propertyCondition': e.get('propertyCondition'),
                        # Per-tenant CRE enrichment fields
                        'effectiveRent': e.get('effectiveRent'),
                        'startingRent': e.get('startingRent'),
                        'leaseExpiryRent': e.get('leaseExpiryRent'),
                        'dealType': e.get('dealType'),
                        'leaseStart': e.get('leaseStart'),
                        'leaseExpiryDate': e.get('leaseExpiryDate'),
                        'lockInPeriod': e.get('lockInPeriod'),
                        'rentEscalation': e.get('rentEscalation'),
                        'escalationPeriod': e.get('escalationPeriod'),
                        'agreementType': e.get('agreementType'),
                        'landlordContact': e.get('landlordContact'),
                    }
            tenant_list = list(seen_tenants.values())
            # Normalize occupancy so tenants sum to 100% (conflict overrides can inflate)
            raw_total = sum(t.get('occupancy') or 0 for t in tenant_list)
            if raw_total > 100:
                scale = 100.0 / raw_total
                for t in tenant_list:
                    if t.get('occupancy'):
                        t['occupancy'] = round(t['occupancy'] * scale, 1)
            agg['tenants'] = tenant_list

            aggregated.append(agg)

    return aggregated


def build_floor_object(entry, floor_plate, all_entries, txn_lookup=None):
    """Build a single floor JS object from an enriched entry."""
    area = floor_plate or entry.get('area', 0) or 0
    rent = entry.get('rentPerSqft')
    efficiency = entry.get('efficiencyRatio', 70) or 70

    # Force 0% occupancy for vacant floors regardless of CSV value
    tenant_name = entry.get('tenant', '') or ''
    # Clean "(vacant)" from tenant names — if name contains "vacant", it's just vacant
    is_vacant = 'vacant' in tenant_name.lower()
    if is_vacant:
        tenant_name = 'Vacant'
        entry['tenant'] = 'Vacant'
        entry['status'] = 'Vacant'
        entry['propertyCondition'] = 'Bare Shell'  # vacant = bare shell regardless of CRE history
    raw_occ = entry.get('occupancy', 0) or 0

    obj = {
        'floor': entry['floor'],
        'tenant': entry['tenant'],
        'occupancy': 0 if is_vacant else raw_occ,
        'rentPerSqft': rent,
        'area': area,
        'leaseStart': entry.get('leaseStart'),
        'leaseEnd': entry.get('leaseEnd'),
        'status': entry.get('status', 'Unclassified'),
        'carpetArea': round(area * efficiency / 100) if area else None,
        'superBuiltUp': area,
        'lockInPeriod': entry.get('lockInPeriod'),
        'lockInEnd': entry.get('lockInExpiryDate'),
        'securityDeposit': entry.get('securityDeposit'),
        'fitOut': entry.get('propertyCondition', 'Fitted Out'),
        'vacancyDuration': entry.get('vacancyDuration'),
        'rentalYield': 0 if is_vacant else (round(((rent or 0) * 12) / 8500 * 100, 2) if rent else 0),
        'monthlyRevenue': 0 if is_vacant else (round(rent * area) if rent and area else 0),
        'annualRevenue': 0 if is_vacant else (round(rent * area * 12) if rent and area else 0),
        # New CREMatrix fields
        'sector': entry.get('sector'),
        'landlord': entry.get('landlord'),
        'landlordContact': entry.get('landlordContact'),
        'landlordLinkedIn': entry.get('landlordLinkedIn'),
        'dealType': entry.get('dealType'),
        'startingRent': entry.get('startingRent'),
        'effectiveRent': entry.get('effectiveRent'),
        'leaseExpiryRent': entry.get('leaseExpiryRent'),
        'propertyCondition': entry.get('propertyCondition'),
        'agreementType': entry.get('agreementType'),
        'dealMemo': entry.get('dealMemo'),
        'rentFreeMonths': entry.get('rentFreeMonths'),
        'freeCarParks': entry.get('freeCarParks'),
        'paidCarParks': entry.get('paidCarParks'),
        'rentEscalation': entry.get('rentEscalation'),
        'escalationPeriod': entry.get('escalationPeriod'),
        'nextEscalationDue': entry.get('nextEscalationDue'),
        'leaseExpiryDate': entry.get('leaseExpiryDate'),
        'efficiencyRatio': entry.get('efficiencyRatio', 70),
        # Conflict detection + multi-landlord
        'dataConflict': entry.get('dataConflict'),
        'allLandlords': entry.get('allLandlords'),
        # New CRE fields (Session 3 — 11 additions)
        'absorptionDate': entry.get('absorptionDate'),
        'microMarketCRE': entry.get('microMarket'),
        'buildingCategory': entry.get('buildingCategory'),
        'developer': entry.get('developer'),
        'startingRentCarpet': entry.get('startingRentCarpet'),
        'currentRentCarpet': entry.get('currentRentCarpet'),
        'propertyTaxPayer': entry.get('propertyTaxPayer'),
        'pincode': entry.get('pincode'),
    }

    # Build per-floor deal history from ALL CRE transactions
    if txn_lookup:
        bldg = entry.get('building', '')
        floor_num = entry.get('floor', 0)
        floor_txns = txn_lookup.get((bldg, floor_num), [])
        if floor_txns:
            history = []
            for txn in sorted(floor_txns, key=lambda t: t.get('commencementDate') or '0000', reverse=True):
                tenant = txn.get('tenantBrand') or txn.get('tenantSPV') or 'Unclassified'
                history.append({
                    'date': txn.get('commencementDate'),
                    'tenant': tenant,
                    'type': txn.get('dealType'),
                    'rent': txn.get('startingRent'),
                    'effectiveRent': txn.get('effectiveRent'),
                    'expiry': txn.get('leaseExpiryDate'),
                    'area': txn.get('chargeableArea'),
                    'sector': txn.get('sector'),
                })
            obj['floorDealHistory'] = history

    return obj


# ============================================================
# STEP 6: Build deal history per building from CREMatrix
# ============================================================
def build_deal_history(transactions, building_full_name):
    """Build year-by-year deal history for a building from real CREMatrix data."""
    bldg_txns = [t for t in transactions if t['building'] == building_full_name]
    if not bldg_txns:
        return []

    by_year = defaultdict(lambda: {'deals': 0, 'totalArea': 0, 'avgRent': 0, 'rents': [], 'newDeals': 0, 'renewals': 0})
    for txn in bldg_txns:
        cd = txn.get('commencementDate')
        if not cd:
            continue
        try:
            year = int(cd[:4])
        except:
            continue

        by_year[year]['deals'] += 1
        if txn.get('chargeableArea'):
            by_year[year]['totalArea'] += txn['chargeableArea']
        if txn.get('startingRent'):
            by_year[year]['rents'].append(txn['startingRent'])
        dt = txn.get('dealType', '') or ''
        if dt.lower() == 'new':
            by_year[year]['newDeals'] += 1
        elif dt.lower() == 'renewal':
            by_year[year]['renewals'] += 1

    history = []
    for year in sorted(by_year.keys()):
        data = by_year[year]
        avg_rent = round(sum(data['rents']) / len(data['rents']), 1) if data['rents'] else None
        history.append({
            'year': year,
            'deals': data['deals'],
            'totalArea': data['totalArea'],
            'avgRent': avg_rent,
            'newDeals': data['newDeals'],
            'renewals': data['renewals'],
        })
    return history


# ============================================================
# STEP 7: Build sector mix per building
# ============================================================
def build_sector_mix(transactions, building_full_name):
    """Build sector distribution for a building."""
    bldg_txns = [t for t in transactions if t['building'] == building_full_name]
    sector_area = defaultdict(int)
    for txn in bldg_txns:
        sector = txn.get('sector')
        if not sector or sector == '-':
            sector = 'Unclassified'
        area = txn.get('chargeableArea') or 0
        sector_area[sector] += area

    total = sum(sector_area.values())
    if total == 0:
        return []

    mix = []
    for sector, area in sorted(sector_area.items(), key=lambda x: -x[1]):
        mix.append({
            'sector': sector,
            'area': area,
            'percentage': round(area / total * 100, 1)
        })
    return mix


# ============================================================
# STEP 8: Generate JS output
# ============================================================
def js_value(val, indent=0):
    """Convert Python value to JS-safe string."""
    if val is None:
        return 'null'
    if isinstance(val, bool):
        return 'true' if val else 'false'
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, str):
        # Escape for JS
        escaped = val.replace('\\', '\\\\').replace("'", "\\'").replace('"', '\\"').replace('\n', '\\n').replace('\r', '')
        return f'"{escaped}"'
    if isinstance(val, list):
        if not val:
            return '[]'
        items = [js_value(v, indent+2) for v in val]
        if all(isinstance(v, (int, float, str, type(None))) for v in val):
            return '[' + ', '.join(items) + ']'
        inner = (',\n' + ' ' * (indent+2)).join(items)
        return f'[\n{" " * (indent+2)}{inner}\n{" " * indent}]'
    if isinstance(val, dict):
        items = []
        for k, v in val.items():
            key = k if re.match(r'^[a-zA-Z_$][a-zA-Z0-9_$]*$', k) else f'"{k}"'
            items.append(f'{" " * (indent+2)}{key}: {js_value(v, indent+2)}')
        inner = ',\n'.join(items)
        return f'{{\n{inner}\n{" " * indent}}}'
    return str(val)


def generate_building_js(building_info, floors, transactions, all_transactions, park_type, building_config):
    """Generate JS object for a single building."""
    full_name = building_info['name']
    if 'Vatika' in full_name:
        short_name = full_name.replace('Vatika Business Park ', '')
    elif 'Unitech' in full_name:
        short_name = full_name.replace('Unitech Cyber Park ', '')
    else:
        short_name = BUILDING_SHORT.get(full_name, full_name.split()[-1])

    deal_history = build_deal_history(all_transactions, full_name)
    sector_mix = build_sector_mix(all_transactions, full_name)

    # Extract building-level CRE fields from first transaction for this building
    bldg_txns = [t for t in all_transactions if t.get('building') == full_name or t.get('buildingShort') == full_name]
    first_txn = bldg_txns[0] if bldg_txns else {}
    cre_developer = first_txn.get('developer')
    cre_building_category = first_txn.get('buildingCategory')
    cre_micro_market = first_txn.get('microMarket')
    cre_market = first_txn.get('market')
    cre_macro_market = first_txn.get('macroMarket')
    cre_pincode = first_txn.get('pincode')

    # Get config values (position, color, shape etc.) from existing data
    cfg = building_config

    lines = []
    lines.append('    {')
    lines.append(f'      id: "{cfg["id"]}",')
    lines.append(f'      name: "{short_name}",')
    lines.append(f'      totalFloors: {building_info["totalFloors"] or cfg.get("totalFloors", 10)},')
    lines.append(f'      totalArea: {building_info["totalArea"] or 0},')
    lines.append(f'      yearBuilt: {building_info["yearBuilt"] or 0},')
    lines.append(f'      color: "{cfg["color"]}",')
    lines.append(f'      position: {{ x: {cfg["position"]["x"]}, z: {cfg["position"]["z"]} }},')
    lines.append(f'      width: {cfg["width"]}, depth: {cfg["depth"]}, height: {cfg["height"]},')
    lines.append(f'      rotation: {cfg.get("rotation", 0)},')
    lines.append(f'      buildingShape: "{cfg.get("buildingShape", "box")}",')
    lines.append(f'      grade: "{building_info.get("grade") or cfg.get("grade", "")}",')

    cert = building_info.get("certification")
    lines.append(f'      certification: {js_value(cert)},')

    lines.append(f'      camCharges: {building_info.get("camCharges") or cfg.get("camCharges", 0)},')
    lines.append(f'      escalation: "{building_info.get("escalation") or cfg.get("escalation", "")}",')
    lines.append(f'      powerBackup: "{building_info.get("powerBackup") or cfg.get("powerBackup", "")}",')
    lines.append(f'      parkingRatio: {cfg.get("parkingRatio", 1.0)},')
    lines.append(f'      floorPlateSize: {building_info.get("floorPlateSize") or cfg.get("floorPlateSize", 0)},')
    lines.append(f'      efficiencyRatio: {building_info.get("efficiencyRatio") or 70},')
    lines.append(f'      amenities: {js_value(cfg.get("amenities", []))},')
    lines.append(f'      microMarket: "{cfg.get("microMarket", "")}",')
    lines.append(f'      microMarketAvgRent: {building_info.get("microMarketAvgRent") or cfg.get("microMarketAvgRent", 0)},')
    lines.append(f'      absorptionRate: {cfg.get("absorptionRate", 70)},')
    lines.append(f'      upcomingSupply: "{cfg.get("upcomingSupply", "Limited")}",')
    lines.append(f'      capitalValuePerSqft: 0,')
    lines.append(f'      capitalValueTrend: [],')

    # New: deal history from real CREMatrix data
    lines.append(f'      dealHistory: {json.dumps(deal_history)},')
    # New: sector mix
    lines.append(f'      sectorMix: {json.dumps(sector_mix)},')
    # New: building-level CRE fields (Session 3)
    lines.append(f'      developer: {js_value(cre_developer)},')
    lines.append(f'      buildingCategory: {js_value(cre_building_category)},')
    lines.append(f'      microMarketCRE: {js_value(cre_micro_market)},')
    lines.append(f'      market: {js_value(cre_market)},')
    lines.append(f'      macroMarket: {js_value(cre_macro_market)},')
    lines.append(f'      pincode: {js_value(cre_pincode)},')

    # Floors
    lines.append('      floors: [')
    for i, floor in enumerate(floors):
        comma = ',' if i < len(floors) - 1 else ''
        lines.append(generate_floor_js(floor) + comma)
    lines.append('      ]')
    lines.append('    }')

    return '\n'.join(lines)


def generate_floor_js(floor):
    """Generate JS object for a single floor."""
    lines = []
    lines.append('        {')

    # Core fields
    lines.append(f'          floor: {floor["floor"]},')
    lines.append(f'          tenant: {js_value(floor["tenant"])},')
    lines.append(f'          occupancy: {floor.get("occupancy", 0)},')
    lines.append(f'          rentPerSqft: {js_value(floor.get("rentPerSqft"))},')
    lines.append(f'          area: {floor.get("area", 0)},')
    lines.append(f'          leaseStart: {js_value(floor.get("leaseStart"))},')
    lines.append(f'          leaseEnd: {js_value(floor.get("leaseEnd"))},')
    lines.append(f'          status: {js_value(floor.get("status"))},')
    lines.append(f'          carpetArea: {js_value(floor.get("carpetArea"))},')
    lines.append(f'          superBuiltUp: {floor.get("superBuiltUp", 0)},')
    lines.append(f'          lockInPeriod: {js_value(floor.get("lockInPeriod"))},')
    lines.append(f'          lockInEnd: {js_value(floor.get("lockInEnd"))},')
    lines.append(f'          securityDeposit: {js_value(floor.get("securityDeposit"))},')
    lines.append(f'          fitOut: {js_value(floor.get("fitOut"))},')
    lines.append(f'          vacancyDuration: {js_value(floor.get("vacancyDuration"))},')
    lines.append(f'          rentalYield: {floor.get("rentalYield", 0)},')
    lines.append(f'          monthlyRevenue: {floor.get("monthlyRevenue", 0)},')
    lines.append(f'          annualRevenue: {floor.get("annualRevenue", 0)},')

    # CREMatrix enrichment fields
    lines.append(f'          // CREMatrix enrichment')
    lines.append(f'          sector: {js_value(floor.get("sector"))},')
    lines.append(f'          landlord: {js_value(floor.get("landlord"))},')
    lines.append(f'          landlordContact: {js_value(floor.get("landlordContact"))},')
    lines.append(f'          landlordLinkedIn: {js_value(floor.get("landlordLinkedIn"))},')
    lines.append(f'          dealType: {js_value(floor.get("dealType"))},')
    lines.append(f'          startingRent: {js_value(floor.get("startingRent"))},')
    lines.append(f'          effectiveRent: {js_value(floor.get("effectiveRent"))},')
    lines.append(f'          leaseExpiryRent: {js_value(floor.get("leaseExpiryRent"))},')
    lines.append(f'          propertyCondition: {js_value(floor.get("propertyCondition"))},')
    lines.append(f'          agreementType: {js_value(floor.get("agreementType"))},')
    lines.append(f'          dealMemo: {js_value(floor.get("dealMemo"))},')
    lines.append(f'          rentFreeMonths: {js_value(floor.get("rentFreeMonths"))},')
    lines.append(f'          freeCarParks: {js_value(floor.get("freeCarParks"))},')
    lines.append(f'          paidCarParks: {js_value(floor.get("paidCarParks"))},')
    lines.append(f'          rentEscalation: {js_value(floor.get("rentEscalation"))},')
    lines.append(f'          escalationPeriod: {js_value(floor.get("escalationPeriod"))},')
    lines.append(f'          nextEscalationDue: {js_value(floor.get("nextEscalationDue"))},')
    lines.append(f'          leaseExpiryDate: {js_value(floor.get("leaseExpiryDate"))},')
    lines.append(f'          efficiencyRatio: {js_value(floor.get("efficiencyRatio"))},')

    # Data conflict flag (CSV vs CREMatrix mismatch)
    if floor.get('dataConflict'):
        lines.append(f'          dataConflict: {js_value(floor["dataConflict"])},')

    # All landlords (when multiple owners exist)
    if floor.get('allLandlords'):
        lines.append(f'          allLandlords: {json.dumps(floor["allLandlords"])},')

    # Multi-tenant breakdown if exists
    if floor.get('tenants'):
        lines.append(f'          tenants: {json.dumps(floor["tenants"])},')

    # Per-floor deal history from CRE transactions
    if floor.get('floorDealHistory'):
        lines.append(f'          floorDealHistory: {json.dumps(floor["floorDealHistory"])},')

    # New CRE fields (Session 3)
    if floor.get('absorptionDate'):
        lines.append(f'          absorptionDate: {js_value(floor["absorptionDate"])},')
    if floor.get('startingRentCarpet'):
        lines.append(f'          startingRentCarpet: {js_value(floor["startingRentCarpet"])},')
    if floor.get('currentRentCarpet'):
        lines.append(f'          currentRentCarpet: {js_value(floor["currentRentCarpet"])},')
    if floor.get('propertyTaxPayer'):
        lines.append(f'          propertyTaxPayer: {js_value(floor["propertyTaxPayer"])},')
    if floor.get('buildingCategory'):
        lines.append(f'          buildingCategory: {js_value(floor["buildingCategory"])},')

    lines.append('        }')
    return '\n'.join(lines)


# ============================================================
# EXISTING BUILDING CONFIGS (positions, colors, shapes from current JS)
# ============================================================
UNITECH_CONFIGS = {
    "Unitech Cyber Park Tower A": {
        "id": "tower-a", "color": "#e97320",
        "position": {"x": 2.2, "z": 8.5}, "width": 14, "depth": 5, "height": 3.5,
        "rotation": 0.35, "buildingShape": "box", "totalFloors": 8,
        "grade": "B", "camCharges": 19, "escalation": "15% every 3 years",
        "powerBackup": "100% DG + Dual Feed", "parkingRatio": 1.0,
        "floorPlateSize": 53000, "amenities": ["Cafeteria", "ATM", "Parking", "Power Backup", "Lift", "Security"],
        "microMarket": "Sector 39, Gurugram", "microMarketAvgRent": 65,
        "absorptionRate": 70, "upcomingSupply": "Limited"
    },
    "Unitech Cyber Park Tower B": {
        "id": "tower-b", "color": "#3b82f6",
        "position": {"x": -9.8, "z": 0.4}, "width": 9, "depth": 4.5, "height": 6.4,
        "rotation": -0.26, "buildingShape": "box", "totalFloors": 16,
        "grade": "B", "camCharges": 19, "escalation": "15% every 3 years",
        "powerBackup": "100% DG + Dual Feed", "parkingRatio": 1.0,
        "floorPlateSize": 25777, "amenities": ["Cafeteria", "ATM", "Parking", "Power Backup", "Lift", "Security"],
        "microMarket": "Sector 39, Gurugram", "microMarketAvgRent": 65,
        "absorptionRate": 72, "upcomingSupply": "Limited"
    },
    "Unitech Cyber Park Tower C": {
        "id": "tower-c", "color": "#10b981",
        "position": {"x": -0.8, "z": -3.8}, "width": 9, "depth": 4.5, "height": 6.4,
        "rotation": 0.09, "buildingShape": "box", "totalFloors": 16,
        "grade": "B", "camCharges": 19, "escalation": "15% every 3 years",
        "powerBackup": "100% DG + Dual Feed", "parkingRatio": 1.0,
        "floorPlateSize": 27286, "amenities": ["Cafeteria", "ATM", "Parking", "Power Backup", "Lift", "Security"],
        "microMarket": "Sector 39, Gurugram", "microMarketAvgRent": 65,
        "absorptionRate": 68, "upcomingSupply": "Limited"
    },
    "Unitech Cyber Park Tower D": {
        "id": "tower-d", "color": "#8b5cf6",
        "position": {"x": 8.3, "z": -5.1}, "width": 8, "depth": 4.2, "height": 4.2,
        "rotation": 0.17, "buildingShape": "box", "totalFloors": 10,
        "grade": "B", "camCharges": 19, "escalation": "15% every 3 years",
        "powerBackup": "100% DG + Dual Feed", "parkingRatio": 1.0,
        "floorPlateSize": 27000, "amenities": ["Cafeteria", "ATM", "Parking", "Power Backup", "Lift", "Security"],
        "microMarket": "Sector 39, Gurugram", "microMarketAvgRent": 65,
        "absorptionRate": 75, "upcomingSupply": "Limited"
    }
}

VATIKA_CONFIGS = {
    "Vatika Business Park Building 1": {
        "id": "vatika-bldg-1", "color": "#2563eb",
        "position": {"x": -4, "z": -3}, "width": 6, "depth": 4, "height": 3.5,
        "rotation": 0, "buildingShape": "box", "totalFloors": 8,
        "grade": "A", "camCharges": 18, "escalation": "15% every 3 years",
        "powerBackup": "100% DG + Dual Feed", "parkingRatio": 1.0,
        "floorPlateSize": 27000, "amenities": ["Cafeteria", "ATM", "Parking", "Power Backup", "Lift", "Security", "Green Certified"],
        "microMarket": "Sohna Road, Gurugram", "microMarketAvgRent": 60,
        "absorptionRate": 78, "upcomingSupply": "Limited"
    },
    "Vatika Business Park Building 2": {
        "id": "vatika-bldg-2", "color": "#0891b2",
        "position": {"x": 2, "z": -2}, "width": 5, "depth": 3.5, "height": 5,
        "rotation": 0.1, "buildingShape": "box", "totalFloors": 14,
        "grade": "A", "camCharges": 18, "escalation": "15% every 3 years",
        "powerBackup": "100% DG + Dual Feed", "parkingRatio": 1.0,
        "floorPlateSize": 26900, "amenities": ["Cafeteria", "ATM", "Parking", "Power Backup", "Lift", "Security", "Green Certified"],
        "microMarket": "Sohna Road, Gurugram", "microMarketAvgRent": 60,
        "absorptionRate": 72, "upcomingSupply": "Limited"
    },
    "Vatika Business Park Building 3": {
        "id": "vatika-bldg-3", "color": "#7c3aed",
        "position": {"x": 5, "z": 3}, "width": 5, "depth": 3.5, "height": 3.5,
        "rotation": -0.15, "buildingShape": "box", "totalFloors": 9,
        "grade": "A", "camCharges": 18, "escalation": "15% every 3 years",
        "powerBackup": "100% DG + Dual Feed", "parkingRatio": 1.0,
        "floorPlateSize": 26000, "amenities": ["Cafeteria", "ATM", "Parking", "Power Backup", "Lift", "Security", "Green Certified"],
        "microMarket": "Sohna Road, Gurugram", "microMarketAvgRent": 60,
        "absorptionRate": 85, "upcomingSupply": "Limited"
    }
}


# ============================================================
# MAIN
# ============================================================
def main():
    print("Parsing Building CSV...")
    buildings = parse_buildings()
    print(f"  Found {len(buildings)} buildings")

    print("Parsing Floor CSV...")
    all_floors = parse_floors()
    total_floors = sum(len(v) for v in all_floors.values())
    print(f"  Found {total_floors} floor entries across {len(all_floors)} buildings")

    print("Parsing CREMatrix Transactions...")
    transactions, txn_lookup = parse_transactions()
    print(f"  Found {len(transactions)} transactions")

    # Enrich floor data
    print("Enriching floor data with CREMatrix...")
    enriched_floors = {}
    match_count = 0
    for bldg_name, floor_list in all_floors.items():
        enriched = []
        for floor_entry in floor_list:
            ef = enrich_floor(floor_entry, txn_lookup)
            if ef.get('sector') or ef.get('landlord'):
                match_count += 1
            enriched.append(ef)
        enriched_floors[bldg_name] = enriched
    print(f"  CREMatrix matched {match_count}/{total_floors} floor entries")

    # Aggregate floors per building
    print("Aggregating multi-tenant floors...")
    aggregated = {}
    for bldg_name, floor_list in enriched_floors.items():
        bldg_info = buildings.get(bldg_name, {})
        aggregated[bldg_name] = aggregate_floors(floor_list, bldg_info, txn_lookup)

    # Generate JS output
    print("Generating JS output...")

    # --- Unitech ---
    unitech_buildings_js = []
    for full_name in ["Unitech Cyber Park Tower A", "Unitech Cyber Park Tower B",
                      "Unitech Cyber Park Tower C", "Unitech Cyber Park Tower D"]:
        bldg_info = buildings.get(full_name, {})
        if not bldg_info:
            bldg_info = {'name': full_name}
        floors = aggregated.get(full_name, [])
        cfg = UNITECH_CONFIGS[full_name]
        js = generate_building_js(bldg_info, floors, transactions, transactions, 'unitech', cfg)
        unitech_buildings_js.append(js)

    # --- Vatika ---
    vatika_buildings_js = []
    for full_name in ["Vatika Business Park Building 1", "Vatika Business Park Building 2",
                      "Vatika Business Park Building 3"]:
        bldg_info = buildings.get(full_name, {})
        if not bldg_info:
            bldg_info = {'name': full_name}
        floors = aggregated.get(full_name, [])
        cfg = VATIKA_CONFIGS[full_name]
        js = generate_building_js(bldg_info, floors, transactions, transactions, 'vatika', cfg)
        vatika_buildings_js.append(js)

    # Read existing file for GURGAON_CITY_PARKS_DATA
    with open(OUTPUT_JS, 'r') as f:
        existing = f.read()

    # Extract GURGAON_CITY_PARKS_DATA section
    city_match = re.search(r'(const GURGAON_CITY_PARKS_DATA\s*=\s*\{.*)', existing, re.DOTALL)
    city_section = city_match.group(1) if city_match else ''

    # Assemble output
    output = []
    output.append('// ============================================================')
    output.append('// GURGAON TECH PARK DATA — Enriched with CREMatrix (Apr 2026)')
    output.append('// Auto-generated by tools/enrich-data.py')
    output.append('// ============================================================')
    output.append('')
    output.append('const GURGAON_TECH_PARK_DATA = {')
    output.append('  name: "Unitech Cyber Park",')
    output.append('  address: "Sector 39, Gurugram, Haryana 122003",')
    output.append('  dataSources: [')
    output.append('    { name: "myHQ Internal Data", url: "myhq.in", type: "Primary" },')
    output.append('    { name: "CRE Matrix", url: "crematrix.com", type: "CRE Database" }')
    output.append('  ],')
    output.append('  lastUpdated: "April 2026",')
    output.append('  campus: {')
    output.append('    boundary: [],')
    output.append('    gates: [], mainRoad: null, roads: [], center: null,')
    output.append('    parking: [], amenities: [], signs: [], roadSigns: [],')
    output.append('  },')
    output.append('  buildings: [')
    output.append(',\n'.join(unitech_buildings_js))
    output.append('  ]')
    output.append('};')
    output.append('')
    output.append('// ============================================================')
    output.append('// VATIKA BUSINESS PARK — Enriched with CREMatrix (Apr 2026)')
    output.append('// Auto-generated by tools/enrich-data.py')
    output.append('// ============================================================')
    output.append('const VATIKA_TECH_PARK_DATA = {')
    output.append('  name: "Vatika Business Park",')
    output.append('  address: "Sector 49, Sohna Road, Gurugram, Haryana 122018",')
    output.append('  dataSources: [')
    output.append('    { name: "myHQ Internal Data", url: "myhq.in", type: "Primary" },')
    output.append('    { name: "CRE Matrix", url: "crematrix.com", type: "CRE Database" }')
    output.append('  ],')
    output.append('  lastUpdated: "April 2026",')
    output.append('  buildings: [')
    output.append(',\n'.join(vatika_buildings_js))
    output.append('  ]')
    output.append('};')
    output.append('')

    if city_section:
        output.append(city_section)

    js_output = '\n'.join(output)

    with open(OUTPUT_JS, 'w') as f:
        f.write(js_output)

    print(f"\nDone! Written to {OUTPUT_JS}")
    print(f"  Unitech: {len(unitech_buildings_js)} buildings")
    print(f"  Vatika: {len(vatika_buildings_js)} buildings")

    # Summary stats
    print("\n=== ENRICHMENT SUMMARY ===")
    for bldg_name, floors in aggregated.items():
        short = BUILDING_SHORT.get(bldg_name, bldg_name)
        with_sector = sum(1 for f in floors if f.get('sector'))
        with_landlord = sum(1 for f in floors if f.get('landlord'))
        with_rent_backfill = sum(1 for f in floors if f.get('startingRent'))
        print(f"  {short}: {len(floors)} floors | sector: {with_sector} | landlord: {with_landlord} | CRE rent: {with_rent_backfill}")


if __name__ == '__main__':
    main()
