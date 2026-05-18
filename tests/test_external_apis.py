"""
Standalone External API Tester
Tests NASA FIRMS and TomTom Traffic APIs directly — no Django required.
Run from the project root:  python tests/test_external_apis.py

FINDINGS from first run:
- NASA FIRMS: Area query works (HTTP 200). keycheck and country endpoints need
  a different path — the area/csv endpoint is what matters and it works fine.
- TomTom: Auth + small bbox work fine. ±0.5° bbox (~3025km²) was fine but
  ±1.0° exceeded TomTom's 10,000km² limit. Production uses ±0.1° (~121km²),
  which is well within limits.
"""

import os
import json
import requests

# ── Load .env manually (no Django needed) ─────────────────────────────────────
def load_env(path=None):
    env_path = path or os.path.join(os.path.dirname(__file__), '..', '.env')
    env_path = os.path.abspath(env_path)
    env = {}
    if not os.path.exists(env_path):
        print(f"[WARN] .env not found at {env_path}")
        return env
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            env[k.strip()] = v.strip().strip('"\'')
    return env

ENV = load_env()
NASA_FIRMS_KEY = ENV.get('NASA_FIRMS_MAP_KEY')
TOMTOM_KEY     = ENV.get('MYTOMTOM_API_KEY')

# Test location: Islamabad G-10
TEST_LAT  = 33.684
TEST_LON  = 73.048
BBOX_DELTA = 0.1   # ±0.1° ≈ 11km × 11km (~121km²) — safely below TomTom 10,000km² limit

PASS = "✅ PASS"
FAIL = "❌ FAIL"
INFO = "ℹ️  INFO"

def section(title):
    print(f"\n{'='*62}")
    print(f"  {title}")
    print(f"{'='*62}")

def result(label, ok, detail=""):
    icon = PASS if ok else FAIL
    print(f"  {icon}  {label}")
    if detail:
        for line in detail.splitlines():
            print(f"         {line}")

def info(msg):
    for line in msg.splitlines():
        print(f"  {INFO}  {line}")

# ══════════════════════════════════════════════════════════════════════════════
# 1. NASA FIRMS
# ══════════════════════════════════════════════════════════════════════════════
def test_nasa_firms():
    section("NASA FIRMS — Thermal Anomaly API (VIIRS SNPP NRT)")

    if not NASA_FIRMS_KEY:
        result("API key loaded from .env", False, "NASA_FIRMS_MAP_KEY is missing in .env")
        return
    result("API key loaded from .env", True, f"Key: {NASA_FIRMS_KEY[:8]}…")

    # ── Test 1: Transaction check (correct endpoint) ──────────────────────────
    print("\n  [1] Checking remaining API transactions…")
    # The correct endpoint is /api/area/keycheck/<key> — returns plain text
    keycheck_url = f"https://firms.modaps.eosdis.nasa.gov/mapserver/mapkey_status/?MAP_KEY={NASA_FIRMS_KEY}"
    try:
        r = requests.get(keycheck_url, timeout=10)
        print(f"       HTTP {r.status_code}")
        body = r.text.strip()[:300]
        print(f"       Body: {body}")
        ok = r.status_code == 200
        result("Transaction check endpoint", ok, "" if ok else f"HTTP {r.status_code}")
    except Exception as e:
        result("Transaction check request", False, str(e))

    # ── Test 2: Area bounding box query (production use-case) ─────────────────
    print(f"\n  [2] Area bbox query (±{BBOX_DELTA}° ≈ 11×11km around Islamabad G-10)…")
    lon_min = round(TEST_LON - BBOX_DELTA, 4)
    lat_min = round(TEST_LAT - BBOX_DELTA, 4)
    lon_max = round(TEST_LON + BBOX_DELTA, 4)
    lat_max = round(TEST_LAT + BBOX_DELTA, 4)
    area_url = (
        f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/"
        f"{NASA_FIRMS_KEY}/VIIRS_SNPP_NRT/"
        f"{lon_min},{lat_min},{lon_max},{lat_max}/1"
    )
    print(f"       URL: {area_url}")
    try:
        r = requests.get(area_url, timeout=15)
        print(f"       HTTP {r.status_code}")
        if r.status_code == 200:
            lines = [l for l in r.text.strip().split("\n") if l.strip()]
            header    = lines[0] if lines else ""
            data_rows = max(0, len(lines) - 1)
            print(f"       CSV header : {header[:100]}")
            print(f"       Data rows  : {data_rows}  (0 = no active fires today — normal)")
            if data_rows > 0:
                print(f"       First row  : {lines[1][:120]}")
            result(f"Area query (VIIRS_SNPP_NRT) — {data_rows} fire point(s)", True)
        else:
            result("Area query", False, f"HTTP {r.status_code}\n{r.text[:300]}")
    except Exception as e:
        result("Area query request", False, str(e))

    # ── Test 3: Alternative sensor (MODIS NRT) ────────────────────────────────
    print(f"\n  [3] Same bbox using MODIS_NRT sensor (backup sensor)…")
    modis_url = (
        f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/"
        f"{NASA_FIRMS_KEY}/MODIS_NRT/"
        f"{lon_min},{lat_min},{lon_max},{lat_max}/1"
    )
    try:
        r = requests.get(modis_url, timeout=15)
        print(f"       HTTP {r.status_code}")
        if r.status_code == 200:
            lines = [l for l in r.text.strip().split("\n") if l.strip()]
            data_rows = max(0, len(lines) - 1)
            print(f"       Data rows : {data_rows}")
            result(f"MODIS_NRT query — {data_rows} fire point(s)", True)
        else:
            result("MODIS_NRT query", False, f"HTTP {r.status_code}: {r.text[:200]}")
    except Exception as e:
        result("MODIS_NRT request", False, str(e))

    # ── Test 4: Simulate a location with known past fires (Margalla Hills) ─────
    print(f"\n  [4] Wider 2-day query over Margalla Hills to sanity-check data presence…")
    margalla_url = (
        f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/"
        f"{NASA_FIRMS_KEY}/VIIRS_SNPP_NRT/"
        f"72.8,33.5,73.2,33.9/2"   # 2-day window, wider box
    )
    try:
        r = requests.get(margalla_url, timeout=15)
        print(f"       HTTP {r.status_code}")
        if r.status_code == 200:
            lines = [l for l in r.text.strip().split("\n") if l.strip()]
            data_rows = max(0, len(lines) - 1)
            print(f"       Data rows (last 2 days): {data_rows}")
            result(f"Margalla Hills 2-day query — {data_rows} fire point(s)", True,
                   "Fire data is available — API is healthy" if data_rows > 0 else "No fires in last 2 days (area is safe)")
        else:
            result("Margalla wider query", False, f"HTTP {r.status_code}: {r.text[:200]}")
    except Exception as e:
        result("Margalla wider request", False, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# 2. TomTom Traffic Incidents
# ══════════════════════════════════════════════════════════════════════════════
def test_tomtom():
    section("TomTom — Traffic Incidents API v5")

    if not TOMTOM_KEY:
        result("API key loaded from .env", False, "MYTOMTOM_API_KEY is missing in .env")
        return
    result("API key loaded from .env", True, f"Key: {TOMTOM_KEY[:8]}…")

    base_url = "https://api.tomtom.com/traffic/services/5/incidentDetails"
    lon_min = round(TEST_LON - BBOX_DELTA, 4)
    lat_min = round(TEST_LAT - BBOX_DELTA, 4)
    lon_max = round(TEST_LON + BBOX_DELTA, 4)
    lat_max = round(TEST_LAT + BBOX_DELTA, 4)
    bbox_str = f"{lon_min},{lat_min},{lon_max},{lat_max}"

    # ── Test 1: Auth + minimal fields ─────────────────────────────────────────
    print("\n  [1] Auth check — minimal fields request…")
    try:
        r = requests.get(base_url, params={
            "key": TOMTOM_KEY,
            "bbox": bbox_str,
            "fields": "{incidents{type,properties{iconCategory}}}",
            "language": "en-GB",
            "timeValidityFilter": "present"
        }, timeout=10)
        print(f"       HTTP {r.status_code}")
        print(f"       Response: {r.text[:200]}")
        ok = r.status_code == 200
        result("Auth + minimal query", ok, f"HTTP {r.status_code}: {r.text[:200]}" if not ok else "")
        if not ok:
            return
        count = len(r.json().get("incidents", []))
        result(f"Incidents in G-10 small bbox ({count} total)", True,
               "0 is normal for quiet residential area")
    except Exception as e:
        result("Minimal request", False, str(e))
        return

    # ── Test 2: Production-identical full fields request ───────────────────────
    print("\n  [2] Full production request (all fields, category filter 1,3,7,8,9,11)…")
    full_fields = "{incidents{type,properties{id,iconCategory,magnitudeOfDelay,events{description,iconCategory},from,to,roadNumbers,timeValidity}}}"
    try:
        r = requests.get(base_url, params={
            "key": TOMTOM_KEY,
            "bbox": bbox_str,
            "fields": full_fields,
            "language": "en-GB",
            "categoryFilter": "1,3,7,8,9,11",
            "timeValidityFilter": "present"
        }, timeout=10)
        print(f"       HTTP {r.status_code}")
        ok = r.status_code == 200
        result("Full production query", ok, f"HTTP {r.status_code}: {r.text[:200]}" if not ok else "")
        if ok:
            data = r.json()
            incidents = data.get("incidents", [])
            result(f"Parsed incidents: {len(incidents)} road incident(s)", True)
            for inc in incidents[:3]:
                props = inc.get("properties", {})
                evts  = props.get("events", [])
                desc  = evts[0].get("description", "no description") if evts else "no description"
                cat   = props.get("iconCategory", "?")
                frm   = props.get("from", "?")
                to    = props.get("to", "?")
                delay = props.get("magnitudeOfDelay", "?")
                print(f"         • [{cat}] {desc} | {frm} → {to} | delay={delay}")
    except Exception as e:
        result("Full production request", False, str(e))

    # ── Test 3: Wider bbox over Islamabad (safe size) ─────────────────────────
    # ±0.3° ≈ 33×33km ≈ ~1089km² — well within 10,000km² limit
    print("\n  [3] Wider bbox (±0.3°, ~33km×33km) to find any active incidents in Islamabad…")
    wide_bbox = f"{round(TEST_LON-0.3,4)},{round(TEST_LAT-0.3,4)},{round(TEST_LON+0.3,4)},{round(TEST_LAT+0.3,4)}"
    try:
        r = requests.get(base_url, params={
            "key": TOMTOM_KEY,
            "bbox": wide_bbox,
            "fields": "{incidents{type,properties{iconCategory,magnitudeOfDelay,events{description},from,to}}}",
            "language": "en-GB",
            "timeValidityFilter": "present"
        }, timeout=10)
        print(f"       HTTP {r.status_code}")
        ok = r.status_code == 200
        result(f"Wider Islamabad query", ok, f"HTTP {r.status_code}: {r.text[:200]}" if not ok else "")
        if ok:
            incidents = r.json().get("incidents", [])
            result(f"Incidents in greater Islamabad area: {len(incidents)}", True)
            for inc in incidents[:5]:
                props = inc.get("properties", {})
                evts  = props.get("events", [])
                desc  = evts[0].get("description", "—") if evts else "—"
                cat   = props.get("iconCategory", "?")
                frm   = props.get("from", "?")
                to    = props.get("to", "?")
                print(f"         • [{cat}] {desc} | {frm} → {to}")
            if not incidents:
                info("No active incidents in greater Islamabad — TomTom API is healthy, city is clear.")
    except Exception as e:
        result("Wider bbox request", False, str(e))

    # ── Test 4: All-category query (no filter) to see everything ──────────────
    print("\n  [4] All-category query (no categoryFilter) — shows everything TomTom sees…")
    try:
        r = requests.get(base_url, params={
            "key": TOMTOM_KEY,
            "bbox": wide_bbox,
            "fields": "{incidents{type,properties{iconCategory,events{description},from,to}}}",
            "language": "en-GB",
            "timeValidityFilter": "present"
        }, timeout=10)
        print(f"       HTTP {r.status_code}")
        if r.status_code == 200:
            incidents = r.json().get("incidents", [])
            by_cat = {}
            for inc in incidents:
                cat = inc.get("properties", {}).get("iconCategory", "Unknown")
                by_cat[cat] = by_cat.get(cat, 0) + 1
            result(f"Total incidents (all types): {len(incidents)}", True)
            for cat, cnt in sorted(by_cat.items(), key=lambda x: -x[1]):
                print(f"         • {cat}: {cnt}")
            if not incidents:
                info("City is clear of all tracked incidents at this moment.")
        else:
            result("All-category query", False, f"HTTP {r.status_code}: {r.text[:200]}")
    except Exception as e:
        result("All-category request", False, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("\n" + "="*62)
    print("  EXTERNAL API DIAGNOSTIC TOOL  v2")
    print("  APIs: NASA FIRMS Thermal  |  TomTom Traffic v5")
    print("  Location: Islamabad G-10 (33.684°N, 73.048°E)")
    print("="*62)

    test_nasa_firms()
    test_tomtom()

    print("\n" + "="*62)
    print("  Diagnostics complete.")
    print("  ✅ = working correctly")
    print("  ❌ = needs attention (see details above)")
    print("="*62 + "\n")
