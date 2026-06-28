import sqlite3
import uuid
from datetime import datetime
from config import DB_PATH


def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        full_name TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'other',
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        created_by INTEGER REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        created_by INTEGER REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS project_assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        assigned_by INTEGER REFERENCES users(id),
        assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(project_id, user_id)
    );

    CREATE TABLE IF NOT EXISTS quality_report_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    );

    CREATE TABLE IF NOT EXISTS listen_in_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    );

    CREATE TABLE IF NOT EXISTS backcheck_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    );

    CREATE TABLE IF NOT EXISTS cancelled_interview_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    );

    CREATE TABLE IF NOT EXISTS performance_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    );

    CREATE TABLE IF NOT EXISTS timing_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
        upload_id TEXT NOT NULL,
        uploaded_by INTEGER REFERENCES users(id),
        upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        instance_id TEXT,
        interviewer_id TEXT,
        region TEXT,
        interview_date DATE,
        duration_minutes REAL
    );

    CREATE TABLE IF NOT EXISTS upload_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        upload_id TEXT NOT NULL,
        project_id INTEGER REFERENCES projects(id),
        report_type TEXT NOT NULL,
        uploaded_by INTEGER REFERENCES users(id),
        upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        filename TEXT,
        row_count INTEGER DEFAULT 0,
        notes TEXT
    );
    """)
    conn.commit()

    # ── Migrations for existing DBs ────────────────────────────────────────
    _safe_add_column(conn, "quality_report_records", "extra_data", "TEXT")
    _safe_add_column(conn, "upload_log", "notes", "TEXT")
    _safe_add_column(conn, "upload_log", "wave_label", "TEXT")
    _safe_add_column(conn, "projects", "job_number", "TEXT")
    _safe_add_column(conn, "projects", "loi_min_minutes", "REAL DEFAULT 0")
    _safe_add_column(conn, "projects", "loi_pct_threshold", "REAL DEFAULT 0.50")
    _safe_add_column(conn, "projects", "flag_warning_pct", "REAL DEFAULT 5.0")
    _safe_add_column(conn, "projects", "flag_critical_pct", "REAL DEFAULT 10.0")

    # Seed a default admin if no users exist
    existing = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if existing == 0:
        import bcrypt
        pw = bcrypt.hashpw(b"admin1234", bcrypt.gensalt()).decode()
        c.execute(
            "INSERT INTO users (email, password_hash, full_name, role) VALUES (?,?,?,?)",
            ("admin@servallab.com", pw, "System Admin", "qc_executive"),
        )
        conn.commit()

    conn.close()


def _safe_add_column(conn, table: str, column: str, col_type: str):
    """Add column to table only if it doesn't already exist."""
    try:
        existing = [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
            conn.commit()
    except Exception:
        pass


# ── Users ──────────────────────────────────────────────────────────────────

def get_user_by_email(email: str):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE email=? AND is_active=1", (email,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_users():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM users ORDER BY full_name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_user(email, password_hash, full_name, role, created_by=None):
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


def update_user_role(user_id, role):
    conn = get_conn()
    conn.execute("UPDATE users SET role=? WHERE id=?", (role, user_id))
    conn.commit()
    conn.close()


def toggle_user_active(user_id, is_active):
    conn = get_conn()
    conn.execute("UPDATE users SET is_active=? WHERE id=?", (is_active, user_id))
    conn.commit()
    conn.close()


def update_user_password(user_id, new_hash):
    conn = get_conn()
    conn.execute("UPDATE users SET password_hash=? WHERE id=?", (new_hash, user_id))
    conn.commit()
    conn.close()


# ── Projects ───────────────────────────────────────────────────────────────

def get_all_projects():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM projects ORDER BY status, name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_project(project_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_project(name, client, sample_target, start_date, end_date,
                   backcheck_target, listenin_target, accompaniment_target, created_by,
                   job_number=None, loi_min_minutes=0, loi_pct_threshold=0.50,
                   flag_warning_pct=5.0, flag_critical_pct=10.0):
    conn = get_conn()
    conn.execute(
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
    conn.commit()
    conn.close()


def update_project(project_id, **kwargs):
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


def get_user_projects(user_id, role):
    """Return projects visible to this user based on role."""
    conn = get_conn()
    if role in ("qc_executive", "operations_manager", "management", "other"):
        rows = conn.execute("SELECT * FROM projects ORDER BY status, name").fetchall()
    else:
        rows = conn.execute(
            """SELECT p.* FROM projects p
               JOIN project_assignments pa ON pa.project_id=p.id
               WHERE pa.user_id=? ORDER BY p.status, p.name""",
            (user_id,),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def assign_user_to_project(project_id, user_id, assigned_by):
    conn = get_conn()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO project_assignments (project_id, user_id, assigned_by) VALUES (?,?,?)",
            (project_id, user_id, assigned_by),
        )
        conn.commit()
    finally:
        conn.close()


def remove_user_from_project(project_id, user_id):
    conn = get_conn()
    conn.execute(
        "DELETE FROM project_assignments WHERE project_id=? AND user_id=?",
        (project_id, user_id),
    )
    conn.commit()
    conn.close()


def get_project_assignees(project_id):
    conn = get_conn()
    rows = conn.execute(
        """SELECT u.id, u.email, u.full_name, u.role FROM users u
           JOIN project_assignments pa ON pa.user_id=u.id
           WHERE pa.project_id=?""",
        (project_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def user_can_drilldown(user_id, project_id, role):
    from config import ADMIN_ROLES, DRILLDOWN_ROLES
    if role in ADMIN_ROLES:
        return True
    if role not in DRILLDOWN_ROLES:
        return False
    conn = get_conn()
    row = conn.execute(
        "SELECT 1 FROM project_assignments WHERE project_id=? AND user_id=?",
        (project_id, user_id),
    ).fetchone()
    conn.close()
    return row is not None


# ── Data insertion helpers ─────────────────────────────────────────────────

def _log_upload(conn, upload_id, project_id, report_type, uploaded_by, filename, row_count, wave_label=None):
    conn.execute(
        """INSERT INTO upload_log (upload_id, project_id, report_type, uploaded_by, filename, row_count, wave_label)
           VALUES (?,?,?,?,?,?,?)""",
        (upload_id, project_id, report_type, uploaded_by, filename, row_count, wave_label or None),
    )


def insert_quality_records(project_id, uploaded_by, filename, records: list[dict], wave_label=None):
    import json
    uid = str(uuid.uuid4())
    conn = get_conn()
    std_cols = [
        "instance_id", "interviewer_id", "interview_date", "start_time", "end_time",
        "duration_minutes", "duration_validation", "duration_flag",
        "straight_lining", "long_pause", "gps_status", "phone_present", "audio_present",
        "region", "location", "sample_point_id", "approval_status", "qc_comments",
    ]
    all_cols = std_cols + ["extra_data"]
    for r in records:
        extra = {k: v for k, v in r.items() if k not in std_cols and k not in ("id", "project_id", "upload_id", "uploaded_by", "upload_date")}
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


def insert_backcheck_records(project_id, uploaded_by, filename, records: list[dict], wave_label=None):
    uid = str(uuid.uuid4())
    conn = get_conn()
    error_cols = [f"error_{i:02d}" for i in range(1, 14)]
    base_cols = ["bc_instance_id", "original_instance_id", "interview_status",
                 "region", "location", "sample_point_id", "backchecker_id",
                 "interviewer_id", "script_name", "interview_date",
                 "interview_start_time", "backcheck_date", "backcheck_time"]
    all_cols = base_cols + error_cols
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


def insert_cancelled_records(project_id, uploaded_by, filename, records: list[dict], wave_label=None):
    uid = str(uuid.uuid4())
    conn = get_conn()
    cols = [
        "instance_id", "region", "location", "sample_point_id", "interviewer_id",
        "script_name", "interview_date", "start_time", "end_time",
        "interview_length", "active_length", "avg_length_sample_point",
        "avg_length_region", "avg_length_project", "idle_time", "gap_to_last",
        "same_day_finish", "qf_a", "qf_b", "qf_c", "qf_d", "qf_e", "qf_f",
        "interviewer_performance", "backcheck_result_telephone",
        "backcheck_result_f2f", "backcheck_result_independent",
    ]
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


def insert_performance_records(project_id, uploaded_by, filename, records: list[dict], wave_label=None):
    uid = str(uuid.uuid4())
    conn = get_conn()
    cols = [
        "interviewer_id", "region", "first_interview", "last_interview",
        "interview_completes", "followup_completes", "ecs_completes",
        "work_summary", "accompaniments", "cancelled_interviews",
        "backcheck_telephone_created", "backcheck_f2f_created",
        "backcheck_f2f_infield", "backcheck_total", "backcheck_completed",
    ]
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


def insert_timing_records(project_id, uploaded_by, filename, records: list[dict], wave_label=None):
    uid = str(uuid.uuid4())
    conn = get_conn()
    cols = ["instance_id", "interviewer_id", "region", "interview_date", "duration_minutes"]
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


def get_quality_instance_ids(project_id) -> set:
    """Return the set of instance_ids already stored for a project."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT DISTINCT instance_id FROM quality_report_records WHERE project_id=? AND instance_id IS NOT NULL",
        (project_id,),
    ).fetchall()
    conn.close()
    return {r["instance_id"] for r in rows}


def delete_wave_records(project_id, wave_label, report_type):
    """Delete all records for a specific wave label within a project."""
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
        conn.execute(
            f"DELETE FROM upload_log WHERE upload_id IN ({ph})", upload_ids
        )
        conn.commit()
    conn.close()


def delete_upload(upload_id, report_type):
    table_map = {
        "quality_report": "quality_report_records",
        "backcheck": "backcheck_records",
        "cancelled_interviews": "cancelled_interview_records",
        "performance": "performance_records",
        "timing": "timing_records",
    }
    table = table_map.get(report_type)
    if not table:
        return
    conn = get_conn()
    conn.execute(f"DELETE FROM {table} WHERE upload_id=?", (upload_id,))
    conn.execute("DELETE FROM upload_log WHERE upload_id=?", (upload_id,))
    conn.commit()
    conn.close()


# ── Data retrieval ─────────────────────────────────────────────────────────

def get_quality_records(project_id) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM quality_report_records WHERE project_id=? ORDER BY interview_date, interviewer_id",
        (project_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_backcheck_records(project_id) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM backcheck_records WHERE project_id=? ORDER BY interview_date",
        (project_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_cancelled_records(project_id) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM cancelled_interview_records WHERE project_id=? ORDER BY interview_date",
        (project_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_performance_records(project_id) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM performance_records WHERE project_id=? ORDER BY region, interviewer_id",
        (project_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_timing_records(project_id) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM timing_records WHERE project_id=? ORDER BY interview_date",
        (project_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_upload_log(project_id=None) -> list[dict]:
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


def get_dashboard_summary():
    """Summary stats for all projects — used on the main dashboard."""
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

        acc = perf["accompaniments"] or 0
        completes = perf["completes"] or 0
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


# ── Listen-in ───────────────────────────────────────────────────────────────

def get_listen_in_records(project_id) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM listen_in_records WHERE project_id=? ORDER BY listen_date DESC",
        (project_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def insert_listen_in_record(project_id, logged_by, instance_id, interviewer_id,
                             region, listen_date, listen_type, result,
                             issues_noted, action_taken, upload_id=None):
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


def insert_listen_in_batch(project_id, logged_by, filename, records: list[dict], wave_label=None):
    import uuid as _uuid
    uid = str(_uuid.uuid4())
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


def delete_listen_in_record(record_id):
    conn = get_conn()
    conn.execute("DELETE FROM listen_in_records WHERE id=?", (record_id,))
    conn.commit()
    conn.close()


# ── Wave comparison ────────────────────────────────────────────────────────

def get_project_waves(project_id) -> list[str]:
    """Return distinct wave labels for a project, ordered."""
    conn = get_conn()
    rows = conn.execute(
        """SELECT DISTINCT wave_label FROM upload_log
           WHERE project_id=? AND wave_label IS NOT NULL AND wave_label != ''
           ORDER BY wave_label""",
        (project_id,),
    ).fetchall()
    conn.close()
    return [r["wave_label"] for r in rows]


def get_wave_comparison_data(project_id) -> list[dict]:
    """Per-wave aggregated metrics for wave comparison charts."""
    conn = get_conn()
    waves = conn.execute(
        """SELECT DISTINCT wave_label FROM upload_log
           WHERE project_id=? AND wave_label IS NOT NULL AND wave_label != ''
           ORDER BY wave_label""",
        (project_id,),
    ).fetchall()

    result = []
    for wave_row in waves:
        wave = wave_row["wave_label"]

        # Quality report metrics for this wave
        qr_ids = [r["upload_id"] for r in conn.execute(
            "SELECT upload_id FROM upload_log WHERE project_id=? AND wave_label=? AND report_type='quality_report'",
            (project_id, wave),
        ).fetchall()]

        if qr_ids:
            ph = ",".join("?" * len(qr_ids))
            qr = conn.execute(
                f"""SELECT COUNT(*) as total,
                    SUM(CASE WHEN approval_status='Approved' THEN 1 ELSE 0 END) as approved,
                    SUM(CASE WHEN duration_flag='Flag' THEN 1 ELSE 0 END) as flagged,
                    AVG(duration_minutes) as avg_duration,
                    COUNT(DISTINCT interviewer_id) as interviewers,
                    COUNT(DISTINCT interview_date) as active_days
                    FROM quality_report_records
                    WHERE project_id=? AND upload_id IN ({ph})""",
                (project_id, *qr_ids),
            ).fetchone()
        else:
            qr = None

        total = (qr["total"] or 0) if qr else 0
        approved = (qr["approved"] or 0) if qr else 0
        flagged = (qr["flagged"] or 0) if qr else 0
        avg_dur = float(qr["avg_duration"] or 0) if qr else 0.0
        interviewers = (qr["interviewers"] or 0) if qr else 0
        active_days = max((qr["active_days"] or 1) if qr else 1, 1)
        error_rate = round(flagged / total * 100, 1) if total else 0.0
        productivity = round(approved / active_days, 1)

        # Back-check metrics for this wave
        bc_ids = [r["upload_id"] for r in conn.execute(
            "SELECT upload_id FROM upload_log WHERE project_id=? AND wave_label=? AND report_type='backcheck'",
            (project_id, wave),
        ).fetchall()]
        if bc_ids:
            ph = ",".join("?" * len(bc_ids))
            bc_count = conn.execute(
                f"SELECT COUNT(*) as n FROM backcheck_records WHERE project_id=? AND upload_id IN ({ph})",
                (project_id, *bc_ids),
            ).fetchone()["n"] or 0
        else:
            bc_count = 0
        bc_rate = round(bc_count / approved * 100, 1) if approved else 0.0

        # Listen-in metrics for this wave
        li_ids = [r["upload_id"] for r in conn.execute(
            "SELECT upload_id FROM upload_log WHERE project_id=? AND wave_label=? AND report_type='listen_in'",
            (project_id, wave),
        ).fetchall()]
        if li_ids:
            ph = ",".join("?" * len(li_ids))
            li_count = conn.execute(
                f"SELECT COUNT(*) as n FROM listen_in_records WHERE project_id=? AND upload_id IN ({ph})",
                (project_id, *li_ids),
            ).fetchone()["n"] or 0
        else:
            li_count = 0
        li_rate = round(li_count / approved * 100, 1) if approved else 0.0

        result.append({
            "wave": wave,
            "total_interviews": total,
            "approved": approved,
            "flagged": flagged,
            "error_rate": error_rate,
            "avg_duration": round(avg_dur, 1),
            "productivity": productivity,
            "bc_count": bc_count,
            "bc_rate": bc_rate,
            "li_count": li_count,
            "li_rate": li_rate,
            "interviewers": interviewers,
        })

    conn.close()
    return result


def get_at_risk_interviewers_cross_project(min_interviews: int = 5, flag_pct_threshold: float = 15.0) -> list[dict]:
    """Return interviewers with high QC flag rates across all projects."""
    conn = get_conn()
    rows = conn.execute(
        """SELECT
               interviewer_id,
               COUNT(*) as total_interviews,
               COUNT(DISTINCT project_id) as project_count,
               SUM(CASE WHEN LOWER(duration_flag) = 'flag' THEN 1 ELSE 0 END) as duration_flags,
               SUM(CASE WHEN straight_lining IS NOT NULL
                        AND TRIM(straight_lining) != ''
                        AND LOWER(TRIM(straight_lining)) NOT IN ('0','no','false','none')
                   THEN 1 ELSE 0 END) as sl_flags
           FROM quality_report_records
           WHERE interviewer_id IS NOT NULL AND TRIM(interviewer_id) != ''
           GROUP BY interviewer_id
           HAVING total_interviews >= ?
           ORDER BY (duration_flags + sl_flags) * 1.0 / total_interviews DESC""",
        (min_interviews,),
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        total = d["total_interviews"] or 1
        total_flags = (d["duration_flags"] or 0) + (d["sl_flags"] or 0)
        flag_rate = round(total_flags / total * 100, 1)
        d["total_flags"] = total_flags
        d["flag_rate_pct"] = flag_rate
        if flag_rate >= flag_pct_threshold:
            result.append(d)
    return result


def get_interviewer_cross_project_count() -> list[dict]:
    """Return how many distinct projects each interviewer has appeared in across performance records."""
    conn = get_conn()
    rows = conn.execute(
        """SELECT interviewer_id,
                  COUNT(DISTINCT project_id) as project_count,
                  SUM(interview_completes) as total_completes
           FROM performance_records
           WHERE interviewer_id IS NOT NULL AND interviewer_id != ''
           GROUP BY interviewer_id
           ORDER BY project_count DESC, total_completes DESC""",
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Activity feed ──────────────────────────────────────────────────────────

def get_all_interviewers() -> list[dict]:
    conn = get_conn()
    rows = conn.execute("""
        SELECT i.*, s.name AS supervisor_name
        FROM interviewers i
        LEFT JOIN supervisors s ON i.supervisor_id = s.id
        ORDER BY i.interviewer_code
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_supervisors() -> list[dict]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM supervisors ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_project_activity(project_id=None, limit=20) -> list[dict]:
    """Recent upload activity, optionally filtered to one project."""
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
