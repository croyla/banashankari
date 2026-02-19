"""
Populates stop sequences in input/bus-stops.csv from BMTC API data.

Reads route numbers from the first column of bus-stops.csv, fetches stop
sequences via SearchRoute_v2 + SearchByRouteDetails_v4, and overwrites
the stops columns (column 2 onwards).

Route names in bus-stops.csv have no hyphens (e.g. 500A), while the BMTC
API uses hyphens (e.g. 500-A). The script handles this conversion.

Usage:
    python generate-bus-stops.py <stop_id1> [stop_id2 ...]

Example:
    python generate-bus-stops.py 20921 20922
"""

import csv
import json
import os
import sys
import hashlib
import sqlite3

import requests

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────

API_URL = 'https://bmtcmobileapi.karnataka.gov.in/WebAPI/'
CSV_PATH = 'input/bus-stops.csv'

REQUEST_HEADERS = {
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.5',
    'Content-Type': 'application/json',
    'lan': 'en',
    'deviceType': 'WEB',
    'Origin': 'https://bmtcwebportal.amnex.com',
    'Referer': 'https://bmtcwebportal.amnex.com/',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

CACHE_DB_PATH = 'api_cache.db'
CACHE_DURATION_HOURS = 24


# ──────────────────────────────────────────────
# SQLite Cache (shared with generate-geojson.py)
# ──────────────────────────────────────────────

def init_cache_db():
    conn = sqlite3.connect(CACHE_DB_PATH)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS api_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_hash TEXT UNIQUE NOT NULL,
            request_desc TEXT NOT NULL,
            response_data TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()


def get_cache_key(desc, request_data):
    return hashlib.md5(f"{desc}:{request_data}".encode()).hexdigest()


def get_cached_response(desc, request_data):
    try:
        conn = sqlite3.connect(CACHE_DB_PATH)
        cursor = conn.cursor()
        cache_key = get_cache_key(desc, request_data)
        cursor.execute(
            f"SELECT response_data FROM api_cache WHERE request_hash = ? AND created_at > datetime('now', '-{CACHE_DURATION_HOURS} hours')",
            (cache_key,)
        )
        result = cursor.fetchone()
        conn.close()
        return json.loads(result[0]) if result else None
    except Exception:
        return None


def store_cached_response(desc, request_data, response_data):
    try:
        conn = sqlite3.connect(CACHE_DB_PATH)
        cache_key = get_cache_key(desc, request_data)
        conn.execute(
            'INSERT OR REPLACE INTO api_cache (request_hash, request_desc, response_data, created_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)',
            (cache_key, desc, json.dumps(response_data))
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


# ──────────────────────────────────────────────
# Route number conversion
# ──────────────────────────────────────────────

def add_hyphens(route_number):
    """Convert CSV format to API format: '500A' -> '500-A', '238VM' -> '238-VM'."""
    i = 0
    while i < len(route_number) and route_number[i].isdigit():
        i += 1
    if i > 0 and i < len(route_number):
        return route_number[:i] + '-' + route_number[i:]
    return route_number


# ──────────────────────────────────────────────
# BMTC API calls
# ──────────────────────────────────────────────

def fetch_search_results(prefix):
    """Fetch SearchRoute_v2 results for a single-character prefix. Returns list of entries."""
    cache_desc = f'SearchRoute_v2_{prefix}'
    cached = get_cached_response(cache_desc, prefix)

    if cached is not None:
        return cached.get('data', [])

    try:
        resp = requests.post(
            f'{API_URL}SearchRoute_v2',
            headers=REQUEST_HEADERS,
            data=json.dumps({"routetext": prefix}),
            timeout=30
        )
        result = resp.json()
        store_cached_response(cache_desc, prefix, result)
        return result.get('data', [])
    except Exception as e:
        print(f'    SearchRoute_v2 error for prefix "{prefix}": {e}')
        return []


def fetch_route_parent_ids(route_api_names):
    """Batch-fetch routeparentids by grouping routes by first character.
    Returns dict: route_api_name -> routeparentid."""
    parent_ids = {}

    # Group by first character
    groups = {}
    for name in route_api_names:
        prefix = name[0] if name else ''
        if prefix:
            groups.setdefault(prefix, []).append(name)

    print(f'  Querying {len(groups)} prefix groups: {sorted(groups.keys())}')

    for prefix, names in groups.items():
        data = fetch_search_results(prefix)

        # Build lookup from API response
        api_lookup = {}
        for entry in data:
            rn = entry.get('routeno', '').upper()
            if rn not in api_lookup:
                api_lookup[rn] = entry['routeparentid']

        for name in names:
            search_text = name.split(' ')[0]
            # Exact match first
            if name.upper() in api_lookup:
                parent_ids[name] = api_lookup[name.upper()]
            else:
                # Prefix match fallback
                for entry in data:
                    if entry.get('routeno', '').upper().startswith(search_text.upper()):
                        parent_ids[name] = entry['routeparentid']
                        break

    return parent_ids


def fetch_stop_sequence(route_parent_id, stop_ids):
    """Use SearchByRouteDetails_v4 to get ordered stop names."""
    cache_desc = f'SearchByRouteDetails_v4_{route_parent_id}'
    cached = get_cached_response(cache_desc, str(route_parent_id))

    if cached is not None:
        result = cached
    else:
        try:
            resp = requests.post(
                f'{API_URL}SearchByRouteDetails_v4',
                headers=REQUEST_HEADERS,
                data=json.dumps({"routeid": route_parent_id, "servicetypeid": 0}),
                timeout=60
            )
            result = resp.json()
            store_cached_response(cache_desc, str(route_parent_id), result)
        except Exception:
            return []

    stop_ids_set = set(str(sid) for sid in stop_ids)

    # Pick direction starting from one of our stop IDs
    for direction in ['up', 'down']:
        data = result.get(direction, {}).get('data', [])
        if not data:
            continue
        if str(data[0].get('stationid', '')) in stop_ids_set:
            return [stop.get('stationname', '') for stop in data]

    # Fallback: UP
    up_data = result.get('up', {}).get('data', [])
    if up_data:
        return [stop.get('stationname', '') for stop in up_data]

    return []


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print('Usage: python generate-bus-stops.py <stop_id1> [stop_id2 ...]')
        print('Reads route numbers from input/bus-stops.csv and populates stops from BMTC API.')
        sys.exit(1)

    stop_ids = sys.argv[1:]
    print(f'Stop IDs: {stop_ids}')

    init_cache_db()

    # Read existing CSV
    rows = []
    with open(CSV_PATH, encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            rows.append(row)

    if not rows:
        print('ERROR: bus-stops.csv is empty')
        sys.exit(1)

    header = rows[0]
    route_rows = rows[1:]
    print(f'Found {len(route_rows)} routes in {CSV_PATH}')

    # Batch-fetch all route parent IDs with optimised prefix queries
    route_api_names = []
    for row in route_rows:
        route_csv = row[0].strip()
        if route_csv:
            route_api_names.append(add_hyphens(route_csv))

    print(f'Fetching parent IDs for {len(route_api_names)} routes...')
    parent_ids = fetch_route_parent_ids(route_api_names)
    print(f'  Found parent IDs for {len(parent_ids)}/{len(route_api_names)} routes')

    # Process each route
    updated_rows = []
    max_cols = len(header)
    failed = []
    succeeded = 0

    for row in route_rows:
        route_csv = row[0].strip()
        if not route_csv:
            updated_rows.append(row)
            continue

        route_api = add_hyphens(route_csv)
        print(f'  {route_csv} (API: {route_api})...', end=' ')

        # Get parent ID from batch results
        parent_id = parent_ids.get(route_api)
        if parent_id is None:
            print('no parent ID found')
            failed.append(route_csv)
            updated_rows.append(row)
            continue

        # Get stops
        stops = fetch_stop_sequence(parent_id, stop_ids)
        if not stops:
            print(f'no stops (parent={parent_id})')
            failed.append(route_csv)
            updated_rows.append(row)
            continue

        # Build new row: route number + stops, padded to max_cols
        new_row = [route_csv] + stops
        if len(new_row) < max_cols:
            new_row += [''] * (max_cols - len(new_row))
        elif len(new_row) > max_cols:
            max_cols = len(new_row)

        updated_rows.append(new_row)
        succeeded += 1
        print(f'{len(stops)} stops')

    # Pad header and all rows to max_cols
    if len(header) < max_cols:
        header += [''] * (max_cols - len(header))
    for i, row in enumerate(updated_rows):
        if len(row) < max_cols:
            updated_rows[i] = row + [''] * (max_cols - len(row))

    # Write back
    with open(CSV_PATH, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for row in updated_rows:
            writer.writerow(row)

    print(f'\nUpdated {succeeded}/{len(route_rows)} routes in {CSV_PATH}')
    if failed:
        print(f'Failed ({len(failed)}): {", ".join(failed)}')

    print('Done')


if __name__ == '__main__':
    main()
