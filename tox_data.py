import pandas as pd
import sqlite3

# Define file and database paths
csv_file = "chemical_data.csv"
db_file = "chemical_data.sqlite"
table_name = "chemical_inventory"

# Load CSV with proper handling of quoted fields and commas
df = pd.read_csv(csv_file)

# Create SQLite connection and load the dataframe
conn = sqlite3.connect(db_file)
df.to_sql(table_name, conn, if_exists="replace", index=False)

# Optional: create an index on common query fields for performance
with conn:
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_dtxsid ON {table_name}(DTXSID);")
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_cas ON {table_name}([Curated CAS]);")
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_function_use ON {table_name}([Harmonized Functional Use]);")

print(f"Data loaded into '{db_file}' in table '{table_name}'")

# Close connection
conn.close()
