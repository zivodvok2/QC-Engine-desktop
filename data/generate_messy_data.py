"""
Generates data/messy_survey_sample.csv — a realistic CATI dataset
that intentionally triggers every QC check in Servallab.

Run from repo root:
    python data/generate_messy_data.py
"""

import json
import random
from pathlib import Path

import numpy as np
import pandas as pd

random.seed(42)
np.random.seed(42)

# Pre-generate a pool of non-sequential IDs for normal/random rows so the
# fabrication sequential-ID check doesn't false-fire on them.
_ID_POOL = random.sample(range(10_000, 90_000), 5_000)

# ── Lookup tables ─────────────────────────────────────────────────────────────

PROVINCES   = ["Gauteng","Western Cape","KwaZulu-Natal","Eastern Cape",
                "Limpopo","Mpumalanga","North West","Free State","Northern Cape"]
GENDERS     = ["Male","Female","Other"]
EMPLOYMENT  = ["Employed","Unemployed","Student","Retired"]
MARITAL     = ["Single","Married","Divorced","Widowed"]
OPEN_GOOD   = [
    "The service was very helpful and professional overall.",
    "I enjoyed the experience and would recommend it to others.",
    "Could be improved in some areas but generally satisfactory.",
    "Very satisfied with the overall quality of the service.",
    "Staff were friendly, responsive, and easy to work with.",
    "The process was straightforward and well explained to me.",
    "Reasonable experience, though waiting times were a bit long.",
    "Good service delivery, the staff were knowledgeable.",
]
OPEN_JUNK   = [
    "asdfghjkl",
    "aaaaaaaaaaaaa",
    "1234567890 xyz ???",
    ".",
    "no comment lol lol lol lol lol",
    "n/a n/a n/a n/a",
    "test test test",
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def good_phone():
    prefix = random.choice(["060","061","062","063","064","071","072","073",
                             "074","076","079","081","082","083","084"])
    return prefix + str(random.randint(1000000, 9999999))

def bad_phone():
    return random.choice(["08012ABCDE","CALL ME BACK","N/A","0000000000",
                           "123-456-ABC","none","+(27) ???"])

def rand_date():
    import datetime
    start = datetime.date(2024, 6, 1)
    return str(start + datetime.timedelta(days=random.randint(0, 150)))

def make_row(respondent_id, interviewer_id,
             age=None, gender=None, province=None,
             duration=None, consent="Yes",
             monthly_income=None, income_null=False,
             phone=None, email=None,
             straightline=False, fixed_income=None,
             open_text=None):

    age      = age      if age      is not None else random.randint(22, 68)
    gender   = gender   or random.choice(GENDERS)
    province = province or random.choice(PROVINCES)
    duration = duration if duration is not None else random.randint(14, 30)

    if income_null:
        monthly_income = None
    elif fixed_income is not None:
        monthly_income = fixed_income
    elif monthly_income is None:
        monthly_income = random.randint(5_000, 45_000) if random.random() > 0.25 else None

    if straightline:
        qs = {f"Q{i}": 3 for i in range(1, 11)}
    else:
        qs = {f"Q{i}": random.randint(1, 5) for i in range(1, 11)}

    return {
        "respondent_id":    respondent_id,
        "interviewer_id":   interviewer_id,
        "interview_date":   rand_date(),
        "duration_minutes": duration,
        "consent":          consent,
        "age":              age,
        "gender":           gender,
        "province":         province,
        "phone":            phone or good_phone(),
        "email":            email or f"resp{respondent_id}@survey.co.za",
        "employment_status":random.choice(EMPLOYMENT),
        "monthly_income":   monthly_income,
        "marital_status":   random.choice(MARITAL),
        **qs,
        "open_ended":       open_text or random.choice(OPEN_GOOD),
    }


# ══════════════════════════════════════════════════════════════════════════════
# Build the dataset
# ══════════════════════════════════════════════════════════════════════════════

rows   = []
_pool  = iter(_ID_POOL)

def next_rid():
    return next(_pool)

# ── INT001–INT007: clean interviewers, varied counts ─────────────────────────
int_counts = {"INT001":10,"INT002":12,"INT003":11,"INT004":13,
              "INT005":12,"INT006":10,"INT007":11}

for int_id, n in int_counts.items():
    for _ in range(n):
        rows.append(make_row(next_rid(), int_id))

# ── INT_FAST: duration anomaly + productivity anomaly (only 3 interviews) ────
for _ in range(3):
    rows.append(make_row(next_rid(), "INT_FAST", duration=random.randint(2, 3)))

# ── INT_HIGH: productivity anomaly (55 interviews) ───────────────────────────
# First 6 rows share the same demographic combo (near-duplicate trigger)
for i in range(55):
    if i < 6:
        rows.append(make_row(next_rid(), "INT_HIGH", age=30, gender="Female",
                             province="Gauteng"))
    else:
        rows.append(make_row(next_rid(), "INT_HIGH"))

# ── INT_FAKE: fabrication (sequential IDs, straightlining, low variance) ─────
for seq_id in range(5001, 5013):           # 12 consecutive IDs → fabrication flag
    rows.append(make_row(
        seq_id, "INT_FAKE",
        straightline=True,                 # straightlining flag
        fixed_income=15000,                # near-zero variance on monthly_income
    ))

# ══════════════════════════════════════════════════════════════════════════════
# Targeted dirty injections
# ══════════════════════════════════════════════════════════════════════════════

# 1. Age below valid range (range_check)
rows.append(make_row(next_rid(), "INT001", age=7))
# 2. Age above valid range (range_check)
rows.append(make_row(next_rid(), "INT002", age=215))
# 3. Age 16 + has income → logic violation (age<18 → income must be null)
rows.append(make_row(next_rid(), "INT003", age=16, monthly_income=12000))
# 4. Duration too short (duration_check)
rows.append(make_row(next_rid(), "INT004", duration=1))
# 5. Duration too long (duration_check)
rows.append(make_row(next_rid(), "INT005", duration=290))
# 6-7. Invalid phone format (pattern_check)
r6 = make_row(next_rid(), "INT006"); r6["phone"] = bad_phone(); rows.append(r6)
r7 = make_row(next_rid(), "INT007"); r7["phone"] = "CALL ME BACK"; rows.append(r7)
# 8. IQR outlier income (anomaly_check)
rows.append(make_row(next_rid(), "INT001", monthly_income=9_500_000))
# 9-11. Consent = "Refused" but Q1-Q10 filled (consent_eligibility_check)
# NOTE: use "Refused" not "No" — the cleaner converts Yes/No → bool True/False
for _ in range(3):
    rows.append(make_row(next_rid(), "INT002", consent="Refused"))
# 12. Exact duplicate of row 0 (duplicate_check)
rows.append(rows[0].copy())
# 13-14. Shared phone under two different respondent IDs (near_duplicate_check)
shared_phone = "0821111111"
rA = make_row(next_rid(), "INT003"); rA["phone"] = shared_phone; rows.append(rA)
rB = make_row(next_rid(), "INT004"); rB["phone"] = shared_phone; rows.append(rB)
# 15-17. Gibberish open-ended responses (verbatim_quality_check)
for int_id in ["INT001", "INT005", "INT006"]:
    r = make_row(next_rid(), int_id, open_text=random.choice(OPEN_JUNK))
    rows.append(r)

# ══════════════════════════════════════════════════════════════════════════════
# Inject missing values into normal rows to push above threshold
# (missing_value_check / high_missing_column_check)
# ══════════════════════════════════════════════════════════════════════════════

normal_indices = list(range(0, 79))   # INT001–INT007 rows

# Null age in ~14 rows (≈18% of normal rows → above a 10% threshold)
for idx in random.sample(normal_indices, 14):
    rows[idx]["age"] = None

# Null phone in ~17 rows
remaining = [i for i in normal_indices if rows[i]["age"] is not None]
for idx in random.sample(remaining, 17):
    rows[idx]["phone"] = None

# ══════════════════════════════════════════════════════════════════════════════
# Build DataFrame and save
# ══════════════════════════════════════════════════════════════════════════════

df = pd.DataFrame(rows)

# Ensure correct dtypes for numeric columns
for col in ["age", "duration_minutes", "monthly_income"] + [f"Q{i}" for i in range(1, 11)]:
    df[col] = pd.to_numeric(df[col], errors="coerce")

out = Path(__file__).parent / "messy_survey_sample.csv"
df.to_csv(out, index=False)
print(f"Generated {len(df)} rows  →  {out}")

# ── Print a summary of what each check should catch ───────────────────────────
print("\nExpected QC flags:")
print(f"  missing_value_check        age null={df['age'].isna().sum()}, phone null={df['phone'].isna().sum()}")
print(f"  range_check (age<18/>99)   {((df['age'] < 18) | (df['age'] > 99)).sum()} rows")
print(f"  duration_check             {((df['duration_minutes'] < 8) | (df['duration_minutes'] > 60)).sum()} rows")
print(f"  logic_check (age<18+inc)   {((df['age'] < 18) & df['monthly_income'].notna()).sum()} rows")
print(f"  duplicate_check            1 exact duplicate injected")
print(f"  pattern_check (phone)      2+ invalid phone rows")
print(f"  anomaly_check (income IQR) 1 row with income=9,500,000")
print(f"  straightlining             {(df['interviewer_id'] == 'INT_FAKE').sum()} rows (INT_FAKE)")
print(f"  consent_eligibility        3 rows (consent=No + Q answers filled)")
print(f"  fabrication (seq IDs)      12 consecutive IDs (5001–5012, INT_FAKE)")
print(f"  fabrication (low variance) INT_FAKE monthly_income all = 15000")
print(f"  interviewer_duration       INT_FAST avg ~2 min vs peer avg ~20 min")
print(f"  interviewer_productivity   INT_HIGH={df[df['interviewer_id']=='INT_HIGH'].shape[0]} interviews vs normal ~11")
print(f"  near_dup (shared phone)    phone 0821111111 under 2 respondent IDs")
print(f"  near_dup (demo combo)      age=30/Female/Gauteng appears 6 times")
print(f"  verbatim_quality           3 gibberish open_ended responses")
