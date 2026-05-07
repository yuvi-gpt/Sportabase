import sqlite3

DB_PATH = "backend/data/sportabase.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS cricket_matches (
    match_id TEXT PRIMARY KEY,
    season INTEGER NOT NULL,
    competition TEXT NOT NULL,
    match_date TEXT NOT NULL,
    venue TEXT NOT NULL,

    team1 TEXT NOT NULL,
    team2 TEXT NOT NULL,

    toss_winner TEXT NOT NULL,
    toss_decision TEXT NOT NULL CHECK (toss_decision IN ('bat', 'bowl')),

    first_innings_team TEXT NOT NULL,
    second_innings_team TEXT NOT NULL,

    first_innings_runs INTEGER NOT NULL,
    first_innings_wickets INTEGER NOT NULL,
    first_innings_overs REAL NOT NULL,

    second_innings_runs INTEGER NOT NULL,
    second_innings_wickets INTEGER NOT NULL,
    second_innings_overs REAL NOT NULL,

    winner TEXT NOT NULL,
    margin_type TEXT NOT NULL,
    margin_value INTEGER NOT NULL,

    match_completed INTEGER NOT NULL DEFAULT 1
)
""")

conn.commit()
conn.close()

print("cricket_matches table ready.")