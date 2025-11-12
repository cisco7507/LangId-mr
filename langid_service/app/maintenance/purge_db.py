# app/maintenance/purge_db.py
import argparse
import datetime as dt
import logging
import pathlib
import sqlite3
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]  # repo root
DB_PATH = ROOT / "langid.sqlite"
STORAGE_DIR = ROOT / "storage"

log = logging.getLogger("purge_db")
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")


def connect(db_path: pathlib.Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    # Pragmas tuned for maintenance
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def cutoff_iso(days: int) -> str:
    # Use timezone-aware UTC per deprecation warnings
    return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")


def pick_timestamp_column(conn: sqlite3.Connection) -> str:
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(jobs)").fetchall()}
    for c in ("finished_at", "updated_at", "created_at"):
        if c in cols:
            return c
    # Fallback if schema is unexpected; treat all as old to avoid getting stuck
    return "created_at"


def purge_jobs(conn: sqlite3.Connection, keep_days: int, batch_size: int) -> int:
    """
    Portable batched purge:
      1) SELECT ids of old succeeded/failed jobs
      2) DELETE FROM jobs WHERE id IN (…) in batches
    """
    ts_col = pick_timestamp_column(conn)
    cutoff = cutoff_iso(keep_days)
    total_deleted = 0

    sel_sql = f"""
      SELECT id
      FROM jobs
      WHERE status IN ('succeeded','failed')
        AND {ts_col} IS NOT NULL
        AND {ts_col} < ?
    """

    ids = [row["id"] for row in conn.execute(sel_sql, (cutoff,))]

    for i in range(0, len(ids), batch_size):
        batch_ids = ids[i:i + batch_size]
        placeholders = ",".join("?" for _ in batch_ids)
        del_sql = f"DELETE FROM jobs WHERE id IN ({placeholders})"
        cur = conn.execute(del_sql, batch_ids)
        conn.commit()
        total_deleted += cur.rowcount or 0

    return total_deleted


def fetch_known_ids(conn: sqlite3.Connection) -> set[str]:
    # If the table is large and you only need this for orphan files,
    # it’s fine—purge keeps the table small. Otherwise, consider streaming.
    return {r["id"] for r in conn.execute("SELECT id FROM jobs")}


def purge_orphan_files(known_ids: set[str], older_than_days: int) -> tuple[int, int]:
    """
    Remove files under storage that don't map to any job id
    or are older than retention.
    """
    removed = 0
    scanned = 0
    cutoff_dt = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=older_than_days)

    def maybe_rm(p: pathlib.Path):
        nonlocal removed, scanned
        if not p.is_file():
            return
        scanned += 1
        name = p.name
        job_id = name.split(".")[0]  # files are typically <jobid>.* or <jobid>
        try:
            mtime = dt.datetime.fromtimestamp(p.stat().st_mtime, tz=dt.timezone.utc)
        except Exception:
            mtime = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)
        if job_id not in known_ids or mtime < cutoff_dt:
            try:
                p.unlink()
                removed += 1
            except Exception:
                pass

    if STORAGE_DIR.exists():
        for p in STORAGE_DIR.iterdir():
            maybe_rm(p)

    return removed, scanned


def maybe_prepare_indexes(conn: sqlite3.Connection):
    # Safe to re-run; speeds up selection
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);")
        for col in ("finished_at", "updated_at", "created_at"):
            try:
                conn.execute(f"CREATE INDEX IF NOT EXISTS idx_jobs_{col} ON jobs({col});")
            except sqlite3.OperationalError:
                pass
        conn.commit()
    except Exception:
        pass


def maybe_vacuum(conn: sqlite3.Connection, vacuum: bool):
    if vacuum:
        conn.execute("PRAGMA optimize;")
        conn.execute("VACUUM;")
        conn.commit()


def main():
    ap = argparse.ArgumentParser(description="Purge old jobs and orphaned files.")
    ap.add_argument("--keep-days", type=int, default=30, help="Keep jobs newer than N days (default: 30).")
    ap.add_argument("--batch", type=int, default=2000, help="Delete in batches of N (default: 2000).")
    ap.add_argument("--vacuum", action="store_true", help="Run VACUUM after purge.")
    ap.add_argument("--purge-files", action="store_true", help="Also remove orphan/old files from storage.")
    args = ap.parse_args()

    if not DB_PATH.exists():
        log.error(f"Database not found at {DB_PATH}")
        sys.exit(1)

    conn = connect(DB_PATH)
    try:
        maybe_prepare_indexes(conn)
        deleted_jobs = purge_jobs(conn, args.keep_days, args.batch)
        log.info(f"Deleted jobs: {deleted_jobs}")

        deleted_files = 0
        if args.purge_files:
            known = fetch_known_ids(conn)
            deleted_files, scanned_files = purge_orphan_files(known, args.keep_days)
            log.info(f"Files scanned: {scanned_files}  removed: {deleted_files}")

        maybe_vacuum(conn, args.vacuum)
        log.info("Purge complete.")
        print(f"Deleted jobs: {deleted_jobs}")
        print(f"Deleted files: {deleted_files}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
