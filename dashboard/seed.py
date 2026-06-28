"""
Demo data seeder.
Called automatically by app.py on first run when no projects exist.
"""

import random
from datetime import date, timedelta
import database as db

_RNG = random.Random(42)


def _rdate(start: date, end: date) -> str:
    return str(start + timedelta(days=_RNG.randint(0, max(0, (end - start).days))))


def _rtime(h0=8, h1=17):
    return f"{_RNG.randint(h0,h1-1):02d}:{_RNG.randint(0,59):02d}:{_RNG.randint(0,59):02d}"


def _add_minutes(t: str, mins: float) -> str:
    h, m, s = map(int, t.split(":"))
    total = h * 3600 + m * 60 + s + int(mins * 60)
    return f"{total//3600:02d}:{(total%3600)//60:02d}:{total%60:02d}"


PROJECTS = [
    {
        "name": "Consumer Satisfaction Survey 2025",
        "client": "Unilever Kenya",
        "sample_target": 500,
        "start_date": "2025-02-01",
        "end_date": "2025-05-31",
        "status": "active",
        "backcheck_target": 0.20,
        "listenin_target": 0.10,
        "accompaniment_target": 0.20,
        "regions": ["Nairobi", "Mombasa", "Kisumu", "Nakuru"],
        "interviewers": ["NB0664", "NB0712", "MSA0234", "KSM0891", "NAK0445", "NB0991"],
        "waves": [
            ("Wave 1", date(2025, 2, 1),  date(2025, 2, 28),  120, 0.083, 0.82),
            ("Wave 2", date(2025, 3, 1),  date(2025, 3, 31),  180, 0.055, 0.87),
            ("Wave 3", date(2025, 4, 1),  date(2025, 4, 25),  150, 0.047, 0.89),
        ],
    },
    {
        "name": "National Youth Survey 2025",
        "client": "UNICEF Kenya",
        "sample_target": 800,
        "start_date": "2025-03-01",
        "end_date": "2025-06-30",
        "status": "active",
        "backcheck_target": 0.25,
        "listenin_target": 0.15,
        "accompaniment_target": 0.25,
        "regions": ["Nairobi", "Kisumu", "Eldoret", "Meru", "Nyeri"],
        "interviewers": ["NB1001", "NB1002", "KSM1003", "ELD1004", "MER1005", "NYR1006", "NB1007", "KSM1008"],
        "waves": [
            ("Wave 1", date(2025, 3, 1),  date(2025, 3, 31),  200, 0.060, 0.84),
            ("Wave 2", date(2025, 4, 1),  date(2025, 4, 30),  180, 0.078, 0.85),
        ],
    },
    {
        "name": "Media Habits Tracker Q1 2025",
        "client": "Nation Media Group",
        "sample_target": 300,
        "start_date": "2025-01-15",
        "end_date": "2025-03-31",
        "status": "completed",
        "backcheck_target": 0.20,
        "listenin_target": 0.10,
        "accompaniment_target": 0.20,
        "regions": ["Nairobi", "Mombasa"],
        "interviewers": ["NB0501", "NB0502", "MSA0503", "NB0504"],
        "waves": [
            ("Wave 1", date(2025, 1, 15), date(2025, 1, 31),  80,  0.092, 0.81),
            ("Wave 2", date(2025, 2, 1),  date(2025, 2, 28),  120, 0.058, 0.88),
            ("Wave 3", date(2025, 3, 1),  date(2025, 3, 31),  115, 0.042, 0.91),
        ],
    },
]

_LISTEN_TYPES  = ["Telephone", "F2F / Accompaniment", "Audio Playback"]
_LISTEN_ISSUES = [
    "Interviewer skipped key probes",
    "Background noise affecting audio quality",
    "Respondent appeared rushed",
    "Interviewer read out response options prematurely",
    "",
]


def _quality(pid, admin_id, interviewers, regions, wave, start, end,
             n, flagged_pct, approved_pct):
    n_flagged   = round(n * flagged_pct)
    n_approved  = round(n * approved_pct)
    n_cancelled = round(n * 0.04)
    avg_dur = _RNG.uniform(22, 35)
    records = []
    for i in range(n):
        iv  = _RNG.choice(interviewers)
        reg = _RNG.choice(regions)
        d   = _rdate(start, end)
        st  = _rtime(8, 16)
        dur = max(5.0, _RNG.gauss(avg_dur, avg_dur * 0.25))
        gps_r = _RNG.random()
        records.append({
            "instance_id":      f"ID{pid}{i+1:05d}",
            "interviewer_id":   iv,
            "interview_date":   d,
            "start_time":       st,
            "end_time":         _add_minutes(st, dur),
            "duration_minutes": round(dur, 1),
            "duration_flag":    "Flag" if i < n_flagged else "Okay",
            "straight_lining":  "0" if _RNG.random() > 0.04 else "Straight-lining detected",
            "long_pause":       "0" if _RNG.random() > 0.03 else "Long pause > 10s",
            "gps_status":       "Present" if gps_r > 0.07 else ("Missing" if gps_r > 0.02 else "Duplicate"),
            "phone_present":    "Yes" if _RNG.random() > 0.05 else "No",
            "audio_present":    "Yes" if _RNG.random() > 0.04 else "No",
            "region":           reg,
            "location":         f"{reg} Zone {_RNG.randint(1,5)}",
            "sample_point_id":  f"{reg[:2].upper()}{_RNG.randint(10,99)}",
            "approval_status":  ("Approved" if i < n_approved
                                 else ("Cancelled" if i < n_approved + n_cancelled
                                       else "Pending")),
            "qc_comments": "",
        })
    _RNG.shuffle(records)
    db.insert_quality_records(pid, admin_id, f"quality_{wave}.xlsx", records, wave_label=wave)
    return [r for r in records if r["approval_status"] == "Approved"]


def _backcheck(pid, admin_id, approved, wave, bc_tgt, end):
    n_bc   = round(len(approved) * bc_tgt)
    sample = _RNG.sample(approved, min(n_bc, len(approved)))
    recs   = []
    for r in sample:
        err  = {f"error_{i:02d}": 0 for i in range(1, 14)}
        roll = _RNG.random()
        if roll < 0.15:   err["error_07"] = 1
        elif roll < 0.25: err["error_08"] = 1
        elif roll < 0.30: err["error_09"] = 1
        elif roll < 0.32: err["error_05"] = 1
        elif roll < 0.33: err["error_01"] = 1
        iv_date = date.fromisoformat(r["interview_date"])
        recs.append({
            "bc_instance_id":       f"BC{r['instance_id']}",
            "original_instance_id": r["instance_id"],
            "interview_status":     "Completed - Pending Export",
            "region":               r["region"],
            "location":             r["location"],
            "sample_point_id":      r["sample_point_id"],
            "backchecker_id":       f"BC{_RNG.choice(['LE0018','LE0024','LE0031'])}",
            "interviewer_id":       r["interviewer_id"],
            "script_name":          "Project Survey",
            "interview_date":       r["interview_date"],
            "interview_start_time": r["start_time"],
            "backcheck_date":       _rdate(iv_date + timedelta(days=1),
                                           max(iv_date + timedelta(days=1),
                                               end + timedelta(days=7))),
            "backcheck_time":       _rtime(8, 17),
            **err,
        })
    db.insert_backcheck_records(pid, admin_id, f"backcheck_{wave}.xlsx", recs, wave_label=wave)
    return recs


def _performance(pid, admin_id, approved, wave, bc_recs):
    by_iv  = {}
    for r in approved:
        iv = r["interviewer_id"]
        by_iv.setdefault(iv, {"dates": [], "completes": 0, "region": r["region"]})
        by_iv[iv]["completes"] += 1
        by_iv[iv]["dates"].append(r["interview_date"])
    bc_by_iv = {}
    for b in bc_recs:
        bc_by_iv[b["interviewer_id"]] = bc_by_iv.get(b["interviewer_id"], 0) + 1
    perf = []
    for iv, d in by_iv.items():
        c      = d["completes"]
        bc     = bc_by_iv.get(iv, 0)
        tel_bc = round(bc * _RNG.uniform(0.55, 0.75))
        f2f_bc = bc - tel_bc
        sd     = sorted(d["dates"])
        perf.append({
            "interviewer_id":              iv,
            "region":                      d["region"],
            "first_interview":             sd[0] if sd else "",
            "last_interview":              sd[-1] if sd else "",
            "interview_completes":         c,
            "followup_completes":          round(c * _RNG.uniform(0.02, 0.08)),
            "ecs_completes":               round(c * _RNG.uniform(0.01, 0.05)),
            "work_summary":                c,
            "accompaniments":              round(c * _RNG.uniform(0.08, 0.30)),
            "cancelled_interviews":        _RNG.randint(0, 3),
            "backcheck_telephone_created": tel_bc,
            "backcheck_f2f_created":       f2f_bc,
            "backcheck_f2f_infield":       round(f2f_bc * 0.6),
            "backcheck_total":             bc,
            "backcheck_completed":         bc,
        })
    db.insert_performance_records(pid, admin_id, f"performance_{wave}.xlsx", perf, wave_label=wave)


def _listenin(pid, admin_id, approved, wave, li_tgt, end):
    n_li   = round(len(approved) * li_tgt)
    sample = _RNG.sample(approved, min(n_li, len(approved)))
    recs   = []
    for r in sample:
        roll   = _RNG.random()
        result = "Pass" if roll > 0.18 else ("Partial" if roll > 0.06 else "Fail")
        issue  = _RNG.choice(_LISTEN_ISSUES) if result != "Pass" else ""
        iv_date = date.fromisoformat(r["interview_date"])
        recs.append({
            "instance_id":    r["instance_id"],
            "interviewer_id": r["interviewer_id"],
            "region":         r["region"],
            "listen_date":    _rdate(iv_date, min(end, iv_date + timedelta(days=7))),
            "listen_type":    _RNG.choice(_LISTEN_TYPES),
            "result":         result,
            "issues_noted":   issue,
            "action_taken":   "Debrief conducted with interviewer" if issue else "",
        })
    db.insert_listen_in_batch(pid, admin_id, f"listenin_{wave}.xlsx", recs, wave_label=wave)


def _cancelled(pid, admin_id, approved, wave):
    n_c    = max(3, round(len(approved) * _RNG.uniform(0.02, 0.06)))
    sample = _RNG.sample(approved, min(n_c, len(approved)))
    recs   = []
    for r in sample:
        dur = _RNG.uniform(2, 8)
        recs.append({
            "instance_id":                  r["instance_id"],
            "region":                       r["region"],
            "location":                     r["location"],
            "sample_point_id":              r["sample_point_id"],
            "interviewer_id":               r["interviewer_id"],
            "script_name":                  "Project Survey",
            "interview_date":               r["interview_date"],
            "start_time":                   r["start_time"],
            "end_time":                     _add_minutes(r["start_time"], dur),
            "interview_length":             round(dur, 1),
            "active_length":                round(dur * 0.7, 1),
            "avg_length_sample_point":      round(_RNG.uniform(20, 30), 1),
            "avg_length_region":            round(_RNG.uniform(22, 32), 1),
            "avg_length_project":           round(_RNG.uniform(23, 31), 1),
            "idle_time":                    round(_RNG.uniform(0, 5), 1),
            "gap_to_last":                  round(_RNG.uniform(30, 600), 0),
            "same_day_finish":              _RNG.choice(["Yes", "No"]),
            "qf_a": _RNG.choice(["", "", "", "1"]),
            "qf_b": _RNG.choice(["", "", "1"]),
            "qf_c": "", "qf_d": "", "qf_e": "", "qf_f": "",
            "interviewer_performance":      _RNG.choice(["Good", "Average", "Poor"]),
            "backcheck_result_telephone":   "",
            "backcheck_result_f2f":         "",
            "backcheck_result_independent": "",
        })
    db.insert_cancelled_records(pid, admin_id, f"cancelled_{wave}.xlsx", recs, wave_label=wave)


def run():
    """Seed demo projects. Skips silently if projects already exist."""
    if db.get_all_projects():
        return

    admin    = db.get_user_by_email("admin@servallab.com")
    admin_id = admin["id"] if admin else None

    for pdef in PROJECTS:
        db.create_project(
            pdef["name"], pdef["client"], pdef["sample_target"],
            pdef["start_date"], pdef["end_date"],
            pdef["backcheck_target"], pdef["listenin_target"],
            pdef["accompaniment_target"], admin_id,
        )
        pid = next(p["id"] for p in db.get_all_projects() if p["name"] == pdef["name"])
        db.update_project(pid, status=pdef["status"])

        for wave, wstart, wend, n, flagged_pct, approved_pct in pdef["waves"]:
            bc_tgt = pdef["backcheck_target"] + _RNG.uniform(-0.03, 0.05)
            li_tgt = pdef["listenin_target"]  + _RNG.uniform(-0.02, 0.04)

            approved = _quality(pid, admin_id, pdef["interviewers"], pdef["regions"],
                                wave, wstart, wend, n, flagged_pct, approved_pct)
            bc_recs  = _backcheck(pid, admin_id, approved, wave, bc_tgt, wend)
            _performance(pid, admin_id, approved, wave, bc_recs)
            _listenin(pid, admin_id, approved, wave, li_tgt, wend)
            _cancelled(pid, admin_id, approved, wave)
