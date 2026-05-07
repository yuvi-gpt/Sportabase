import sqlite3
import pandas as pd

DB_PATH = "backend/data/sportabase.db"
CSV_PATH = "backend/data/ipl_matches.csv"

df = pd.read_csv(CSV_PATH)

conn = sqlite3.connect(DB_PATH)
df.to_sql("cricket_matches", conn, if_exists="append", index=False)
conn.close()

print(f"Imported {len(df)} rows into cricket_matches.")