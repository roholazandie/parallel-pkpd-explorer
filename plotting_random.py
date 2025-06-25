import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import random

# Path to the uploaded SQLite file
db_path = "cvt_db_20210607.sqlite"

# Connect to the database
conn = sqlite3.connect(db_path)

# Choose species and pick a random subject and series
species = "human"

subject_ids = pd.read_sql_query(
    "SELECT id FROM subjects WHERE species = ?", conn, params=(species,)
)
random_subject_id = random.choice(subject_ids['id'].tolist())

series_ids = pd.read_sql_query(
    "SELECT id FROM series WHERE fk_subject_id = ?", conn, params=(random_subject_id,)
)
random_series_id = random.choice(series_ids['id'].tolist())

# Fetch and sort the concentration–time data
conc_time_df = pd.read_sql_query(
    """
    SELECT time_hr, conc
    FROM conc_time_values
    WHERE fk_series_id = ?
    """,
    conn,
    params=(random_series_id,),
)

# Ensure numeric types
conc_time_df['time_hr'] = conc_time_df['time_hr'].astype(float)
conc_time_df['conc']    = conc_time_df['conc'].astype(float)

# **Sort by time before plotting**
conc_time_df = conc_time_df.sort_values(by='time_hr').reset_index(drop=True)

# Plot
plt.figure(figsize=(10, 6))
plt.plot(
    conc_time_df['time_hr'],
    conc_time_df['conc'],
    marker='o',
    linestyle='-',
)
plt.title(f"Concentration vs. Time for Subject {random_subject_id} ({species})")
plt.xlabel("Time (hr)")
plt.ylabel("Concentration")
plt.grid(True)
plt.tight_layout()
plt.show()
