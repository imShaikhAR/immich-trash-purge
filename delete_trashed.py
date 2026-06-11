#!/usr/bin/env python3
"""
immich-trash-purge
Permanently delete trashed assets from Immich external libraries
by matching a specific originalPath prefix.

Author: imShaikhAR
License: MIT
"""

import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

# ── CONFIG (from .env or edit directly) ─────────────────────────────────────
IMMICH_URL  = os.getenv("IMMICH_URL", "http://localhost:2283").rstrip("/")
API_KEY     = os.getenv("IMMICH_API_KEY", "")
PATH_PREFIX = os.getenv("PATH_PREFIX", "/your/external/library/path/")
DRY_RUN     = os.getenv("DRY_RUN", "true").lower() == "true"
BATCH_SIZE  = int(os.getenv("BATCH_SIZE", "100"))
# ────────────────────────────────────────────────────────────────────────────

session = requests.Session()
session.headers.update({
    "x-api-key": API_KEY,
    "Content-Type": "application/json",
    "Accept": "application/json",
})


def request(method: str, endpoint: str, retries: int = 3, **kwargs):
    """Make an API request with exponential backoff retry."""
    url = f"{IMMICH_URL}/api{endpoint}"
    for attempt in range(1, retries + 1):
        try:
            r = session.request(method, url, **kwargs)
            r.raise_for_status()
            return r.json() if r.content else {}
        except requests.exceptions.RequestException as e:
            print(f"  Attempt {attempt}/{retries} failed: {e}")
            if attempt < retries:
                time.sleep(2 ** attempt)
    return None


def test_connection() -> bool:
    """Verify API key and connectivity."""
    result = request("GET", "/users/me")
    if result:
        print(f"✅ Connected as: {result.get('email', 'unknown')}")
        return True
    print("❌ Connection failed. Check IMMICH_URL and IMMICH_API_KEY.")
    return False


def search_trashed_assets(path_prefix: str) -> list:
    """
    Return IDs of all trashed assets whose originalPath starts with path_prefix.
    Uses POST /api/search/metadata with withDeleted=True.
    """
    ids = []
    page = 1

    while True:
        data = request("POST", "/search/metadata", json={
            "withDeleted": True,
            "trashedAfter": "2000-01-01T00:00:00.000Z",
            "originalPath": path_prefix,
            "page": page,
            "size": BATCH_SIZE,
        })

        if not data:
            print("  Warning: empty or failed response from search API.")
            break

        items = data.get("assets", {}).get("items", [])
        if not items:
            break

        for asset in items:
            ids.append(asset["id"])
            print(f"  [{asset['id'][:8]}...] {asset.get('originalPath', 'N/A')}")

        # nextPage is None when no further pages exist
        if data.get("assets", {}).get("nextPage") is None:
            break

        page += 1

    return ids


def delete_assets(ids: list):
    """Permanently delete assets by UUID list (bypasses trash)."""
    if not ids:
        print("\nNo matching trashed assets found.")
        return

    print(f"\n{'[DRY RUN] Would permanently delete' if DRY_RUN else 'Permanently deleting'} {len(ids)} asset(s)...")

    if DRY_RUN:
        print("[DRY RUN] Set DRY_RUN=false in .env to perform actual deletion.")
        return

    for i in range(0, len(ids), BATCH_SIZE):
        batch = ids[i:i + BATCH_SIZE]
        result = request("DELETE", "/assets", json={"force": True, "ids": batch})
        if result is not None:
            print(f"  ✅ Batch {i // BATCH_SIZE + 1}: deleted {len(batch)} assets")
        else:
            print(f"  ❌ Batch {i // BATCH_SIZE + 1}: FAILED — check logs")


def main():
    if not API_KEY:
        print("Error: IMMICH_API_KEY is not set. Copy .env.example to .env and fill it in.")
        return

    print(f"\n{'='*60}")
    print(f"  immich-trash-purge")
    print(f"  Mode:   {'DRY RUN (no changes)' if DRY_RUN else '⚠️  LIVE (will DELETE)'}")
    print(f"  Server: {IMMICH_URL}")
    print(f"  Path:   {PATH_PREFIX}")
    print(f"{'='*60}\n")

    if not test_connection():
        return

    print(f"\nSearching for trashed assets under: {PATH_PREFIX}\n")
    matched_ids = search_trashed_assets(PATH_PREFIX)
    print(f"\nTotal matched: {len(matched_ids)}")

    if not matched_ids:
        return

    if not DRY_RUN:
        confirm = input("\nType 'yes' to permanently delete these assets: ").strip().lower()
        if confirm not in ("yes", "y"):
            print("Aborted.")
            return

    delete_assets(matched_ids)
    print("\nDone.")


if __name__ == "__main__":
    main()
