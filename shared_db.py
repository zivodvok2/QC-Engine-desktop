"""
Read/write access to the dashboard's database.
Supports PostgreSQL (production) and SQLite (local demo via SQLITE_PATH env var
or when DATABASE_URL is not set).
"""
import json
import os
import re
import uuid
from typing import Optional

DATABASE_URL = os.environ.get("DATABASE_URL", "")
_USE_SQLITE = not bool(DATABASE_URL)
_SQLITE_PATH = os.environ.get("SQLITE_PATH", "qc_dashboard.db")

# ── SQLite adapter ─────────────────────────────────────────────────────────────

def _pg_to_sqlite(sql: str) -> str:
    """Translate PostgreSQL SQL syntax to SQLite."""
    sql = sql.replace("%s", "?")
    sql = re.sub(r"::\w+", "", sql)
    sql = sql.replace("SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT")
    sql = re.sub(r"\s+RETURNING\s+\w+", "", sql, flags=re.IGNORECASE)
    if "ON CONFLICT DO NOTHING" in sql:
        sql = sql.replace(" ON CONFLICT DO NOTHING", "")
        sql = re.sub(r"\bINSERT\s+INTO\b", "INSERT OR IGNORE INTO", sql, count=1, flags=re.IGNORECASE)
    sql = sql.replace("NOW()", "CURRENT_TIMESTAMP")
    return sql


class _SQLiteCursor:
    def __init__(self, cur: "sqlite3.Cursor", is_insert: bool = False):
        self._cur = cur
        self._lastrowid = cur.lastrowid
        self._is_insert = is_insert

    def fetchone(self) -> Optional[dict]:
        if self._is_insert:
            row = self._cur.fetchone()
            if row is None:
                return {"id": self._lastrowid} if self._lastrowid else None
            return dict(row)
        row = self._cur.fetchone()
        return dict(row) if row else None

    def fetchall(self) -> list:
        return [dict(r) for r in self._cur.fetchall()]


_sqlite_connection = None

def _get_sqlite_conn():
    global _sqlite_connection
    if _sqlite_connection is None:
        import sqlite3
        _sqlite_connection = sqlite3.connect(_SQLITE_PATH, check_same_thread=False)
        _sqlite_connection.row_factory = sqlite3.Row
        _sqlite_connection.execute("PRAGMA journal_mode=WAL")
    return _sqlite_connection


class _SQLiteConn:
    def __init__(self):
        self._conn = _get_sqlite_conn()

    def execute(self, sql: str, params=None):
        adapted = _pg_to_sqlite(sql)
        is_insert = adapted.strip().upper().startswith("INSERT")
        # Expand ANY(?) → IN (?,?,...)
        if params and "ANY(?)" in adapted:
            new_params = list(params)
            for i, p in enumerate(new_params):
                if isinstance(p, (list, tuple)):
                    placeholders = ",".join(["?"] * len(p))
                    adapted = adapted.replace("= ANY(?)", f"IN ({placeholders})", 1)
                    new_params = new_params[:i] + list(p) + new_params[i + 1:]
                    break
            params = tuple(new_params)
        cur = self._conn.cursor()
        cur.execute(adapted, params or ())
        return _SQLiteCursor(cur, is_insert)

    def commit(self):
        self._conn.commit()

    def close(self):
        pass  # Reuse the global connection


# ── PostgreSQL adapter ─────────────────────────────────────────────────────────

if not _USE_SQLITE:
    import psycopg2
    import psycopg2.errors
    import psycopg2.extras
    from psycopg2 import pool as pg_pool

    _pool: "pg_pool.ThreadedConnectionPool | None" = None

    def _get_pool() -> "pg_pool.ThreadedConnectionPool":
        global _pool
        if _pool is None:
            _pool = pg_pool.ThreadedConnectionPool(1, 10, DATABASE_URL)
        return _pool


class _PGConn:
    def __init__(self):
        self._conn = _get_pool().getconn()

    def execute(self, sql: str, params=None):
        cur = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, params)
        return cur

    def commit(self):
        self._conn.commit()

    def close(self):
        _get_pool().putconn(self._conn)


def get_conn():
    return _SQLiteConn() if _USE_SQLITE else _PGConn()


def db_available() -> bool:
    return True


# ── Internal helpers ───────────────────────────────────────────────────────────

def _safe_add_column(conn, table: str, column: str, col_type: str):
    """Add a column if it doesn't already exist. Safe to call repeatedly."""
    try:
        conn.execute(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {col_type}"
        )
        conn.commit()
    except Exception:
        pass


def _log_upload(conn, upload_id, project_id, report_type, uploaded_by, filename, row_count, wave_label=None):
    conn.execute(
        """INSERT INTO upload_log (upload_id, project_id, report_type, uploaded_by, filename, row_count, wave_label)
           VALUES (%s,%s,%s,%s,%s,%s,%s)""",
        (upload_id, project_id, report_type, uploaded_by, filename, row_count, wave_label or None),
    )


# ── Users ──────────────────────────────────────────────────────────────────────

def get_user_by_email(email: str) -> Optional[dict]:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM users WHERE email=%s AND is_active=1", (email,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> Optional[dict]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE id=%s", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_users() -> list:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM users ORDER BY full_name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_user(email: str, password_hash: str, full_name: str, role: str, created_by=None):
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO users (email, password_hash, full_name, role, created_by) VALUES (%s,%s,%s,%s,%s)",
            (email, password_hash, full_name, role, created_by),
        )
        conn.commit()
        return True, None
    except psycopg2.errors.UniqueViolation:
        return False, "Email already registered."
    except Exception:
        return False, "Email already registered."
    finally:
        conn.close()


def set_user_otp(user_id: int, otp_hash: str, expires_at_iso: str):
    conn = get_conn()
    conn.execute(
        "UPDATE users SET otp_code=%s, otp_expires_at=%s WHERE id=%s",
        (otp_hash, expires_at_iso, user_id),
    )
    conn.commit()
    conn.close()


def clear_user_otp(user_id: int):
    conn = get_conn()
    conn.execute("UPDATE users SET otp_code=NULL, otp_expires_at=NULL WHERE id=%s", (user_id,))
    conn.commit()
    conn.close()


def set_2fa_enabled(user_id: int, enabled: bool):
    conn = get_conn()
    conn.execute("UPDATE users SET totp_enabled=%s WHERE id=%s", (1 if enabled else 0, user_id))
    conn.commit()
    conn.close()


def update_user_role(user_id: int, role: str):
    conn = get_conn()
    conn.execute("UPDATE users SET role=%s WHERE id=%s", (role, user_id))
    conn.commit()
    conn.close()


def toggle_user_active(user_id: int, is_active: int):
    conn = get_conn()
    conn.execute("UPDATE users SET is_active=%s WHERE id=%s", (is_active, user_id))
    conn.commit()
    conn.close()


# ── Projects ───────────────────────────────────────────────────────────────────

def get_all_projects() -> list:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM projects ORDER BY status, name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_project(project_id: int) -> Optional[dict]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM projects WHERE id=%s", (project_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_project_by_name(name: str) -> Optional[dict]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM projects WHERE name=%s", (name,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_project(name: str, created_by: int) -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO projects (name, created_by) VALUES (%s,%s) RETURNING id",
        (name, created_by),
    )
    project_id = cur.fetchone()["id"]
    conn.commit()
    conn.close()
    return project_id


def create_project_full(
    name: str,
    client: Optional[str],
    sample_target: int,
    start_date: Optional[str],
    end_date: Optional[str],
    backcheck_target: float,
    listenin_target: float,
    accompaniment_target: float,
    created_by: int,
    job_number: Optional[str] = None,
    loi_min_minutes: float = 0,
    loi_pct_threshold: float = 0.50,
    flag_warning_pct: float = 5.0,
    flag_critical_pct: float = 10.0,
) -> int:
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO projects
           (name, job_number, client, sample_target, start_date, end_date,
            backcheck_target, listenin_target, accompaniment_target,
            loi_min_minutes, loi_pct_threshold, flag_warning_pct, flag_critical_pct,
            created_by)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
        (name, job_number, client, sample_target, start_date, end_date,
         backcheck_target, listenin_target, accompaniment_target,
         loi_min_minutes, loi_pct_threshold, flag_warning_pct, flag_critical_pct,
         created_by),
    )
    project_id = cur.fetchone()["id"]
    conn.commit()
    conn.close()
    return project_id


def update_project(project_id: int, **kwargs):
    allowed = {"name", "job_number", "client", "sample_target", "start_date", "end_date",
               "status", "backcheck_target", "listenin_target", "accompaniment_target",
               "loi_min_minutes", "loi_pct_threshold", "flag_warning_pct", "flag_critical_pct",
               "column_config"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return
    conn = get_conn()
    sets = ", ".join(f"{k}=%s" for k in fields)
    conn.execute(f"UPDATE projects SET {sets} WHERE id=%s", (*fields.values(), project_id))
    conn.commit()
    conn.close()


def get_project_assignees(project_id: int) -> list:
    conn = get_conn()
    rows = conn.execute(
        """SELECT u.id, u.email, u.full_name, u.role FROM users u
           JOIN project_assignments pa ON pa.user_id=u.id
           WHERE pa.project_id=%s""",
        (project_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def assign_user_to_project(project_id: int, user_id: int, assigned_by: int):
    conn = get_conn()
    try:
        conn.execute(
            """INSERT INTO project_assignments (project_id, user_id, assigned_by)
               VALUES (%s,%s,%s) ON CONFLICT DO NOTHING""",
            (project_id, user_id, assigned_by),
        )
        conn.commit()
    finally:
        conn.close()


def remove_user_from_project(project_id: int, user_id: int):
    conn = get_conn()
    conn.execute(
        "DELETE FROM project_assignments WHERE project_id=%s AND user_id=%s",
        (project_id, user_id),
    )
    conn.commit()
    conn.close()


# ── QC quality records ─────────────────────────────────────────────────────────

def insert_quality_records(
    project_id: int,
    uploaded_by: int,
    filename: str,
    records: list,
    wave_label: Optional[str] = None,
) -> str:
    uid = str(uuid.uuid4())
    std_cols = [
        "instance_id", "interviewer_id", "interview_date", "start_time", "end_time",
        "duration_minutes", "duration_validation", "duration_flag",
        "straight_lining", "long_pause", "gps_status", "phone_present", "audio_present",
        "region", "location", "sample_point_id", "approval_status", "qc_comments",
    ]
    all_cols = std_cols + ["extra_data"]
    conn = get_conn()
    for r in records:
        extra = {
            k: v for k, v in r.items()
            if k not in std_cols
            and k not in ("id", "project_id", "upload_id", "uploaded_by", "upload_date")
        }
        extra_json = json.dumps(extra) if extra else None
        conn.execute(
            f"""INSERT INTO quality_report_records
                (project_id, upload_id, uploaded_by, {', '.join(all_cols)})
                VALUES (%s,%s,%s,{','.join(['%s'] * len(all_cols))})""",
            (project_id, uid, uploaded_by, *[r.get(c) for c in std_cols], extra_json),
        )
    _log_upload(conn, uid, project_id, "quality_report", uploaded_by, filename, len(records), wave_label)
    conn.commit()
    conn.close()
    return uid


def get_quality_records(project_id: int) -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM quality_report_records WHERE project_id=%s ORDER BY interview_date, interviewer_id",
        (project_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_quality_instance_ids(project_id: int) -> set:
    conn = get_conn()
    rows = conn.execute(
        "SELECT DISTINCT instance_id FROM quality_report_records WHERE project_id=%s AND instance_id IS NOT NULL",
        (project_id,),
    ).fetchall()
    conn.close()
    return {r["instance_id"] for r in rows}


# ── Backcheck records ──────────────────────────────────────────────────────────

def insert_backcheck_records(
    project_id: int,
    uploaded_by: int,
    filename: str,
    records: list,
    wave_label: Optional[str] = None,
) -> str:
    uid = str(uuid.uuid4())
    error_cols = [f"error_{i:02d}" for i in range(1, 14)]
    base_cols = ["bc_instance_id", "original_instance_id", "interview_status",
                 "region", "location", "sample_point_id", "backchecker_id",
                 "interviewer_id", "script_name", "interview_date",
                 "interview_start_time", "backcheck_date", "backcheck_time"]
    all_cols = base_cols + error_cols
    conn = get_conn()
    for r in records:
        conn.execute(
            f"""INSERT INTO backcheck_records
                (project_id, upload_id, uploaded_by, {', '.join(all_cols)})
                VALUES (%s,%s,%s,{','.join(['%s'] * len(all_cols))})""",
            (project_id, uid, uploaded_by, *[r.get(c) for c in all_cols]),
        )
    _log_upload(conn, uid, project_id, "backcheck", uploaded_by, filename, len(records), wave_label)
    conn.commit()
    conn.close()
    return uid


def get_backcheck_records(project_id: int) -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM backcheck_records WHERE project_id=%s ORDER BY interview_date",
        (project_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Listen-in records ──────────────────────────────────────────────────────────

def insert_listen_in_record(
    project_id: int,
    logged_by: int,
    instance_id: Optional[str],
    interviewer_id: str,
    region: Optional[str],
    listen_date: str,
    listen_type: str,
    result: str,
    issues_noted: Optional[str],
    action_taken: Optional[str],
    upload_id: Optional[str] = None,
):
    conn = get_conn()
    conn.execute(
        """INSERT INTO listen_in_records
           (project_id, upload_id, logged_by, instance_id, interviewer_id,
            region, listen_date, listen_type, result, issues_noted, action_taken)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (project_id, upload_id, logged_by, instance_id, interviewer_id,
         region, str(listen_date), listen_type, result, issues_noted, action_taken),
    )
    conn.commit()
    conn.close()


def insert_listen_in_batch(
    project_id: int,
    logged_by: int,
    filename: str,
    records: list,
    wave_label: Optional[str] = None,
) -> str:
    uid = str(uuid.uuid4())
    conn = get_conn()
    cols = ["instance_id", "interviewer_id", "region", "listen_date",
            "listen_type", "result", "issues_noted", "action_taken"]
    for r in records:
        conn.execute(
            f"""INSERT INTO listen_in_records
                (project_id, upload_id, logged_by, {', '.join(cols)})
                VALUES (%s,%s,%s,{','.join(['%s'] * len(cols))})""",
            (project_id, uid, logged_by, *[r.get(c) for c in cols]),
        )
    _log_upload(conn, uid, project_id, "listen_in", logged_by, filename, len(records), wave_label)
    conn.commit()
    conn.close()
    return uid


def get_listen_in_records(project_id: int) -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM listen_in_records WHERE project_id=%s ORDER BY listen_date DESC",
        (project_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_listen_in_record(record_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM listen_in_records WHERE id=%s", (record_id,))
    conn.commit()
    conn.close()


# ── Performance & timing records ───────────────────────────────────────────────

def get_performance_records(project_id: int) -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM performance_records WHERE project_id=%s ORDER BY region, interviewer_id",
        (project_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_timing_records(project_id: int) -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM timing_records WHERE project_id=%s ORDER BY interview_date",
        (project_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_cancelled_records(project_id: int) -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM cancelled_interview_records WHERE project_id=%s ORDER BY interview_date",
        (project_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_interviewer_code_set() -> set:
    """Return the set of all known interviewer_codes in the registry."""
    conn = get_conn()
    rows = conn.execute("SELECT interviewer_code FROM interviewers").fetchall()
    conn.close()
    return {r["interviewer_code"] for r in rows}


# ── Upload log ─────────────────────────────────────────────────────────────────

def get_upload_log(project_id: Optional[int] = None) -> list:
    conn = get_conn()
    if project_id:
        rows = conn.execute(
            """SELECT ul.*, u.full_name as uploader_name FROM upload_log ul
               LEFT JOIN users u ON u.id=ul.uploaded_by
               WHERE ul.project_id=%s ORDER BY ul.upload_date DESC""",
            (project_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT ul.*, u.full_name as uploader_name, p.name as project_name
               FROM upload_log ul
               LEFT JOIN users u ON u.id=ul.uploaded_by
               LEFT JOIN projects p ON p.id=ul.project_id
               ORDER BY ul.upload_date DESC""",
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def lock_upload(upload_id: str):
    conn = get_conn()
    conn.execute("UPDATE upload_log SET is_locked=1 WHERE upload_id=%s", (upload_id,))
    conn.commit()
    conn.close()


def is_upload_locked(upload_id: str) -> bool:
    conn = get_conn()
    row = conn.execute("SELECT is_locked FROM upload_log WHERE upload_id=%s", (upload_id,)).fetchone()
    conn.close()
    return bool(row and row["is_locked"])


def delete_upload(upload_id: str, report_type: str):
    table_map = {
        "quality_report": "quality_report_records",
        "backcheck": "backcheck_records",
        "cancelled_interviews": "cancelled_interview_records",
        "performance": "performance_records",
        "timing": "timing_records",
        "listen_in": "listen_in_records",
    }
    table = table_map.get(report_type)
    if not table:
        return
    conn = get_conn()
    conn.execute(f"DELETE FROM {table} WHERE upload_id=%s", (upload_id,))
    conn.execute("DELETE FROM upload_log WHERE upload_id=%s", (upload_id,))
    conn.commit()
    conn.close()


def delete_wave_records(project_id: int, wave_label: str, report_type: str):
    table_map = {
        "quality_report": "quality_report_records",
        "backcheck": "backcheck_records",
        "cancelled_interviews": "cancelled_interview_records",
        "performance": "performance_records",
        "timing": "timing_records",
        "listen_in": "listen_in_records",
    }
    table = table_map.get(report_type)
    if not table:
        return
    conn = get_conn()
    upload_ids = [r["upload_id"] for r in conn.execute(
        "SELECT upload_id FROM upload_log WHERE project_id=%s AND wave_label=%s AND report_type=%s",
        (project_id, wave_label, report_type),
    ).fetchall()]
    if upload_ids:
        conn.execute(f"DELETE FROM {table} WHERE upload_id = ANY(%s)", (upload_ids,))
        conn.execute("DELETE FROM upload_log WHERE upload_id = ANY(%s)", (upload_ids,))
        conn.commit()
    conn.close()


# ── Dashboard summary ──────────────────────────────────────────────────────────

def get_dashboard_summary() -> list:
    """Summary stats for all projects — used on the main dashboard overview."""
    conn = get_conn()
    projects = conn.execute("SELECT * FROM projects ORDER BY status, name").fetchall()
    result = []
    for p in projects:
        pid = p["id"]

        qr = conn.execute(
            "SELECT COUNT(*) as total, "
            "SUM(CASE WHEN approval_status='Approved' THEN 1 ELSE 0 END) as approved, "
            "SUM(CASE WHEN approval_status='Cancelled' THEN 1 ELSE 0 END) as cancelled, "
            "SUM(CASE WHEN duration_flag='Flag' THEN 1 ELSE 0 END) as flagged "
            "FROM quality_report_records WHERE project_id=%s",
            (pid,),
        ).fetchone()

        bc = conn.execute(
            "SELECT COUNT(*) as total FROM backcheck_records WHERE project_id=%s",
            (pid,),
        ).fetchone()

        perf = conn.execute(
            "SELECT SUM(accompaniments) as accompaniments, "
            "SUM(interview_completes) as completes "
            "FROM performance_records WHERE project_id=%s",
            (pid,),
        ).fetchone()

        approved = qr["approved"] or 0
        target = p["sample_target"] or 0
        pct = round(approved / target * 100, 1) if target > 0 else 0

        bc_count = bc["total"] or 0
        bc_rate = round(bc_count / approved * 100, 1) if approved > 0 else 0

        acc = (perf["accompaniments"] or 0) if perf else 0
        completes = (perf["completes"] or 0) if perf else 0
        acc_rate = round(acc / completes * 100, 1) if completes > 0 else 0

        li = conn.execute(
            "SELECT COUNT(*) as total FROM listen_in_records WHERE project_id=%s",
            (pid,),
        ).fetchone()
        li_count = li["total"] or 0
        li_rate = round(li_count / approved * 100, 1) if approved > 0 else 0

        result.append({
            **dict(p),
            "approved": approved,
            "completion_pct": pct,
            "backcheck_count": bc_count,
            "backcheck_rate": bc_rate,
            "accompaniment_rate": acc_rate,
            "listenin_count": li_count,
            "listenin_rate": li_rate,
            "flagged": qr["flagged"] or 0,
            "total_submitted": qr["total"] or 0,
        })

    conn.close()
    return result


# ── Schema init ────────────────────────────────────────────────────────────────

def init_tables():
    """Create the full base schema and apply additive migrations."""
    conn = get_conn()

    tables = [
        """CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'other',
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by INTEGER REFERENCES users(id),
            interviewer_code TEXT,
            totp_enabled INTEGER DEFAULT 0,
            otp_code TEXT,
            otp_expires_at TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS projects (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            job_number TEXT,
            client TEXT,
            sample_target INTEGER DEFAULT 0,
            backcheck_target REAL DEFAULT 0.20,
            listenin_target REAL DEFAULT 0.10,
            accompaniment_target REAL DEFAULT 0.20,
            loi_min_minutes REAL DEFAULT 0,
            loi_pct_threshold REAL DEFAULT 0.50,
            flag_warning_pct REAL DEFAULT 5.0,
            flag_critical_pct REAL DEFAULT 10.0,
            start_date DATE,
            end_date DATE,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by INTEGER REFERENCES users(id),
            column_config TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS project_assignments (
            id SERIAL PRIMARY KEY,
            project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            assigned_by INTEGER REFERENCES users(id),
            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(project_id, user_id)
        )""",
        """CREATE TABLE IF NOT EXISTS quality_report_records (
            id SERIAL PRIMARY KEY,
            project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
            upload_id TEXT NOT NULL,
            uploaded_by INTEGER REFERENCES users(id),
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            instance_id TEXT,
            interviewer_id TEXT,
            interview_date DATE,
            start_time TEXT,
            end_time TEXT,
            duration_minutes REAL,
            duration_validation TEXT,
            duration_flag TEXT,
            straight_lining TEXT,
            long_pause TEXT,
            gps_status TEXT,
            phone_present TEXT,
            audio_present TEXT,
            region TEXT,
            location TEXT,
            sample_point_id TEXT,
            approval_status TEXT,
            qc_comments TEXT,
            extra_data TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS listen_in_records (
            id SERIAL PRIMARY KEY,
            project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
            upload_id TEXT,
            logged_by INTEGER REFERENCES users(id),
            log_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            instance_id TEXT,
            interviewer_id TEXT,
            region TEXT,
            listen_date DATE,
            listen_type TEXT,
            result TEXT,
            issues_noted TEXT,
            action_taken TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS backcheck_records (
            id SERIAL PRIMARY KEY,
            project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
            upload_id TEXT NOT NULL,
            uploaded_by INTEGER REFERENCES users(id),
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            bc_instance_id TEXT,
            original_instance_id TEXT,
            interview_status TEXT,
            region TEXT,
            location TEXT,
            sample_point_id TEXT,
            backchecker_id TEXT,
            interviewer_id TEXT,
            script_name TEXT,
            interview_date DATE,
            interview_start_time TEXT,
            backcheck_date DATE,
            backcheck_time TEXT,
            error_01 INTEGER DEFAULT 0,
            error_02 INTEGER DEFAULT 0,
            error_03 INTEGER DEFAULT 0,
            error_04 INTEGER DEFAULT 0,
            error_05 INTEGER DEFAULT 0,
            error_06 INTEGER DEFAULT 0,
            error_07 INTEGER DEFAULT 0,
            error_08 INTEGER DEFAULT 0,
            error_09 INTEGER DEFAULT 0,
            error_10 INTEGER DEFAULT 0,
            error_11 INTEGER DEFAULT 0,
            error_12 INTEGER DEFAULT 0,
            error_13 INTEGER DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS cancelled_interview_records (
            id SERIAL PRIMARY KEY,
            project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
            upload_id TEXT NOT NULL,
            uploaded_by INTEGER REFERENCES users(id),
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            instance_id TEXT,
            region TEXT,
            location TEXT,
            sample_point_id TEXT,
            interviewer_id TEXT,
            script_name TEXT,
            interview_date DATE,
            start_time TEXT,
            end_time TEXT,
            interview_length REAL,
            active_length REAL,
            avg_length_sample_point REAL,
            avg_length_region REAL,
            avg_length_project REAL,
            idle_time REAL,
            gap_to_last REAL,
            same_day_finish TEXT,
            qf_a TEXT,
            qf_b TEXT,
            qf_c TEXT,
            qf_d TEXT,
            qf_e TEXT,
            qf_f TEXT,
            interviewer_performance TEXT,
            backcheck_result_telephone TEXT,
            backcheck_result_f2f TEXT,
            backcheck_result_independent TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS performance_records (
            id SERIAL PRIMARY KEY,
            project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
            upload_id TEXT NOT NULL,
            uploaded_by INTEGER REFERENCES users(id),
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            interviewer_id TEXT,
            region TEXT,
            first_interview DATE,
            last_interview DATE,
            interview_completes INTEGER DEFAULT 0,
            followup_completes INTEGER DEFAULT 0,
            ecs_completes INTEGER DEFAULT 0,
            work_summary INTEGER DEFAULT 0,
            accompaniments INTEGER DEFAULT 0,
            cancelled_interviews INTEGER DEFAULT 0,
            backcheck_telephone_created INTEGER DEFAULT 0,
            backcheck_f2f_created INTEGER DEFAULT 0,
            backcheck_f2f_infield INTEGER DEFAULT 0,
            backcheck_total INTEGER DEFAULT 0,
            backcheck_completed INTEGER DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS timing_records (
            id SERIAL PRIMARY KEY,
            project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
            upload_id TEXT NOT NULL,
            uploaded_by INTEGER REFERENCES users(id),
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            instance_id TEXT,
            interviewer_id TEXT,
            region TEXT,
            interview_date DATE,
            duration_minutes REAL
        )""",
        """CREATE TABLE IF NOT EXISTS upload_log (
            id SERIAL PRIMARY KEY,
            upload_id TEXT NOT NULL,
            project_id INTEGER REFERENCES projects(id),
            report_type TEXT NOT NULL,
            uploaded_by INTEGER REFERENCES users(id),
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            filename TEXT,
            row_count INTEGER DEFAULT 0,
            notes TEXT,
            wave_label TEXT,
            is_locked INTEGER DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS supervisors (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            region TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS interviewers (
            id SERIAL PRIMARY KEY,
            interviewer_code TEXT UNIQUE NOT NULL,
            name TEXT,
            supervisor_id INTEGER REFERENCES supervisors(id) ON DELETE SET NULL,
            region TEXT,
            is_active INTEGER DEFAULT 1,
            is_blocked INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS interviewer_actions (
            id SERIAL PRIMARY KEY,
            interviewer_code TEXT NOT NULL,
            action_type TEXT NOT NULL,
            performed_by INTEGER REFERENCES users(id),
            message TEXT,
            email_sent INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
    ]

    for sql in tables:
        conn.execute(sql)
    conn.commit()

    # Additive migrations — safe to run repeatedly, cover DBs created before
    # any of the columns above were part of the initial CREATE TABLE.
    _safe_add_column(conn, "users", "interviewer_code", "TEXT")
    _safe_add_column(conn, "users", "totp_enabled", "INTEGER DEFAULT 0")
    _safe_add_column(conn, "users", "otp_code", "TEXT")
    _safe_add_column(conn, "users", "otp_expires_at", "TEXT")
    _safe_add_column(conn, "projects", "column_config", "TEXT")
    _safe_add_column(conn, "projects", "job_number", "TEXT")
    _safe_add_column(conn, "projects", "loi_min_minutes", "REAL DEFAULT 0")
    _safe_add_column(conn, "projects", "loi_pct_threshold", "REAL DEFAULT 0.50")
    _safe_add_column(conn, "projects", "flag_warning_pct", "REAL DEFAULT 5.0")
    _safe_add_column(conn, "projects", "flag_critical_pct", "REAL DEFAULT 10.0")
    _safe_add_column(conn, "quality_report_records", "extra_data", "TEXT")
    _safe_add_column(conn, "upload_log", "notes", "TEXT")
    _safe_add_column(conn, "upload_log", "wave_label", "TEXT")
    _safe_add_column(conn, "upload_log", "is_locked", "INTEGER DEFAULT 0")
    _safe_add_column(conn, "interviewers", "is_blocked", "INTEGER DEFAULT 0")

    # Seed a default admin if no users exist.
    row = conn.execute("SELECT COUNT(*) as cnt FROM users").fetchone()
    if (row["cnt"] or 0) == 0:
        import bcrypt
        pw = bcrypt.hashpw(b"admin1234", bcrypt.gensalt()).decode()
        conn.execute(
            "INSERT INTO users (email, password_hash, full_name, role) VALUES (%s,%s,%s,%s)",
            ("admin@example.com", pw, "System Admin", "qc_executive"),
        )
        conn.commit()

    conn.close()


def insert_performance_records(
    project_id: int,
    uploaded_by: int,
    filename: str,
    records: list,
    wave_label: Optional[str] = None,
) -> str:
    uid = str(uuid.uuid4())
    cols = [
        "interviewer_id", "region", "first_interview", "last_interview",
        "interview_completes", "followup_completes", "ecs_completes",
        "work_summary", "accompaniments", "cancelled_interviews",
        "backcheck_telephone_created", "backcheck_f2f_created",
        "backcheck_f2f_infield", "backcheck_total", "backcheck_completed",
    ]
    conn = get_conn()
    for r in records:
        conn.execute(
            f"""INSERT INTO performance_records
                (project_id, upload_id, uploaded_by, {', '.join(cols)})
                VALUES (%s,%s,%s,{','.join(['%s'] * len(cols))})""",
            (project_id, uid, uploaded_by, *[r.get(c) for c in cols]),
        )
    _log_upload(conn, uid, project_id, "performance", uploaded_by, filename, len(records), wave_label)
    conn.commit()
    conn.close()
    return uid


def insert_timing_records(
    project_id: int,
    uploaded_by: int,
    filename: str,
    records: list,
    wave_label: Optional[str] = None,
) -> str:
    uid = str(uuid.uuid4())
    cols = ["instance_id", "interviewer_id", "region", "interview_date", "duration_minutes"]
    conn = get_conn()
    for r in records:
        conn.execute(
            f"""INSERT INTO timing_records
                (project_id, upload_id, uploaded_by, {', '.join(cols)})
                VALUES (%s,%s,%s,{','.join(['%s'] * len(cols))})""",
            (project_id, uid, uploaded_by, *[r.get(c) for c in cols]),
        )
    _log_upload(conn, uid, project_id, "timing", uploaded_by, filename, len(records), wave_label)
    conn.commit()
    conn.close()
    return uid


def insert_cancelled_records(
    project_id: int,
    uploaded_by: int,
    filename: str,
    records: list,
    wave_label: Optional[str] = None,
) -> str:
    uid = str(uuid.uuid4())
    cols = [
        "instance_id", "region", "location", "sample_point_id", "interviewer_id",
        "script_name", "interview_date", "start_time", "end_time",
        "interview_length", "active_length", "avg_length_sample_point",
        "avg_length_region", "avg_length_project", "idle_time", "gap_to_last",
        "same_day_finish", "qf_a", "qf_b", "qf_c", "qf_d", "qf_e", "qf_f",
        "interviewer_performance", "backcheck_result_telephone",
        "backcheck_result_f2f", "backcheck_result_independent",
    ]
    conn = get_conn()
    for r in records:
        conn.execute(
            f"""INSERT INTO cancelled_interview_records
                (project_id, upload_id, uploaded_by, {', '.join(cols)})
                VALUES (%s,%s,%s,{','.join(['%s'] * len(cols))})""",
            (project_id, uid, uploaded_by, *[r.get(c) for c in cols]),
        )
    _log_upload(conn, uid, project_id, "cancelled_interviews", uploaded_by, filename, len(records), wave_label)
    conn.commit()
    conn.close()
    return uid


# ── Supervisors ────────────────────────────────────────────────────────────────

def get_all_supervisors() -> list:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM supervisors ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_supervisor(name: str, email: Optional[str] = None, phone: Optional[str] = None, region: Optional[str] = None) -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO supervisors (name, email, phone, region) VALUES (%s,%s,%s,%s) RETURNING id",
        (name, email, phone, region),
    )
    sid = cur.fetchone()["id"]
    conn.commit()
    conn.close()
    return sid


def update_supervisor(supervisor_id: int, **kwargs):
    if not kwargs:
        return
    fields = ", ".join(f"{k}=%s" for k in kwargs)
    conn = get_conn()
    conn.execute(f"UPDATE supervisors SET {fields} WHERE id=%s", (*kwargs.values(), supervisor_id))
    conn.commit()
    conn.close()


def delete_supervisor(supervisor_id: int):
    conn = get_conn()
    conn.execute("UPDATE interviewers SET supervisor_id=NULL WHERE supervisor_id=%s", (supervisor_id,))
    conn.execute("DELETE FROM supervisors WHERE id=%s", (supervisor_id,))
    conn.commit()
    conn.close()


def upsert_supervisors_bulk(names: list) -> dict:
    """Find-or-create supervisors by name. Returns {name: id} mapping."""
    if not names:
        return {}
    conn = get_conn()
    result: dict = {}
    for raw in names:
        name = str(raw).strip()
        if not name or name.lower() in ("none", "null", "nan", ""):
            continue
        existing = conn.execute("SELECT id FROM supervisors WHERE name=%s", (name,)).fetchone()
        if existing:
            result[name] = existing["id"]
        else:
            cur = conn.execute("INSERT INTO supervisors (name) VALUES (%s) RETURNING id", (name,))
            result[name] = cur.fetchone()["id"]
    conn.commit()
    conn.close()
    return result


# ── Interviewers ───────────────────────────────────────────────────────────────

def get_all_interviewers() -> list:
    conn = get_conn()
    rows = conn.execute("""
        SELECT i.*, s.name AS supervisor_name
        FROM interviewers i
        LEFT JOIN supervisors s ON i.supervisor_id = s.id
        ORDER BY i.interviewer_code
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def upsert_interviewer(
    interviewer_code: str,
    name: Optional[str] = None,
    supervisor_id: Optional[int] = None,
    region: Optional[str] = None,
    is_active: int = 1,
) -> int:
    conn = get_conn()
    existing = conn.execute(
        "SELECT id FROM interviewers WHERE interviewer_code=%s", (interviewer_code,)
    ).fetchone()
    if existing:
        conn.execute(
            """UPDATE interviewers
               SET name=COALESCE(%s,name), supervisor_id=%s, region=COALESCE(%s,region), is_active=%s
               WHERE interviewer_code=%s""",
            (name, supervisor_id, region, is_active, interviewer_code),
        )
        iid = existing["id"]
    else:
        cur = conn.execute(
            "INSERT INTO interviewers (interviewer_code, name, supervisor_id, region, is_active) VALUES (%s,%s,%s,%s,%s) RETURNING id",
            (interviewer_code, name, supervisor_id, region, is_active),
        )
        iid = cur.fetchone()["id"]
    conn.commit()
    conn.close()
    return iid


def get_interviewer_metrics(interviewer_code: str) -> dict:
    """Cross-project performance metrics for one interviewer."""
    conn = get_conn()

    info = conn.execute("""
        SELECT i.*, s.name AS supervisor_name
        FROM interviewers i
        LEFT JOIN supervisors s ON i.supervisor_id = s.id
        WHERE i.interviewer_code=%s
    """, (interviewer_code,)).fetchone()

    qr = conn.execute("""
        SELECT COUNT(*) AS total_interviews,
               SUM(CASE WHEN duration_flag='Flag' THEN 1 ELSE 0 END) AS duration_flags,
               SUM(CASE WHEN straight_lining='Flag' THEN 1 ELSE 0 END) AS sl_flags,
               SUM(CASE WHEN approval_status='Approved' THEN 1 ELSE 0 END) AS approved,
               SUM(CASE WHEN approval_status='Cancelled' THEN 1 ELSE 0 END) AS cancelled,
               AVG(duration_minutes) AS avg_duration
        FROM quality_report_records WHERE interviewer_id=%s
    """, (interviewer_code,)).fetchone()

    bc = conn.execute("""
        SELECT COUNT(*) AS bc_count,
               COALESCE(SUM(error_01+error_02+error_03+error_04+error_05+error_06+error_07+
                            error_08+error_09+error_10+error_11+error_12+error_13),0) AS total_errors
        FROM backcheck_records WHERE interviewer_id=%s
    """, (interviewer_code,)).fetchone()

    li = conn.execute("""
        SELECT COUNT(*) AS li_count,
               SUM(CASE WHEN result='Pass' THEN 1 ELSE 0 END) AS li_pass,
               SUM(CASE WHEN result='Fail' THEN 1 ELSE 0 END) AS li_fail
        FROM listen_in_records WHERE interviewer_id=%s
    """, (interviewer_code,)).fetchone()

    by_project = conn.execute("""
        SELECT p.name AS project_name, p.id AS project_id,
               COUNT(*) AS interviews,
               SUM(CASE WHEN qr.duration_flag='Flag' THEN 1 ELSE 0 END) AS dur_flags,
               SUM(CASE WHEN qr.straight_lining='Flag' THEN 1 ELSE 0 END) AS sl_flags,
               SUM(CASE WHEN qr.approval_status='Approved' THEN 1 ELSE 0 END) AS approved
        FROM quality_report_records qr
        JOIN projects p ON qr.project_id = p.id
        WHERE qr.interviewer_id=%s
        GROUP BY p.id, p.name
        ORDER BY p.name
    """, (interviewer_code,)).fetchall()

    conn.close()
    return {
        "info": dict(info) if info else None,
        "quality": dict(qr) if qr else {},
        "backcheck": dict(bc) if bc else {},
        "listen_in": dict(li) if li else {},
        "by_project": [dict(r) for r in by_project],
    }


def get_interviewer_analytics(
    project_id: Optional[int] = None,
    supervisor_id: Optional[int] = None,
    region: Optional[str] = None,
) -> dict:
    """All interviewers with aggregated metrics in one query. Filterable by project/supervisor/region."""
    conn = get_conn()
    pfilter = "AND project_id = %s" if project_id else ""
    parg: list = [project_id] if project_id else []

    where_parts: list[str] = []
    where_args: list = []
    if supervisor_id is not None:
        where_parts.append("i.supervisor_id = %s")
        where_args.append(supervisor_id)
    if region:
        where_parts.append("i.region = %s")
        where_args.append(region)
    where_clause = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

    sql = f"""
        WITH qr AS (
            SELECT interviewer_id,
                   COUNT(*) AS total_interviews,
                   SUM(CASE WHEN duration_flag='Flag' THEN 1 ELSE 0 END) AS duration_flags,
                   SUM(CASE WHEN straight_lining='Flag' THEN 1 ELSE 0 END) AS sl_flags,
                   SUM(CASE WHEN approval_status='Approved' THEN 1 ELSE 0 END) AS approved,
                   SUM(CASE WHEN approval_status='Cancelled' THEN 1 ELSE 0 END) AS cancelled,
                   AVG(duration_minutes) AS avg_duration
            FROM quality_report_records WHERE 1=1 {pfilter}
            GROUP BY interviewer_id
        ),
        bc AS (
            SELECT interviewer_id,
                   COUNT(*) AS bc_count,
                   COALESCE(SUM(error_01+error_02+error_03+error_04+error_05+error_06+error_07+
                                error_08+error_09+error_10+error_11+error_12+error_13), 0) AS bc_errors
            FROM backcheck_records WHERE 1=1 {pfilter}
            GROUP BY interviewer_id
        ),
        li AS (
            SELECT interviewer_id,
                   COUNT(*) AS li_count,
                   SUM(CASE WHEN result='Pass' THEN 1 ELSE 0 END) AS li_pass,
                   SUM(CASE WHEN result='Fail' THEN 1 ELSE 0 END) AS li_fail
            FROM listen_in_records WHERE 1=1 {pfilter}
            GROUP BY interviewer_id
        )
        SELECT i.interviewer_code AS code, i.name, i.region, i.supervisor_id, i.is_active,
               s.name AS supervisor_name,
               COALESCE(qr.total_interviews, 0) AS total_interviews,
               COALESCE(qr.duration_flags, 0) AS duration_flags,
               COALESCE(qr.sl_flags, 0) AS sl_flags,
               COALESCE(qr.approved, 0) AS approved,
               COALESCE(qr.cancelled, 0) AS cancelled,
               ROUND(COALESCE(qr.avg_duration, 0), 1) AS avg_duration,
               COALESCE(bc.bc_count, 0) AS bc_count,
               COALESCE(bc.bc_errors, 0) AS bc_errors,
               COALESCE(li.li_count, 0) AS li_count,
               COALESCE(li.li_pass, 0) AS li_pass,
               COALESCE(li.li_fail, 0) AS li_fail,
               i.is_blocked,
               CASE WHEN COALESCE(qr.total_interviews, 0) > 0
                    THEN ROUND(((COALESCE(qr.duration_flags,0)+COALESCE(qr.sl_flags,0))*100.0/qr.total_interviews),1)
                    ELSE 0 END AS flag_rate
        FROM interviewers i
        LEFT JOIN supervisors s ON i.supervisor_id = s.id
        LEFT JOIN qr ON qr.interviewer_id = i.interviewer_code
        LEFT JOIN bc ON bc.interviewer_id = i.interviewer_code
        LEFT JOIN li ON li.interviewer_id = i.interviewer_code
        {where_clause}
        ORDER BY flag_rate DESC, total_interviews DESC
    """

    rows = conn.execute(sql, parg + parg + parg + where_args).fetchall()
    interviewers = [dict(r) for r in rows]

    sup_map: dict = {}
    for r in interviewers:
        sn = r.get("supervisor_name") or "Unassigned"
        e = sup_map.setdefault(sn, {"supervisor_name": sn, "interviewer_count": 0,
                                     "total_interviews": 0, "total_flags": 0, "bc_errors": 0})
        e["interviewer_count"] += 1
        e["total_interviews"] += r["total_interviews"]
        e["total_flags"] += r["duration_flags"] + r["sl_flags"]
        e["bc_errors"] += r["bc_errors"]
    by_supervisor = []
    for s in sup_map.values():
        s["flag_rate"] = round(s["total_flags"] * 100 / s["total_interviews"], 1) if s["total_interviews"] else 0
        by_supervisor.append(s)
    by_supervisor.sort(key=lambda x: x["flag_rate"], reverse=True)

    projects = [dict(r) for r in conn.execute("SELECT id, name FROM projects ORDER BY name").fetchall()]
    conn.close()
    return {"interviewers": interviewers, "by_supervisor": by_supervisor, "projects": projects}


# ── Activity feed ──────────────────────────────────────────────────────────────

def get_project_activity(project_id: Optional[int] = None, limit: int = 20) -> list:
    conn = get_conn()
    if project_id:
        rows = conn.execute(
            """SELECT ul.upload_date, ul.report_type, ul.filename, ul.row_count,
                      ul.wave_label, p.name as project_name, u.full_name as uploader
               FROM upload_log ul
               LEFT JOIN projects p ON p.id=ul.project_id
               LEFT JOIN users u ON u.id=ul.uploaded_by
               WHERE ul.project_id=%s
               ORDER BY ul.upload_date DESC LIMIT %s""",
            (project_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT ul.upload_date, ul.report_type, ul.filename, ul.row_count,
                      ul.wave_label, p.name as project_name, u.full_name as uploader
               FROM upload_log ul
               LEFT JOIN projects p ON p.id=ul.project_id
               LEFT JOIN users u ON u.id=ul.uploaded_by
               ORDER BY ul.upload_date DESC LIMIT %s""",
            (limit,),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Interviewer block / warn / escalate ────────────────────────────────────────

def get_interviewer_by_code(code: str) -> Optional[dict]:
    conn = get_conn()
    row = conn.execute(
        """SELECT i.*, s.name AS supervisor_name, s.email AS supervisor_email
           FROM interviewers i
           LEFT JOIN supervisors s ON i.supervisor_id = s.id
           WHERE i.interviewer_code = %s""",
        (code,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def block_interviewer(code: str, performed_by: int, message: Optional[str] = None):
    conn = get_conn()
    conn.execute(
        "UPDATE interviewers SET is_blocked = 1 WHERE interviewer_code = %s",
        (code,),
    )
    conn.execute(
        "INSERT INTO interviewer_actions (interviewer_code, action_type, performed_by, message) VALUES (%s,'block',%s,%s)",
        (code, performed_by, message),
    )
    conn.commit()
    conn.close()


def unblock_interviewer(code: str, performed_by: int):
    conn = get_conn()
    conn.execute(
        "UPDATE interviewers SET is_blocked = 0 WHERE interviewer_code = %s",
        (code,),
    )
    conn.execute(
        "INSERT INTO interviewer_actions (interviewer_code, action_type, performed_by) VALUES (%s,'unblock',%s)",
        (code, performed_by),
    )
    conn.commit()
    conn.close()


def add_interviewer_warning(code: str, performed_by: int, message: Optional[str], email_sent: bool = False):
    conn = get_conn()
    conn.execute(
        "INSERT INTO interviewer_actions (interviewer_code, action_type, performed_by, message, email_sent) VALUES (%s,'warning',%s,%s,%s)",
        (code, performed_by, message, 1 if email_sent else 0),
    )
    conn.commit()
    conn.close()


def add_interviewer_escalation(code: str, performed_by: int, message: Optional[str]):
    conn = get_conn()
    conn.execute(
        "INSERT INTO interviewer_actions (interviewer_code, action_type, performed_by, message) VALUES (%s,'escalation',%s,%s)",
        (code, performed_by, message),
    )
    conn.commit()
    conn.close()


def get_interviewer_actions(code: str) -> list:
    conn = get_conn()
    rows = conn.execute(
        """SELECT ia.*, u.full_name AS performed_by_name
           FROM interviewer_actions ia
           LEFT JOIN users u ON u.id = ia.performed_by
           WHERE ia.interviewer_code = %s
           ORDER BY ia.created_at DESC""",
        (code,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
