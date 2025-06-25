import sqlite3
import pandas as pd

# Connect to the SQLite database
db_path = "cvt_db_20210607.sqlite"
conn = sqlite3.connect(db_path)

'''
These two IDs allow clear delineation between:
✅ What you measured (e.g. a metabolite in plasma) — linked via analyte_dtxsid / analyte_casrn
✅ What you administered (e.g. prodrug or parent compound) — linked via test_substance_dtxsid

the following code finds the shared administered drugs, not the measured metabolites

'''

# Query to get species, analyte, and ensure non-empty time or concentration
query = """
SELECT s.species, r.test_substance_dtxsid, ctv.time_hr, ctv.conc, r.analyte_dtxsid, r.analyte_casrn
FROM subjects AS s
JOIN series   AS r ON s.id = r.fk_subject_id
JOIN conc_time_values AS ctv ON r.id = ctv.fk_series_id
"""

df = pd.read_sql_query(query, conn)

# Filter out empty strings in time_hr and conc
df = df[df['time_hr'].astype(str).str.strip().ne('') &
        df['conc'].astype(str).str.strip().ne('')]

# Normalize species (group different cases together)
df['species_norm'] = df['species'].str.strip().str.lower()

# Build list of unique normalized species
species_list = sorted(df['species_norm'].unique())

# Build a dictionary of analytes per normalized species
analytes_by_species = {
    sp: set(df[df['species_norm'] == sp]['test_substance_dtxsid'])
    for sp in species_list
}

# Create the intersection matrix DataFrame
matrix = pd.DataFrame(index=species_list, columns=species_list, dtype=object)

for sp1 in species_list:
    for sp2 in species_list:
        intersection = analytes_by_species[sp1].intersection(analytes_by_species[sp2])
        matrix.at[sp1, sp2] = sorted(intersection)

# Display the resulting matrix
print(matrix)

# save the matrix

matrix.to_csv('parallel_administered_drugs_matrix.csv')
