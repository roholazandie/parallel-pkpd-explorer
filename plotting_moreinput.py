import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import random

# Path to your SQLite database
db_path = "cvt_db_20210607.sqlite"
conn    = sqlite3.connect(db_path)

# === USER INPUTS ===
species      = "mouse"            # e.g. "mouse", "human", "rat"
analyte_name = "dichloromethane"  # e.g. "Caffeine", "Aspirin", etc.

# 1) Pick a random subject that has at least one series for this analyte
query_subjects = """
SELECT DISTINCT s.id
  FROM subjects AS s
  JOIN series   AS r ON s.id = r.fk_subject_id
 WHERE s.species               = ?
   AND r.analyte_name_original = ?
"""
subject_ids_df = pd.read_sql_query(query_subjects,
                                   conn,
                                   params=(species, analyte_name))
random_subject_id = random.choice(subject_ids_df['id'].tolist())

# 2) Pick a random series for that subject + analyte
query_series = """
SELECT id
  FROM series
 WHERE fk_subject_id           = ?
   AND analyte_name_original   = ?
"""
series_ids_df = pd.read_sql_query(query_series,
                                  conn,
                                  params=(random_subject_id, analyte_name))
random_series_id = random.choice(series_ids_df['id'].tolist())

# 3) Pull subject metadata
meta_df = pd.read_sql_query(
    """
    SELECT sex, age, age_category, height, weight_kg
      FROM subjects
     WHERE id = ?
    """,
    conn,
    params=(random_subject_id,)
)
meta = meta_df.iloc[0]

# 3a) Coerce numeric fields (empty or invalid → NaN)
age_num    = pd.to_numeric(meta['age'],    errors='coerce')
height_num = pd.to_numeric(meta['height'], errors='coerce')
weight_num = pd.to_numeric(meta['weight_kg'], errors='coerce')

# 3b) Build a list of non-null metadata strings
meta_parts = []
if isinstance(meta['sex'], str) and meta['sex'].strip():
    meta_parts.append(f"Sex: {meta['sex']}")
if pd.notna(age_num):
    age_str = f"Age: {int(age_num)}"
    if isinstance(meta['age_category'], str) and meta['age_category'].strip():
        age_str += f" ({meta['age_category']})"
    meta_parts.append(age_str)
if pd.notna(height_num):
    meta_parts.append(f"Height: {height_num} cm")
if pd.notna(weight_num):
    meta_parts.append(f"Weight: {weight_num} kg")

meta_line = " · ".join(meta_parts)  # empty if no metadata

# 4) Load and clean concentration–time data
conc_time_df = pd.read_sql_query(
    """
    SELECT time_hr, conc
      FROM conc_time_values
     WHERE fk_series_id = ?
    """,
    conn,
    params=(random_series_id,)
)

# 4a) Convert to numeric, coercing errors to NaN
conc_time_df['time_hr'] = pd.to_numeric(conc_time_df['time_hr'], errors='coerce')
conc_time_df['conc']    = pd.to_numeric(conc_time_df['conc'],    errors='coerce')

# 4b) Drop any rows that failed to parse
conc_time_df = conc_time_df.dropna(subset=['time_hr', 'conc'])

# 4c) Sort by time
conc_time_df = conc_time_df.sort_values(by='time_hr').reset_index(drop=True)

# 5) Plot
plt.figure(figsize=(10, 6))
plt.plot(
    conc_time_df['time_hr'],
    conc_time_df['conc'],
    marker='o',
    linestyle='-',
    label='Raw Conc'
)

# 6) Annotate
plt.suptitle(
    f"Subject {random_subject_id} · Species: {species} · Analyte: {analyte_name}",
    y=0.98,
    fontsize=12
)
if meta_line:
    plt.title(meta_line, fontsize=10)

plt.xlabel("Time (hr)")
plt.ylabel("Concentration")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()
