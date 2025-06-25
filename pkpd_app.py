import sqlite3
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import ast
import math

# ——— CONFIG ———
DB_PATH    = "cvt_db_20210607.sqlite"
MATRIX_CSV = "parallel_administered_drugs_matrix.csv"


st.set_page_config(page_title="Cross-Species PK/PD Explorer", layout="wide")

# ——— CUSTOM FONT & PAGE TITLE ———
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Ubuntu:wght@400;700&display=swap');

    .page-title {
        font-family: 'Ubuntu', sans-serif;
        font-size: 3rem;
        text-align: center;
        color: white;
        margin-bottom: 1.5rem;
    }
    </style>
    <div class="page-title">Cross-Species PK/PD Explorer</div>
    """, unsafe_allow_html=True)

# Use Matplotlib’s built-in dark style
plt.style.use('dark_background')


# Initialize session state
if 'shared_ready' not in st.session_state:
    st.session_state['shared_ready'] = False

# ——— LOAD ANALYTE MATRIX ———
@st.cache_data
def load_matrix(path):
    df = pd.read_csv(path, index_col=0)
    return df.applymap(ast.literal_eval)

matrix = load_matrix(MATRIX_CSV)
species_options = sorted(matrix.index.str.lower().unique())

# ——— SIDEBAR: SPECIES SELECTION ———
st.sidebar.header("Select Species")
species1 = st.sidebar.selectbox("Species 1", species_options, index=species_options.index("mouse") if "mouse" in species_options else 0)
species2 = st.sidebar.selectbox("Species 2", species_options, index=species_options.index("rat") if "rat" in species_options else 1)
if species1 == species2:
    st.sidebar.error("Pick two different species.")
    st.stop()

# ——— FIND SHARED METABOLITES ———
shared_raw = matrix.at[species1, species2] if species1 != species2 else []
shared = shared_raw if shared_raw else []
if not shared:
    st.error(f"No shared analytes for **{species1}** & **{species2}**.")
    st.stop()

# ——— DB QUERY FUNCTION ———
@st.cache_data
def get_best_series_and_data(db_path, species, metab):
    conn = sqlite3.connect(db_path)
    q_best = """
        SELECT r.id AS series_id, COUNT(*) AS n_pts
          FROM series AS r
          JOIN subjects AS s ON r.fk_subject_id = s.id
          JOIN conc_time_values AS ctv ON r.id = ctv.fk_series_id
         WHERE LOWER(s.species)        = ?
           AND r.test_substance_dtxsid = ?
         GROUP BY r.id
         ORDER BY n_pts DESC
         LIMIT 1
    """
    best = pd.read_sql_query(q_best, conn, params=(species, metab))
    if best.empty or best.at[0, "n_pts"] < 2:
        conn.close()
        return None
    series_id = best.at[0, "series_id"]
    ct_df = pd.read_sql_query(
        "SELECT time_hr, conc FROM conc_time_values WHERE fk_series_id = ?",
        conn,
        params=(series_id,),
    )
    conn.close()
    ct_df["time_hr"] = pd.to_numeric(ct_df["time_hr"], errors="coerce")
    ct_df["conc"]    = pd.to_numeric(ct_df["conc"],    errors="coerce")
    ct_df = (
        ct_df.dropna(subset=["time_hr", "conc"])
             .sort_values("time_hr")
             .reset_index(drop=True)
    )
    return ct_df if len(ct_df) >= 2 else None

# ——— PRE-FILTER AVAILABLE METABOLITES ———
available_metabs = []
for metab in shared:
    if get_best_series_and_data(DB_PATH, species1, metab) is not None \
       and get_best_series_and_data(DB_PATH, species2, metab) is not None:
        available_metabs.append(metab)

if not available_metabs:
    st.warning("No metabolites with ≥2 points for both species.")
    st.stop()

st.header(f"{len(available_metabs)} Metabolites Available for Plotting")

# ——— BUTTON TO SHOW METABOLITES ———
if st.sidebar.button("Show metabolites"):
    st.session_state['shared_ready'] = True

# ——— WHEN BUTTON PRESSED: SHOW MULTISELECT ———
if st.session_state['shared_ready']:
    selected = st.multiselect("Select metabolites to plot", available_metabs)
    if st.button("Plot selected metabolites") and selected:
        colors = {species1: "#1f77b4", species2: "#ff7f0e"}  # bright lines on dark

        # Determine subplot grid size
        n = len(selected)
        ncols = 2
        nrows = math.ceil(n / ncols)

        # Create one figure with subplots
        fig, axes = plt.subplots(
            nrows, ncols,
            figsize=(ncols * 5, nrows * 3),
            # sharex=True, sharey=True,
            constrained_layout=True
        )
        axes = axes.flatten()  # flatten in case of multiple rows/cols

        # Make the figure background black too
        fig.patch.set_facecolor('black')

        # Plot each metabolite in its own axis
        for ax, metab in zip(axes, selected):
            df1 = get_best_series_and_data(DB_PATH, species1, metab)
            df2 = get_best_series_and_data(DB_PATH, species2, metab)

            ax.plot(df1["time_hr"], df1["conc"],
                    marker="o", linestyle="-",
                    color=colors[species1],
                    label=species1.capitalize())
            ax.plot(df2["time_hr"], df2["conc"],
                    marker="s", linestyle="--",
                    color=colors[species2],
                    label=species2.capitalize())

            # Dark-theme styling
            ax.set_facecolor('#222222')
            ax.tick_params(colors='white', which='both')
            ax.xaxis.label.set_color('white')
            ax.yaxis.label.set_color('white')
            ax.title.set_color('white')
            for spine in ax.spines.values():
                spine.set_color('white')
            ax.grid(color='gray', linestyle=':', linewidth=0.5)

            ax.set_title(metab, fontsize=10)
            ax.set_xlabel("Time (hr)")
            ax.set_ylabel("Concentration")
            ax.legend(fontsize=6, facecolor='#333333', edgecolor='white', labelcolor='white')

        # Turn off any unused subplots
        for ax in axes[n:]:
            ax.set_visible(False)

        # Render the combined figure
        st.pyplot(fig)
