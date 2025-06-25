import sqlite3
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import ast
import math

# ——— CONFIG ———
DB_PATH = "cvt_db_20210607.sqlite"
ADMIN_MATRIX_CSV = "parallel_administered_drugs_matrix.csv"
MET_MATRIX_CSV = "parallel_metabolites_matrix.csv"

# ——— STREAMLIT PAGE CONFIG ———
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

# ——— SESSION STATE INITIALIZATION ———
if 'shared_ready_admin' not in st.session_state:
    st.session_state['shared_ready_admin'] = False
if 'shared_ready_meta' not in st.session_state:
    st.session_state['shared_ready_meta'] = False

# ——— LOAD MATRIX FUNCTION ———
@st.cache_data
def load_matrix(path):
    df = pd.read_csv(path, index_col=0)
    return df.applymap(ast.literal_eval)

# Load both matrices
admin_matrix = load_matrix(ADMIN_MATRIX_CSV)
metab_matrix = load_matrix(MET_MATRIX_CSV)

# Species options (assumes both matrices share same species index)
species_options = sorted(admin_matrix.index.str.lower().unique())

# ——— SIDEBAR: SPECIES SELECTION ———
st.sidebar.header("Select Species")
species1 = st.sidebar.selectbox(
    "Species 1",
    species_options,
    index=species_options.index("mouse") if "mouse" in species_options else 0
)
species2 = st.sidebar.selectbox(
    "Species 2",
    species_options,
    index=species_options.index("rat") if "rat" in species_options else 1
)
if species1 == species2:
    st.sidebar.error("Pick two different species.")
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

# ——— TABS FOR ADMINISTERED DRUGS & METABOLITES ———
tab_admin, tab_meta = st.tabs(["Administered Drugs", "Metabolites"])

for tab, matrix, state_key, button_key, select_key, plot_key, label in [
    (tab_admin, admin_matrix, 'shared_ready_admin', 'show_admin', 'select_admin', 'plot_admin', 'Administered Drugs'),
    (tab_meta, metab_matrix, 'shared_ready_meta', 'show_meta', 'select_meta', 'plot_meta', 'Metabolites')
]:
    with tab:
        # Find shared items between species
        shared_raw = matrix.at[species1, species2] if species1 != species2 else []
        shared = shared_raw if shared_raw else []
        if not shared:
            st.error(f"No shared {label.lower()} for **{species1}** & **{species2}**.")
            continue

        # Pre-filter items with ≥2 points in both species
        available = []
        for item in shared:
            if get_best_series_and_data(DB_PATH, species1, item) is not None \
               and get_best_series_and_data(DB_PATH, species2, item) is not None:
                available.append(item)

        if not available:
            st.warning(f"No {label.lower()} with ≥2 points for both species.")
            continue

        st.header(f"{len(available)} {label} Available for Plotting")

        # Button to show items
        if st.button(f"Show {label}", key=button_key):
            st.session_state[state_key] = True

        # When button pressed: show multiselect & plot
        if st.session_state[state_key]:
            selected = st.multiselect(
                f"Select {label} to plot", available, key=select_key
            )
            if st.button(f"Plot selected {label}", key=plot_key) and selected:
                colors = {species1: "#1f77b4", species2: "#ff7f0e"}
                n = len(selected)
                ncols = 2
                nrows = math.ceil(n / ncols)
                fig, axes = plt.subplots(
                    nrows, ncols,
                    figsize=(ncols * 5, nrows * 3),
                    constrained_layout=True
                )
                axes = axes.flatten()
                fig.patch.set_facecolor('black')

                for ax, item in zip(axes, selected):
                    df1 = get_best_series_and_data(DB_PATH, species1, item)
                    df2 = get_best_series_and_data(DB_PATH, species2, item)

                    ax.plot(df1["time_hr"], df1["conc"],
                            marker="o", linestyle="-",
                            color=colors[species1],
                            label=species1.capitalize())
                    ax.plot(df2["time_hr"], df2["conc"],
                            marker="s", linestyle="--",
                            color=colors[species2],
                            label=species2.capitalize())

                    ax.set_facecolor('#222222')
                    ax.tick_params(colors='white', which='both')
                    ax.xaxis.label.set_color('white')
                    ax.yaxis.label.set_color('white')
                    ax.title.set_color('white')
                    for spine in ax.spines.values():
                        spine.set_color('white')
                    ax.grid(color='gray', linestyle=':', linewidth=0.5)

                    ax.set_title(item, fontsize=10)
                    ax.set_xlabel("Time (hr)")
                    ax.set_ylabel("Concentration")
                    ax.legend(fontsize=6, facecolor='#333333', edgecolor='white', labelcolor='white')

                for ax in axes[n:]:
                    ax.set_visible(False)

                st.pyplot(fig)
