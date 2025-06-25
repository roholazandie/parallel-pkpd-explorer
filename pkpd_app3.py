import sqlite3
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import ast
import math
import uuid
from streamlit.components.v1 import html

# ——— CONFIG ———
DB_PATH            = "cvt_db_20210607.sqlite"
ADMIN_MATRIX_CSV   = "parallel_administered_drugs_matrix.csv"
MET_MATRIX_CSV     = "parallel_metabolites_matrix.csv"

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

plt.style.use('dark_background')

# ——— SESSION KEYS ———
if 'shared_ready_admin' not in st.session_state:
    st.session_state['shared_ready_admin'] = False
if 'shared_ready_meta' not in st.session_state:
    st.session_state['shared_ready_meta'] = False

# ——— LOAD MATRICES ———
@st.cache_data
def load_matrix(path):
    df = pd.read_csv(path, index_col=0)
    return df.applymap(ast.literal_eval)

admin_matrix = load_matrix(ADMIN_MATRIX_CSV)
metab_matrix = load_matrix(MET_MATRIX_CSV)

# ——— SPECIES SELECTION ———
species_options = sorted(admin_matrix.index.str.lower().unique())
st.sidebar.header("Select Species")
species1 = st.sidebar.selectbox("Species 1", species_options,
                                index=species_options.index("mouse") if "mouse" in species_options else 0)
species2 = st.sidebar.selectbox("Species 2", species_options,
                                index=species_options.index("rat")   if "rat"   in species_options else 1)
if species1 == species2:
    st.sidebar.error("Pick two different species.")
    st.stop()

# ——— DB QUERY ———
@st.cache_data
def get_best_series_and_data(db_path, species, metab):
    conn = sqlite3.connect(db_path)
    q = """
      SELECT r.id AS series_id, COUNT(*) AS n_pts
        FROM series r
        JOIN subjects s ON r.fk_subject_id = s.id
        JOIN conc_time_values ctv ON r.id = ctv.fk_series_id
       WHERE LOWER(s.species)=? AND r.test_substance_dtxsid=?
       GROUP BY r.id
       ORDER BY n_pts DESC
       LIMIT 1
    """
    best = pd.read_sql_query(q, conn, params=(species, metab))
    if best.empty or best.at[0, "n_pts"] < 2:
        conn.close()
        return None
    sid = best.at[0, "series_id"]
    df = pd.read_sql_query(
        "SELECT time_hr, conc FROM conc_time_values WHERE fk_series_id=?",
        conn, params=(sid,)
    )
    conn.close()
    df["time_hr"] = pd.to_numeric(df["time_hr"], errors="coerce")
    df["conc"]    = pd.to_numeric(df["conc"],    errors="coerce")
    df = df.dropna(subset=["time_hr","conc"]).sort_values("time_hr").reset_index(drop=True)
    return df if len(df) >= 2 else None

# ——— PRE-COMPUTE “AVAILABLE” LISTS FOR STRUCTURE TAB ———
shared_admin_raw = admin_matrix.at[species1, species2] if species1 != species2 else []
available_admin = [
    chem for chem in shared_admin_raw
    if get_best_series_and_data(DB_PATH, species1, chem) is not None
   and get_best_series_and_data(DB_PATH, species2, chem) is not None
]

shared_meta_raw = metab_matrix.at[species1, species2] if species1 != species2 else []
available_meta = [
    chem for chem in shared_meta_raw
    if get_best_series_and_data(DB_PATH, species1, chem) is not None
   and get_best_series_and_data(DB_PATH, species2, chem) is not None
]

struct_options = sorted(set(available_admin + available_meta))

# ——— TABS ———
tab_admin, tab_meta, tab_struct = st.tabs([
    "Administered Drugs", "Metabolites", "3D Structure Viewer"
])

# Administered & Metabolites plotting logic
for tab, matrix, state_key, button_key, select_key, plot_key, label in [
    (tab_admin, admin_matrix, 'shared_ready_admin', 'show_admin', 'select_admin', 'plot_admin', 'Administered Drugs'),
    (tab_meta,  metab_matrix, 'shared_ready_meta',  'show_meta',  'select_meta',  'plot_meta',  'Metabolites')
]:
    with tab:
        shared_raw = matrix.at[species1, species2] if species1 != species2 else []
        shared = shared_raw or []
        if not shared:
            st.error(f"No shared {label.lower()} for **{species1}** & **{species2}**.")
            continue

        available = [
            item for item in shared
            if get_best_series_and_data(DB_PATH, species1, item) is not None
           and get_best_series_and_data(DB_PATH, species2, item) is not None
        ]
        if not available:
            st.warning(f"No {label.lower()} with ≥2 points for both species.")
            continue

        st.header(f"{len(available)} {label} Available for Plotting")
        if st.button(f"Show {label}", key=button_key):
            st.session_state[state_key] = True

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
                    ax.plot(df1["time_hr"], df1["conc"], marker="o", linestyle="-",
                            color=colors[species1], label=species1.capitalize())
                    ax.plot(df2["time_hr"], df2["conc"], marker="s", linestyle="--",
                            color=colors[species2], label=species2.capitalize())

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
                    ax.legend(
                        fontsize=6, facecolor='#333333', edgecolor='white', labelcolor='white'
                    )

                for ax in axes[n:]:
                    ax.set_visible(False)

                st.pyplot(fig)


# ——— 3D STRUCTURE VIEWER ———
with tab_struct:
    st.header("3D Structure Viewer")
    st.write("Select a chemical (DTXSID or CAS) to display its 3D structure:")
    if not struct_options:
        st.warning("No shared chemicals with ≥2 points to visualize.")
    else:
        chem = st.selectbox("Select a chemical", struct_options)

        view_style = st.radio(
            "Choose display style",
            ["Ball and Stick", "Sticks", "Wire-Frame", "Space-Filling"],
            horizontal=True
        )
        animate = st.checkbox("Animate")  # ← new!

        style_map = {
            "Ball and Stick": "{sphere:{scale:0.3},stick:{radius:0.2}}",
            "Sticks":          "{stick:{radius:0.2}}",
            "Wire-Frame":      "{line:{linewidth:1}}",
            "Space-Filling":   "{sphere:{scale:1.0}}"
        }
        style_js = style_map[view_style]
        spin_js   = "viewer.spin(true);" if animate else ""

        if chem:
            div_id = f"viewer_{uuid.uuid4().hex}"
            svc = f"xref/RN/{chem}" if "-" in chem else f"name/{chem}"
            sdf_url = (
                "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/"
                f"{svc}/SDF?record_type=3d"
            )

            component = f"""
            <script src="https://3Dmol.org/build/3Dmol-min.js"></script>
            <div id="{div_id}" style="width:100%; height:500px; background-color:#0E1117;"></div>
            <script>
            (function() {{
              const tgt = document.getElementById("{div_id}");
              const viewer = $3Dmol.createViewer(tgt, {{ backgroundColor: 'black' }});
              fetch("{sdf_url}")
                .then(res => {{
                  if (!res.ok) throw new Error('HTTP ' + res.status);
                  return res.text();
                }})
                .then(sdf => {{
                  viewer.addModel(sdf, 'sdf');
                  viewer.setStyle({{}}, {style_js});
                  viewer.zoomTo();
                  viewer.render();
                  {spin_js}  // ← spins if animate==True
                }})
                .catch(err => {{
                  tgt.innerHTML = '<p style="color:red;">Could not load structure:<br>'
                                 + err.message + '</p>';
                  console.error(err);
                }});
            }})();
            </script>
            """
            html(component, height=550)

