"""
One-time migration: Neon PostgreSQL → local SQLite (qc_dashboard.db)

Run:  python3 migrate_pg_to_sqlite.py
"""
import os
import sqlite3
import sys

# Load .env manually (no dotenv dependency required)
env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
    for line in open(env_path):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

DATABASE_URL = os.environ.get("DATABASE_URL", "")
SQLITE_PATH = os.environ.get("SQLITE_PATH", "qc_dashboard.db")

if not DATABASE_URL:
    sys.exit("DATABASE_URL not set — check your .env file.")

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    sys.exit("psycopg2 not installed. Run: pip install psycopg2-binary")

TABLES = [
    "users",
    "supervisors",
    "interviewers",
    "projects",
    "project_assignments",
    "upload_log",
    "quality_report_records",
    "backcheck_records",
    "listen_in_records",
    "performance_records",
    "timing_records",
    "cancelled_interview_records",
    "interviewer_actions",
]

# ── Step 1: Init SQLite schema ────────────────────────────────────────────────
print("Initialising SQLite schema…")
# Temporarily unset DATABASE_URL so shared_db uses SQLite
_orig = os.environ.pop("DATABASE_URL", None)
import shared_db
shared_db.init_tables()
if _orig:
    os.environ["DATABASE_URL"] = _orig
print("  Schema ready.\n")

# ── Step 2: Connect to PostgreSQL ─────────────────────────────────────────────
print("Connecting to Neon PostgreSQL…")
pg = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
pg.autocommit = True
pgc = pg.cursor()
print("  Connected.\n")

# ── Step 3: Open SQLite ───────────────────────────────────────────────────────
lite = sqlite3.connect(SQLITE_PATH)
lite.row_factory = sqlite3.Row
lite.execute("PRAGMA journal_mode=WAL")
lite.execute("PRAGMA foreign_keys=OFF")   # skip FK checks during bulk insert

# ── Helper ────────────────────────────────────────────────────────────────────

def migrate_table(table: str):
    pgc.execute(f"SELECT * FROM {table} ORDER BY id")
    rows = pgc.fetchall()
    if not rows:
        print(f"  {table}: 0 rows (skipped)")
        return

    # Get column names from the first row
    cols = list(rows[0].keys())
    placeholders = ",".join(["?"] * len(cols))
    col_list = ",".join(cols)

    # DELETE existing rows in SQLite so re-running is safe
    lite.execute(f"DELETE FROM {table}")

    inserted = 0
    for row in rows:
        values = []
        for c in cols:
            v = row[c]
            # Convert lists/dicts to strings (shouldn't happen, but guard)
            if isinstance(v, (list, dict)):
                import json
                v = json.dumps(v)
            # PostgreSQL booleans → SQLite integers
            elif isinstance(v, bool):
                v = int(v)
            values.append(v)
        try:
            lite.execute(
                f"INSERT OR REPLACE INTO {table} ({col_list}) VALUES ({placeholders})",
                values,
            )
            inserted += 1
        except Exception as e:
            print(f"    ⚠  Row skipped in {table}: {e}")

    lite.commit()
    print(f"  {table}: {inserted} rows migrated")


# ── Step 4: Migrate each table ────────────────────────────────────────────────
print("Migrating tables…")
for table in TABLES:
    try:
        pgc.execute(
            "SELECT COUNT(*) AS cnt FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name=%s",
            (table,),
        )
        row = pgc.fetchone()
        if not row or (row.get("cnt") or 0) == 0:
            print(f"  {table}: not found in PostgreSQL (skipped)")
            continue
        migrate_table(table)
    except Exception as e:
        print(f"  {table}: ERROR — {e}")

# ── Step 5: Re-enable FK, close ──────────────────────────────────────────────
lite.execute("PRAGMA foreign_keys=ON")
lite.close()
pg.close()

print("\nMigration complete. Local SQLite is ready at:", SQLITE_PATH)
