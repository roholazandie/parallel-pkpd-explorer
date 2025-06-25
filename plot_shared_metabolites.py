import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import ast

# === USER INPUTS ===
db_path      = "cvt_db_20210607.sqlite"
matrix_csv   = "parallel_metabolites_matrix.csv"  # CSV containing species×species lists
species1     = "mouse"
species2     = "rat"

# colors for each species
colors = {
    species1: "tab:blue",
    species2: "tab:orange"
}

# 1) Read the precomputed analyte‐intersection matrix
matrix_df = pd.read_csv(matrix_csv, index_col=0)
matrix    = matrix_df.applymap(ast.literal_eval)

# 2) Get shared metabolites for the two chosen species
shared_metabs = matrix.at[species1, species2]
if not shared_metabs:
    raise ValueError(f"No shared analytes found for {species1} & {species2}")

# 3) Open DB and collect only the metabolites that have ≥2 points for both species
conn = sqlite3.connect(db_path)
valid_entries = []  # will hold tuples (metab, {0: df1, 1: df2})

for metab in shared_metabs:
    ct_data = {}
    valid = True

    for idx, sp in enumerate([species1, species2]):
        # find the series_id with the most time‐points
        q_best = """
            SELECT r.id AS series_id,
                   COUNT(*) AS n_pts
              FROM series AS r
              JOIN subjects AS s
                ON r.fk_subject_id = s.id
              JOIN conc_time_values AS ctv
                ON r.id = ctv.fk_series_id
             WHERE LOWER(s.species)        = ?
               AND r.test_substance_dtxsid = ?
             GROUP BY r.id
             ORDER BY n_pts DESC
             LIMIT 1
        """
        best = pd.read_sql_query(q_best, conn, params=(sp.lower(), metab))

        if best.empty or best.at[0, 'n_pts'] < 2:
            valid = False
            break

        series_id = best.at[0, 'series_id']
        # load & clean concentration–time
        q_ct = """
            SELECT time_hr, conc
              FROM conc_time_values
             WHERE fk_series_id = ?
        """
        df = pd.read_sql_query(q_ct, conn, params=(series_id,))
        df['time_hr'] = pd.to_numeric(df['time_hr'], errors='coerce')
        df['conc']    = pd.to_numeric(df['conc'],    errors='coerce')
        df = (df
              .dropna(subset=['time_hr','conc'])
              .sort_values('time_hr')
              .reset_index(drop=True))

        if len(df) < 2:
            valid = False
            break

        ct_data[idx] = df

    if valid:
        valid_entries.append((metab, ct_data))

conn.close()

if not valid_entries:
    raise ValueError("No metabolites have ≥2 time‐points in both species.")

# 4) Create subplots only for valid entries
n = len(valid_entries)
fig, axes = plt.subplots(
    nrows=n,
    ncols=2,
    figsize=(8, 4 * n),
    sharex="col"
)
# make sure axes is 2D
if n == 1:
    axes = axes.reshape(1, 2)

# 5) Plot each valid metabolite with species‐specific colors
for i, (metab, ct_data) in enumerate(valid_entries):
    for j, sp in enumerate([species1, species2]):
        ax = axes[i, j]
        df = ct_data[j]
        ax.plot(
            df['time_hr'],
            df['conc'],
            marker='o',
            linestyle='-',
            color=colors[sp]
        )
        if i == 0:
            ax.set_title(sp.capitalize())
        if j == 0:
            ax.set_ylabel(metab, rotation=0, labelpad=40, va='center')

# 6) Label x‐axis on bottom row
for j, sp in enumerate([species1, species2]):
    axes[-1, j].set_xlabel("Time (hr)")

plt.tight_layout()
plt.show()
