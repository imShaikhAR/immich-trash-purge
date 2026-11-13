# immich-trash-purge

Permanently delete trashed assets from [Immich](https://immich.app) **internal uploads and external libraries** by matching a specific `originalPath` directory prefix.

Supports trashed internal uploads (including storage-template locations) and external-library assets. It is also useful when files have been deleted from disk in an external library, Immich has moved them to Trash on rescan, but **Empty Trash** doesn't work for externally-removed assets (a [known Immich bug](https://github.com/immich-app/immich/issues/26601)).

---

## How It Works

1. Calls `POST /api/search/metadata` with `withDeleted: true` and a trash-date filter to search for assets under your path
2. Checks that each returned `originalPath` begins with the exact directory prefix, then displays the matches for review
3. Calls `DELETE /api/assets` with `force: true` to request permanent deletion through Immich

**Deletion affects both the database and filesystem.** Immich removes associated files (including original files still on disk when applicable) as part of its permanent-deletion processing. This is expected and irreversible.

---

## Requirements

- Python 3.8+
- Immich instance (any recent version)
- An Immich API key with asset read/delete permissions

---

## Installation

```bash
git clone https://github.com/imShaikhAR/immich-trash-purge.git
cd immich-trash-purge
```

It is recommended to use a virtual environment to keep dependencies isolated:

```bash
python3 -m venv .venv
source .venv/bin/activate        # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Or without a venv (installs globally):

```bash
pip install -r requirements.txt
```

---

## Configuration

Copy the example env file and fill in your values:

```bash
cp .env.example .env
```

Then edit `.env`:

```env
# Your Immich server URL — do NOT include /api
IMMICH_URL=http://localhost:2283

# API key: Immich Web UI → Account Settings → API Keys → New Key
IMMICH_API_KEY=your_api_key_here

# Directory prefix for internal uploads OR external libraries
# Use the path stored in Immich's originalPath, not necessarily the host path
# A trailing slash is optional; similarly named sibling folders are excluded
PATH_PREFIX=/mnt/nas/photos/old-folder/

# Always start with DRY_RUN=true to verify before deleting
DRY_RUN=true

# Batch size for API calls (max 100)
BATCH_SIZE=100
```

> **How to find the right PATH_PREFIX:**  
> In the Immich web UI, go to Trash, open any affected asset, and look at the file path shown in its details panel. Copy the folder portion as your `PATH_PREFIX`.

For example, internal paths may be under `/data/upload/` or `/data/library/`, while an external library might use `/mnt/nas/photos/`. The actual path varies by installation. Matching is **case-sensitive** and requires a directory boundary: `/photos/old/` will not select `/photos/old-copy/` or `/archive/photos/old/`.

---

## Usage

### Step 1 — Dry Run (always do this first)

With `DRY_RUN=true` (the default), the script will list all matching assets **without deleting anything**:

```bash
python delete_trashed.py
```

Example output:

```
============================================================
  immich-trash-purge
  Mode:   DRY RUN (no changes)
  Server: http://localhost:2283
  Path:   /mnt/nas/photos/old-folder/
============================================================

✅ Connected as: admin@example.com

Searching for trashed assets under: /mnt/nas/photos/old-folder/

  [a1b2c3d4...] /mnt/nas/photos/old-folder/IMG_0001.jpg
  [e5f6g7h8...] /mnt/nas/photos/old-folder/IMG_0002.mp4
  ...

Total matched: 47

[DRY RUN] Set DRY_RUN=false in .env to perform actual deletion.
```

### Step 2 — Review the list

Verify the matched paths look correct. Make sure `PATH_PREFIX` is specific enough that you won't accidentally match assets you want to keep.

### Step 3 — Live deletion

Set `DRY_RUN=false` in your `.env`, then re-run:

```bash
python delete_trashed.py
```

The script will ask for confirmation before deleting:

```
Type 'yes' to permanently delete these assets: yes

  ✅ Batch 1: deleted 47 assets

Done.
```

---

## Notes

- **Internal and external libraries** — both are supported; selection is based on the configured `originalPath` directory, not library type.
- **Database and files** — Immich's permanent-deletion process removes database records and associated files, including original media still on disk when applicable.
- **Strict directory matching** — the script checks results locally because Immich's search API can return substring matches outside the requested folder.
- **`force: true`** — requests permanent deletion without another trash/restore step; Immich processes the deletion jobs asynchronously.
- **Pagination** — the script handles large trash bins automatically, fetching 100 assets per page.
- **IMMICH_URL** — do not include `/api` at the end. The script appends it automatically.

---

## Related

- [immich-video-replace](https://github.com/imShaikhAR/immich-video-replace) — replace lower-quality videos in Immich with transcoded versions
- [Immich External Libraries docs](https://docs.immich.app/features/libraries)
- [Immich API Reference](https://api.immich.app)

---

## License

MIT
