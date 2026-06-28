"""
Read/write access to the dashboard's SQLite database for the FastAPI app.
Mirrors dashboard/database.py logic — all functions needed by routers.
"""
import json
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Optional

DB_PATH = os.environ.get(
    "DB_PATH",
    str(Path(__file__).parent / "dashboard" / "qc_dashboard.db"),
)


def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def db_available() -> bool:
    """Return True if the dashboard database file exists."""
    return Path(DB_PATH).exists()


# ── Internal helpers ───────────────────────────────────────────────────────────

def _log_upload(conn, upload_id, project_id, report_type, uploaded_by, filename, row_count, wave_label=None):
    conn.execute(
        """INSERT INTO upload_log (upload_id, project_id, report_type, uploaded_by, filename, row_count, wave_label)
           VALUES (?,?,?,?,?,?,?)""",
        (upload_id, project_id, report_type, uploaded_by, filename, row_count, wave_label or None),
    )


# ── Users ──────────────────────────────────────────────────────────────────────

def get_user_by_email(email: str) -> Optional[dict]:
    if not db_available():
        return None
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM users WHERE email=? AND is_active=1", (email,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> Optional[dict]:
    if not db_available():
        return None
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_users() -> list:
    if not db_available():
        return []
    conn = get_conn()
    rows = conn.execute("SELECT * FROM users ORDER BY full_name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_user(email: str, password_hash: str, full_name: str, role: str, created_by=None):
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO users (email, password_hash, full_name, role, created_by) VALUES (?,?,?,?,?)",
            (email, password_hash, full_name, role, created_by),
        )
        conn.commit()
        return True, None
    except sqlite3.IntegrityError:
        return False, "Email already registered."
    finally:
        conn.close()


def update_user_role(user_id: int, role: str):
    conn = get_conn()
    conn.execute("UPDATE users SET role=? WHERE id=?", (role, user_id))
    conn.commit()
    conn.close()


def toggle_user_active(user_id: int, is_active: int):
    conn = get_conn()
    conn.execute("UPDATE users SET is_active=? WHERE id=?", (is_active, user_id))
    conn.commit()
    conn.close()


# ── Projects ───────────────────────────────────────────────────────────────────

def get_all_projects() -> list:
    if not db_available():
        return []
    conn = get_conn()
    rows = conn.execute("SELECT * FROM projects ORDER BY status, name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_project(project_id: int) -> Optional[dict]:
    if not db_available():
        return None
    conn = get_conn()
    row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_project_by_name(name: str) -> Optional[dict]:
    if not db_available():
        return None
    conn = get_conn()
    row = conn.execute("SELECT * FROM projects WHERE name=?", (name,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_project(name: str, created_by: int) -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO projects (name, created_by) VALUES (?,?)",
        (name, created_by),
    )
    project_id = cur.lastrowid
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
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (name, job_number, client, sample_target, start_date, end_date,
         backcheck_target, listenin_target, accompaniment_target,
         loi_min_minutes, loi_pct_threshold, flag_warning_pct, flag_critical_pct,
         created_by),
    )
    project_id = cur.lastrowid
    conn.commit()
    conn.close()
    return project_id


def update_project(project_id: int, **kwargs):
    allowed = {"name", "job_number", "client", "sample_target", "start_date", "end_date",
               "status", "backcheck_target", "listenin_target", "accompaniment_target",
               "loi_min_minutes", "loi_pct_threshold", "flag_warning_pct", "flag_critical_pct"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return
    conn = get_conn()
    sets = ", ".join(f"{k}=?" for k in fields)
    conn.execute(f"UPDATE projects SET {sets} WHERE id=?", (*fields.values(), project_id))
    conn.commit()
    conn.close()


def get_project_assignees(project_id: int) -> list:
    if not db_available():
        return []
    conn = get_conn()
    rows = conn.execute(
        """SELECT u.id, u.email, u.full_name, u.role FROM users u
           JOIN project_assignments pa ON pa.user_id=u.id
           WHERE pa.project_id=?""",
        (project_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def assign_user_to_project(project_id: int, user_id: int, assigned_by: int):
    conn = get_conn()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO project_assignments (project_id, user_id, assigned_by) VALUES (?,?,?)",
            (project_id, user_id, assigned_by),
        )
        conn.commit()
    finally:
        conn.close()


def remove_user_from_project(project_id: int, user_id: int):
    conn = get_conn()
    conn.execute(
        "DELETE FROM project_assignments WHERE project_id=? AND user_id=?",
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
                VALUES (?,?,?,{','.join('?' * len(all_cols))})""",
            (project_id, uid, uploaded_by, *[r.get(c) for c in std_cols], extra_json),
        )
    _log_upload(conn, uid, project_id, "quality_report", uploaded_by, filename, len(records), wave_label)
    conn.commit()
    conn.close()
    return uid


def get_quality_records(project_id: int) -> list:
    if not db_available():
        return []
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM quality_report_records WHERE project_id=? ORDER BY interview_date, interviewer_id",
        (project_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_quality_instance_ids(project_id: int) -> set:
    if not db_available():
        return set()
    conn = get_conn()
    rows = conn.execute(
        "SELECT DISTINCT instance_id FROM quality_report_records WHERE project_id=? AND instance_id IS NOT NULL",
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
                VALUES (?,?,?,{','.join('?' * len(all_cols))})""",
            (project_id, uid, uploaded_by, *[r.get(c) for c in all_cols]),
        )
    _log_upload(conn, uid, project_id, "backcheck", uploaded_by, filename, len(records), wave_label)
    conn.commit()
    conn.close()
    return uid


def get_backcheck_records(project_id: int) -> list:
    if not db_available():
        return []
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM backcheck_records WHERE project_id=? ORDER BY interview_date",
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
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
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
                VALUES (?,?,?,{','.join('?' * len(cols))})""",
            (project_id, uid, logged_by, *[r.get(c) for c in cols]),
        )
    _log_upload(conn, uid, project_id, "listen_in", logged_by, filename, len(records), wave_label)
    conn.commit()
    conn.close()
    return uid


def get_listen_in_records(project_id: int) -> list:
    if not db_available():
        return []
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM listen_in_records WHERE project_id=? ORDER BY listen_date DESC",
        (project_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_listen_in_record(record_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM listen_in_records WHERE id=?", (record_id,))
    conn.commit()
    conn.close()


# ── Performance & timing records ───────────────────────────────────────────────

def get_performance_records(project_id: int) -> list:
    if not db_available():
        return []
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM performance_records WHERE project_id=? ORDER BY region, interviewer_id",
        (project_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_timing_records(project_id: int) -> list:
    if not db_available():
        return []
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM timing_records WHERE project_id=? ORDER BY interview_date",
        (project_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_cancelled_records(project_id: int) -> list:
    if not db_available():
        return []
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM cancelled_interview_records WHERE project_id=? ORDER BY interview_date",
        (project_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_interviewer_code_set() -> set:
    """Return the set of all known interviewer_codes in the registry."""
    if not db_available():
        return set()
    conn = get_conn()
    rows = conn.execute("SELECT interviewer_code FROM interviewers").fetchall()
    conn.close()
    return {r["interviewer_code"] for r in rows}


# ── Upload log ─────────────────────────────────────────────────────────────────

def get_upload_log(project_id: Optional[int] = None) -> list:
    if not db_available():
        return []
    conn = get_conn()
    if project_id:
        rows = conn.execute(
            """SELECT ul.*, u.full_name as uploader_name FROM upload_log ul
               LEFT JOIN users u ON u.id=ul.uploaded_by
               WHERE ul.project_id=? ORDER BY ul.upload_date DESC""",
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
    conn.execute(f"DELETE FROM {table} WHERE upload_id=?", (upload_id,))
    conn.execute("DELETE FROM upload_log WHERE upload_id=?", (upload_id,))
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
        "SELECT upload_id FROM upload_log WHERE project_id=? AND wave_label=? AND report_type=?",
        (project_id, wave_label, report_type),
    ).fetchall()]
    if upload_ids:
        ph = ",".join("?" * len(upload_ids))
        conn.execute(f"DELETE FROM {table} WHERE upload_id IN ({ph})", upload_ids)
        conn.execute(f"DELETE FROM upload_log WHERE upload_id IN ({ph})", upload_ids)
        conn.commit()
    conn.close()


# ── Dashboard summary ──────────────────────────────────────────────────────────

def get_dashboard_summary() -> list:
    """Summary stats for all projects — used on the main dashboard overview."""
    if not db_available():
        return []
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
            "FROM quality_report_records WHERE project_id=?",
            (pid,),
        ).fetchone()

        bc = conn.execute(
            "SELECT COUNT(*) as total FROM backcheck_records WHERE project_id=?",
            (pid,),
        ).fetchone()

        perf = conn.execute(
            "SELECT SUM(accompaniments) as accompaniments, "
            "SUM(interview_completes) as completes "
            "FROM performance_records WHERE project_id=?",
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
            "SELECT COUNT(*) as total FROM listen_in_records WHERE project_id=?",
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


# ── Activity feed ──────────────────────────────────────────────────────────────

def init_tables():
    """Create extended tables and apply additive migrations."""
    if not db_available():
        return
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS supervisors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            region TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS interviewers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            interviewer_code TEXT UNIQUE NOT NULL,
            name TEXT,
            supervisor_id INTEGER REFERENCES supervisors(id) ON DELETE SET NULL,
            region TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    # Additive migrations — safe to run repeatedly
    try:
        conn.execute("ALTER TABLE users ADD COLUMN interviewer_code TEXT")
    except Exception:
        pass
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
                VALUES (?,?,?,{','.join('?' * len(cols))})""",
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
                VALUES (?,?,?,{','.join('?' * len(cols))})""",
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
                VALUES (?,?,?,{','.join('?' * len(cols))})""",
            (project_id, uid, uploaded_by, *[r.get(c) for c in cols]),
        )
    _log_upload(conn, uid, project_id, "cancelled_interviews", uploaded_by, filename, len(records), wave_label)
    conn.commit()
    conn.close()
    return uid


# ── Supervisors ────────────────────────────────────────────────────────────────

def get_all_supervisors() -> list:
    if not db_available():
        return []
    conn = get_conn()
    rows = conn.execute("SELECT * FROM supervisors ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_supervisor(name: str, email: Optional[str] = None, phone: Optional[str] = None, region: Optional[str] = None) -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO supervisors (name, email, phone, region) VALUES (?,?,?,?)",
        (name, email, phone, region),
    )
    conn.commit()
    sid = cur.lastrowid
    conn.close()
    return sid


def update_supervisor(supervisor_id: int, **kwargs):
    if not kwargs:
        return
    fields = ", ".join(f"{k}=?" for k in kwargs)
    conn = get_conn()
    conn.execute(f"UPDATE supervisors SET {fields} WHERE id=?", (*kwargs.values(), supervisor_id))
    conn.commit()
    conn.close()


def delete_supervisor(supervisor_id: int):
    conn = get_conn()
    conn.execute("UPDATE interviewers SET supervisor_id=NULL WHERE supervisor_id=?", (supervisor_id,))
    conn.execute("DELETE FROM supervisors WHERE id=?", (supervisor_id,))
    conn.commit()
    conn.close()


def upsert_supervisors_bulk(names: list) -> dict:
    """Find-or-create supervisors by name. Returns {name: id} mapping."""
    if not db_available() or not names:
        return {}
    conn = get_conn()
    result: dict = {}
    for raw in names:
        name = str(raw).strip()
        if not name or name.lower() in ("none", "null", "nan", ""):
            continue
        existing = conn.execute("SELECT id FROM supervisors WHERE name=?", (name,)).fetchone()
        if existing:
            result[name] = existing["id"]
        else:
            cur = conn.execute("INSERT INTO supervisors (name) VALUES (?)", (name,))
            result[name] = cur.lastrowid
    conn.commit()
    conn.close()
    return result


# ── Interviewers ───────────────────────────────────────────────────────────────

def get_all_interviewers() -> list:
    if not db_available():
        return []
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
        "SELECT id FROM interviewers WHERE interviewer_code=?", (interviewer_code,)
    ).fetchone()
    if existing:
        conn.execute(
            """UPDATE interviewers
               SET name=COALESCE(?,name), supervisor_id=?, region=COALESCE(?,region), is_active=?
               WHERE interviewer_code=?""",
            (name, supervisor_id, region, is_active, interviewer_code),
        )
        iid = existing["id"]
    else:
        cur = conn.execute(
            "INSERT INTO interviewers (interviewer_code, name, supervisor_id, region, is_active) VALUES (?,?,?,?,?)",
            (interviewer_code, name, supervisor_id, region, is_active),
        )
        iid = cur.lastrowid
    conn.commit()
    conn.close()
    return iid


def get_interviewer_metrics(interviewer_code: str) -> dict:
    """Cross-project performance metrics for one interviewer."""
    if not db_available():
        return {}
    conn = get_conn()

    info = conn.execute("""
        SELECT i.*, s.name AS supervisor_name
        FROM interviewers i
        LEFT JOIN supervisors s ON i.supervisor_id = s.id
        WHERE i.interviewer_code=?
    """, (interviewer_code,)).fetchone()

    qr = conn.execute("""
        SELECT COUNT(*) AS total_interviews,
               SUM(CASE WHEN duration_flag='Flag' THEN 1 ELSE 0 END) AS duration_flags,
               SUM(CASE WHEN straight_lining='Flag' THEN 1 ELSE 0 END) AS sl_flags,
               SUM(CASE WHEN approval_status='Approved' THEN 1 ELSE 0 END) AS approved,
               SUM(CASE WHEN approval_status='Cancelled' THEN 1 ELSE 0 END) AS cancelled,
               AVG(duration_minutes) AS avg_duration
        FROM quality_report_records WHERE interviewer_id=?
    """, (interviewer_code,)).fetchone()

    bc = conn.execute("""
        SELECT COUNT(*) AS bc_count,
               COALESCE(SUM(error_01+error_02+error_03+error_04+error_05+error_06+error_07+
                            error_08+error_09+error_10+error_11+error_12+error_13),0) AS total_errors
        FROM backcheck_records WHERE interviewer_id=?
    """, (interviewer_code,)).fetchone()

    li = conn.execute("""
        SELECT COUNT(*) AS li_count,
               SUM(CASE WHEN result='Pass' THEN 1 ELSE 0 END) AS li_pass,
               SUM(CASE WHEN result='Fail' THEN 1 ELSE 0 END) AS li_fail
        FROM listen_in_records WHERE interviewer_id=?
    """, (interviewer_code,)).fetchone()

    by_project = conn.execute("""
        SELECT p.name AS project_name, p.id AS project_id,
               COUNT(*) AS interviews,
               SUM(CASE WHEN qr.duration_flag='Flag' THEN 1 ELSE 0 END) AS dur_flags,
               SUM(CASE WHEN qr.straight_lining='Flag' THEN 1 ELSE 0 END) AS sl_flags,
               SUM(CASE WHEN qr.approval_status='Approved' THEN 1 ELSE 0 END) AS approved
        FROM quality_report_records qr
        JOIN projects p ON qr.project_id = p.id
        WHERE qr.interviewer_id=?
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


# ── Activity feed ──────────────────────────────────────────────────────────────

def get_project_activity(project_id: Optional[int] = None, limit: int = 20) -> list:
    if not db_available():
        return []
    conn = get_conn()
    if project_id:
        rows = conn.execute(
            """SELECT ul.upload_date, ul.report_type, ul.filename, ul.row_count,
                      ul.wave_label, p.name as project_name, u.full_name as uploader
               FROM upload_log ul
               LEFT JOIN projects p ON p.id=ul.project_id
               LEFT JOIN users u ON u.id=ul.uploaded_by
               WHERE ul.project_id=?
               ORDER BY ul.upload_date DESC LIMIT ?""",
            (project_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT ul.upload_date, ul.report_type, ul.filename, ul.row_count,
                      ul.wave_label, p.name as project_name, u.full_name as uploader
               FROM upload_log ul
               LEFT JOIN projects p ON p.id=ul.project_id
               LEFT JOIN users u ON u.id=ul.uploaded_by
               ORDER BY ul.upload_date DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
