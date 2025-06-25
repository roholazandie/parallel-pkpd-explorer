import streamlit as st
from streamlit.components.v1 import html
import uuid

st.title("3Dmol.js Structure Viewer in Streamlit (Dark Mode)")

cas = st.text_input("Enter a CAS Number", placeholder="e.g. 50-00-0")
if cas:
    div_id = f"viewer_{uuid.uuid4().hex}"
    sdf_url = (
        "https://pubchem.ncbi.nlm.nih.gov/rest/pug/"
        f"compound/xref/RN/{cas}/SDF?record_type=3d"
    )

    component = f"""
    <script src="https://3Dmol.org/build/3Dmol-min.js"></script>
    <!-- give the container a matching dark background -->
    <div id="{div_id}" style="width:100%; height:500px; background-color:#0E1117;"></div>
    <script>
    (function() {{
      const target = document.getElementById("{div_id}");
      // set viewer background to black (or any dark hex)
      const viewer = $3Dmol.createViewer(target, {{ backgroundColor: 'black' }});
      fetch("{sdf_url}")
        .then(res => {{
          if (!res.ok) throw new Error('HTTP ' + res.status);
          return res.text();
        }})
        .then(sdf => {{
          viewer.addModel(sdf, 'sdf');
          viewer.setStyle({{}}, {{ stick: {{}} }});
          viewer.zoomTo();
          viewer.render();
        }})
        .catch(err => {{
          target.innerHTML = '<p style="color:red;">Could not load structure:<br>' 
                             + err.message + '</p>';
          console.error(err);
        }});
    }})();
    </script>
    """

    html(component, height=550)
