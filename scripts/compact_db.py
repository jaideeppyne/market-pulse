#!/usr/bin/env python3
"""One-time compaction/migration for scan_snapshots bloat.

Rewrites every existing ``scan_snapshots.payload`` JSON into the slim form
(``app.db.slim_snapshot_payload``): keeps scalars + metrics + id/status/points
factors, drops the per-row sparkline and the static factor labels/descriptions.
Then enables ``auto_vacuum=INCREMENTAL`` and runs a one-time full VACUUM so the
existing oversized DB file actually shrinks on disk.

SAFETY: always test on a COPY first. Run with --dry-run to preview, or point
--db at a copied file. Example:

    cp data/market_pulse.db /tmp/mp_copy.db
    python3 scripts/compact_db.py --db /tmp/mp_copy.db

Then compare before/after sizes printed by the script.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

# Make ``app`` importable when run from anywhere in the repo.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import slim_snapshot_payload  # noqa: E402


def _size_mb(path: Path) -> float:
    return path.stat().st_size / (1024 * 1024) if path.exists() else 0.0


def compact(db_path: Path, dry_run: bool = False, batch: int = 2000) -> dict:
    if not db_path.exists():
        raise FileNotFoundError(db_path)

    before_mb = _size_mb(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    total = cur.execute("SELECT COUNT(*) FROM scan_snapshots").fetchone()[0]
    rewritten = 0
    bytes_before = 0
    bytes_after = 0
    failed = 0

    # Stream in batches by id to avoid loading 887 MB into memory at once.
    last_id = -1
    while True:
        rows = cur.execute(
            "SELECT id, payload FROM scan_snapshots WHERE id > ? ORDER BY id LIMIT ?",
            (last_id, batch),
        ).fetchall()
        if not rows:
            break
        updates = []
        for r in rows:
            last_id = r["id"]
            raw = r["payload"] or "{}"
            bytes_before += len(raw)
            try:
                payload = json.loads(raw)
            except Exception:
                failed += 1
                bytes_after += len(raw)
                continue
            slim = slim_snapshot_payload(payload)
            new_raw = json.dumps(slim, separators=(",", ":"))
            bytes_after += len(new_raw)
            if new_raw != raw:
                updates.append((new_raw, r["id"]))
        if updates and not dry_run:
            conn.executemany(
                "UPDATE scan_snapshots SET payload = ? WHERE id = ?", updates
            )
            conn.commit()
            rewritten += len(updates)

    result = {
        "rows_total": total,
        "rows_rewritten": rewritten,
        "rows_failed_parse": failed,
        "payload_bytes_before": bytes_before,
        "payload_bytes_after": bytes_after,
        "payload_shrink_pct": round((1 - bytes_after / bytes_before) * 100, 1)
        if bytes_before
        else 0.0,
        "db_size_mb_before": round(before_mb, 2),
    }

    if not dry_run:
        # Switch to incremental auto_vacuum and do the one-time full rewrite so the
        # file on disk actually shrinks (and future cleanups can use incremental).
        conn.execute("PRAGMA auto_vacuum=INCREMENTAL")
        conn.commit()
        conn.execute("VACUUM")
        conn.commit()

    conn.close()
    result["db_size_mb_after"] = round(_size_mb(db_path), 2)
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    default_db = os.getenv("DB_PATH", str(ROOT / "data" / "market_pulse.db"))
    ap.add_argument("--db", default=default_db, help="Path to SQLite DB (use a COPY!)")
    ap.add_argument("--dry-run", action="store_true", help="Compute sizes, do not write/VACUUM")
    args = ap.parse_args()

    db_path = Path(args.db)
    print(f"Compacting: {db_path}  (dry_run={args.dry_run})")
    res = compact(db_path, dry_run=args.dry_run)
    print(json.dumps(res, indent=2))
    if not args.dry_run:
        print(
            f"\nDB size: {res['db_size_mb_before']} MB -> {res['db_size_mb_after']} MB "
            f"(payload JSON shrunk {res['payload_shrink_pct']}%)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
