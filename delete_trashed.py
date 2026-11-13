#!/usr/bin/env python3
"""
immich-trash-purge
Permanently delete trashed assets from Immich internal uploads or external libraries
by matching a specific originalPath directory prefix.

Author: imShaikhAR
License: MIT
"""

import argparse
import csv
import json
import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

# ── CONFIG (from .env or edit directly) ─────────────────────────────────────
IMMICH_URL  = os.getenv("IMMICH_URL", "http://localhost:2283").rstrip("/")
API_KEY     = os.getenv("IMMICH_API_KEY", "")
PATH_PREFIX = os.getenv("PATH_PREFIX", "/your/library/folder/")
DRY_RUN     = os.getenv("DRY_RUN", "true").lower() == "true"
BATCH_SIZE  = int(os.getenv("BATCH_SIZE", "100"))
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "30"))
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
            r = session.request(method, url, timeout=REQUEST_TIMEOUT, **kwargs)
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


def search_trashed_assets(path_prefix: str, matches: list = None) -> list:
    """
    Return IDs of trashed assets under the specified originalPath directory.
    Immich search is a substring match, so locally verify exact directory boundaries.
    Optional matches collects IDs and paths for report output.
    """
    directory_prefix = path_prefix.rstrip("/") + "/"
    ids = []
    page = 1

    while True:
        data = request("POST", "/search/metadata", json={
            "withDeleted": True,
            "trashedAfter": "2000-01-01T00:00:00.000Z",
            "originalPath": directory_prefix,
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
            original_path = asset.get("originalPath") or ""
            if not original_path.startswith(directory_prefix):
                continue
            ids.append(asset["id"])
            if matches is not None:
                matches.append({"id": asset["id"], "originalPath": original_path, "status": "selected"})
            print(f"  [{asset['id'][:8]}...] {original_path}")

        # nextPage is None when no further pages exist
        if data.get("assets", {}).get("nextPage") is None:
            break

        page += 1

    return ids


def delete_assets(ids: list, matches: list = None):
    """Request permanent deletion of UUIDs, recording API outcomes if requested."""
    if not ids:
        print("\nNo matching trashed assets found.")
        return

    total = len(ids)
    print(f"\n{'[DRY RUN] Would permanently delete' if DRY_RUN else 'Permanently deleting'} {total} asset(s)...")

    if DRY_RUN:
        print("[DRY RUN] Use --delete or set DRY_RUN=false in .env to perform actual deletion.")
        return

    deleted_so_far = 0
    for i in range(0, total, BATCH_SIZE):
        batch = ids[i:i + BATCH_SIZE]
        result = request("DELETE", "/assets", json={"force": True, "ids": batch})
        if matches is not None:
            status = "request_accepted" if result is not None else "request_unconfirmed"
            for asset in matches[i:i + BATCH_SIZE]:
                asset["status"] = status
        if result is not None:
            deleted_so_far += len(batch)
            print(f"  ✅ Deleted {deleted_so_far} / {total}")
        else:
            print(f"  ❌ Batch failed at offset {i} — {len(batch)} assets not deleted")


def build_parser():
    parser = argparse.ArgumentParser(description="Purge trashed Immich assets under one originalPath directory.")
    parser.add_argument("--path", default=PATH_PREFIX, help="Directory prefix (defaults to PATH_PREFIX in .env)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", dest="dry_run", action="store_true", help="List matches without deleting")
    mode.add_argument("--delete", dest="dry_run", action="store_false", help="Delete matches after confirmation")
    parser.set_defaults(dry_run=DRY_RUN)
    parser.add_argument("--timeout", type=float, default=REQUEST_TIMEOUT,
                        help="Timeout in seconds for each Immich API request (default: REQUEST_TIMEOUT or 30)")
    parser.add_argument("--report-json", metavar="FILE", help="Write matched assets and outcomes as JSON")
    parser.add_argument("--report-csv", metavar="FILE", help="Write matched assets and outcomes as CSV")
    return parser


def write_reports(args, matches):
    """Write optional local reports; no API key is included."""
    try:
        if args.report_json:
            with open(args.report_json, "w", encoding="utf-8") as file:
                json.dump({
                    "server": IMMICH_URL,
                    "path_prefix": args.path,
                    "mode": "dry_run" if DRY_RUN else "delete",
                    "total_matches": len(matches),
                    "assets": matches,
                }, file, indent=2, ensure_ascii=False)
                file.write("\n")
            print(f"JSON report saved: {args.report_json}")
        if args.report_csv:
            with open(args.report_csv, "w", encoding="utf-8", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=["id", "originalPath", "status"])
                writer.writeheader()
                writer.writerows(matches)
            print(f"CSV report saved: {args.report_csv}")
    except OSError as error:
        raise SystemExit(f"Error writing report: {error}") from error


def main():
    global DRY_RUN, REQUEST_TIMEOUT
    parser = build_parser()
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be greater than zero")
    DRY_RUN, REQUEST_TIMEOUT = args.dry_run, args.timeout

    if not API_KEY:
        print("Error: IMMICH_API_KEY is not set. Copy .env.example to .env and fill it in.")
        return

    print(f"\n{'='*60}")
    print(f"  immich-trash-purge")
    print(f"  Mode:   {'DRY RUN (no changes)' if DRY_RUN else '⚠️  LIVE (will DELETE)'}")
    print(f"  Server: {IMMICH_URL}")
    print(f"  Path:   {args.path}")
    print(f"{'='*60}\n")

    if not test_connection():
        return

    print(f"\nSearching for trashed assets under: {args.path}\n")
    matches = []
    matched_ids = search_trashed_assets(args.path, matches)
    print(f"\nTotal matched: {len(matched_ids)}")

    if not matched_ids:
        write_reports(args, matches)
        return

    if not DRY_RUN:
        confirm = input("\nType 'yes' to permanently delete these assets: ").strip().lower()
        if confirm not in ("yes", "y"):
            for asset in matches:
                asset["status"] = "aborted"
            write_reports(args, matches)
            print("Aborted.")
            return
    else:
        for asset in matches:
            asset["status"] = "dry_run"

    delete_assets(matched_ids, matches)
    write_reports(args, matches)
    print("\nDone.")


if __name__ == "__main__":
    main()
