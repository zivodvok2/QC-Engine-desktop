import os

DATABASE_URL = os.environ.get("DATABASE_URL", "")

ROLES = {
    "qc_executive": "QC Executive",
    "operations_manager": "Operations Manager",
    "qc_officer": "QC Officer",
    "project_manager": "Project Manager",
    "researcher": "Researcher",
    "management": "Management",
    "other": "Other",
}

ADMIN_ROLES = {"qc_executive", "operations_manager"}
UPLOAD_ROLES = {"qc_executive", "operations_manager", "qc_officer"}
DRILLDOWN_ROLES = {"qc_executive", "operations_manager", "qc_officer", "project_manager", "researcher"}

BACKCHECK_TARGET = 0.20
LISTENIN_TARGET = 0.10
ACCOMPANIMENT_TARGET = 0.20
DURATION_MIN_THRESHOLD = 0.50

# ── Servallab design tokens ─────────────────────────────────────────────────
SL_BG        = "#0b0c0f"
SL_SURFACE   = "#111318"
SL_SURFACE2  = "#181b22"
SL_LINE      = "#1f2330"
SL_TX        = "#e8eaf2"
SL_MUTED     = "#8b90a8"
SL_ACCENT    = "#4af0a0"
SL_ACCENT_DIM = "#2ab870"
SL_CRITICAL  = "#f04a6a"
SL_WARNING   = "#f0c04a"
SL_INFO      = "#4a9ef0"
SL_PURPLE    = "#a078f0"

# Legacy aliases — keep all existing module imports working unchanged
IPSOS_NAVY   = SL_SURFACE
IPSOS_TEAL   = SL_ACCENT
IPSOS_CYAN   = SL_INFO
IPSOS_YELLOW = SL_WARNING
IPSOS_ORANGE = SL_CRITICAL

CHART_COLORS = [
    SL_ACCENT, SL_INFO, SL_WARNING, SL_CRITICAL,
    SL_PURPLE, "#26a69a", "#ef5350", "#ab47bc", "#29b6f6", "#ff7043",
]

# ── Column schemas ──────────────────────────────────────────────────────────
QUALITY_REQUIRED_COLS = [
    "INSTANCE_ID", "INTERVIEWER_ID", "INTERVIEW_DATE",
    "INTERVIEW_START_TIME", "INTERVIEW_END_TIME", "DURATION_MINUTES",
    "DURATION_FLAG", "STRAIGHT_LINING", "LONG_PAUSE",
    "REGION", "LOCATION", "SAMPLE_POINT_ID", "APPROVAL_STATUS",
]

QUALITY_OPTIONAL_COLS = [
    "GPS_STATUS", "PHONE_PRESENT", "AUDIO_PRESENT",
    "DURATION_VALIDATION", "QC_COMMENTS",
]

IFIELD_COLUMN_MAP = {
    "INSTANCE ID": "INSTANCE_ID",
    "Instance ID ": "INSTANCE_ID",
    "INTERVIEWER ID": "INTERVIEWER_ID",
    "Interviewer ID": "INTERVIEWER_ID",
    "INTERVIEW DATE_START": "INTERVIEW_DATE",
    "Interview Date": "INTERVIEW_DATE",
    "INTERVIEW START TIME": "INTERVIEW_START_TIME",
    "Interview Start Time": "INTERVIEW_START_TIME",
    "INTERVIEW END TIME": "INTERVIEW_END_TIME",
    "Interview End Time": "INTERVIEW_END_TIME",
    " DURATION_1_SYSTEM": "DURATION_MINUTES",
    "Interview length": "DURATION_MINUTES",
    "DURATION FLAG": "DURATION_FLAG",
    "STRAIGHT-LINING": "STRAIGHT_LINING",
    "STRAIGHT LINING [From iField]": "STRAIGHT_LINING",
    "LONG PAUSE [From iField]": "LONG_PAUSE",
    "Region": "REGION",
    "Sample Point ID": "SAMPLE_POINT_ID",
    "Location": "LOCATION",
    "Script Name": "PROJECT_NAME",
}

BACKCHECK_ERRORS = {
    "error_01": "Totally fraudulent interview",
    "error_02": "Different respondent name/address",
    "error_03": "Mismatched quotas (age/gender)",
    "error_04": "Wrong usership/recruitment criteria",
    "error_05": "Wrong telephone number",
    "error_06": "Unattainable/invalid telephone",
    "error_07": "Engaged/Answer machine",
    "error_08": "Refused/unable to reach respondent",
    "error_09": "Respondent doesn't remember interview",
    "error_10": "Back-check abandoned/incomplete",
    "error_11": "Wrong interview mode (paper/phone)",
    "error_12": "Voice recording permission issue",
    "error_13": "Respondent participated recently",
}

BACKCHECK_IFIELD_COL_MAP = {
    "BC instance ID": "bc_instance_id",
    "Interview Status": "interview_status",
    "Original interview instance ID": "original_instance_id",
    "Region": "region",
    "Location": "location",
    "Sample Point ID": "sample_point_id",
    "Back-checker ID": "backchecker_id",
    "Interviewer ID": "interviewer_id",
    "Script Name": "script_name",
    "Interview Date": "interview_date",
    "Interview Start Time": "interview_start_time",
    "Back-check completion date": "backcheck_date",
    "Back-check completion time": "backcheck_time",
    "(1) Totally fraudulent intervi": "error_01",
    "(2) Different respondent name ": "error_02",
    "(3) Mismatched quota(s) e.g. d": "error_03",
    "(4) Wrong usership quotas and/": "error_04",
    "(5) Wrong telephone number": "error_05",
    "(6) Unattainable/Invalid telep": "error_06",
    "(7) Engaged/Answer machine": "error_07",
    "(8) Refused/Unable to speak to": "error_08",
    "(9) Respondent does not rememb": "error_09",
    "(10) Back-check abandoned/inco": "error_10",
    "(11) CAPI interview done on Pa": "error_11",
    "(12) Voice recording permission": "error_12",
    "(13) Respondent has already pa": "error_13",
}

CANCELLED_IFIELD_COL_MAP = {
    "Instance ID ": "instance_id",
    "Region": "region",
    "Location": "location",
    "Sample Point ID": "sample_point_id",
    "Interviewer ID": "interviewer_id",
    "Script Name": "script_name",
    "Interview Date": "interview_date",
    "Interview Start Time": "start_time",
    "Interview End Time": "end_time",
    "Interview length": "interview_length",
    "Interview Active Length": "active_length",
    "Average Interview Active Length in Sample Point": "avg_length_sample_point",
    "Average Interview Active Length in Region": "avg_length_region",
    "Average Interview Active Length in Project": "avg_length_project",
    "Idle Time": "idle_time",
    "Gap to the last interview": "gap_to_last",
    "Same Day Finish": "same_day_finish",
    "QF A": "qf_a",
    "QF B": "qf_b",
    "QF C": "qf_c",
    "QF D": "qf_d",
    "QF E": "qf_e",
    "QF F": "qf_f",
    "Interviewer Performance": "interviewer_performance",
    "Interview Back-Checking Result Telephone": "backcheck_result_telephone",
    "Interview Back-Checking Result F2F in Field": "backcheck_result_f2f",
    "Interview Back-Checking Result Independent": "backcheck_result_independent",
}

PERFORMANCE_IFIELD_COL_MAP = {
    "Login": "interviewer_id",
    "Management Region": "region",
    "First Interview": "first_interview",
    "Last Interview": "last_interview",
    "Interview \ncompletes": "interview_completes",
    "Interview completes": "interview_completes",
    "Follow-Ups \ncompletes": "followup_completes",
    "Follow-Ups completes": "followup_completes",
    "ECS \ncompletes": "ecs_completes",
    "ECS completes": "ecs_completes",
    "Work Summary": "work_summary",
    "Accompaniment": "accompaniments",
    "Cancelled \nInterviews": "cancelled_interviews",
    "Cancelled Interviews": "cancelled_interviews",
    "Back-Check \nTelephone Cre": "backcheck_telephone_created",
    "Back-Check \nF2F Created": "backcheck_f2f_created",
    "Back-Check \nF2F in Field ": "backcheck_f2f_infield",
    "Total Back-Check \nInstanc": "backcheck_total",
    "Back-Checks\ncompleted": "backcheck_completed",
}
