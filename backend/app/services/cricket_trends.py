from pathlib import Path
import sqlite3
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[2]   # backend/
DB_PATH = BASE_DIR / "data" / "sportabase.db"


def load_ipl_matches(db_path: str = DB_PATH) -> pd.DataFrame:
    conn = sqlite3.connect(db_path)
    query = """
        SELECT *
        FROM cricket_matches
        WHERE competition = 'IPL' AND match_completed = 1
        ORDER BY match_date ASC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


def add_cricket_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["match_date"] = pd.to_datetime(df["match_date"])
    df = df.sort_values("match_date").reset_index(drop=True)

    df["toss_winner_bowled_first"] = (
        (df["toss_winner"] == df["second_innings_team"]) &
        (df["toss_decision"] == "bowl")
    )

    df["batting_first_won"] = df["winner"] == df["first_innings_team"]
    df["chasing_team_won"] = df["winner"] == df["second_innings_team"]
    df["toss_winner_won"] = df["winner"] == df["toss_winner"]

    df["first_innings_score_band"] = pd.cut(
        df["first_innings_runs"],
        bins=[0, 159, 179, 199, 999],
        labels=["under_160", "160_179", "180_199", "200_plus"]
    )

    return df


def add_rolling_metrics(df: pd.DataFrame, window: int = 10) -> pd.DataFrame:
    df = df.copy()

    df["rolling_bowl_first_choice_rate"] = (
        df["toss_winner_bowled_first"].rolling(window=window, min_periods=3).mean()
    )

    df["rolling_chase_win_rate"] = (
        df["chasing_team_won"].rolling(window=window, min_periods=3).mean()
    )

    df["rolling_bat_first_win_rate"] = (
        df["batting_first_won"].rolling(window=window, min_periods=3).mean()
    )

    return df

def build_history(df: pd.DataFrame) -> list[dict]:
    history = []

    for _, row in df.iterrows():
        history.append({
            "match_id": row["match_id"],
            "match_date": row["match_date"].strftime("%Y-%m-%d"),
            "rolling_bowl_first_choice_rate": None if pd.isna(row["rolling_bowl_first_choice_rate"]) else round(float(row["rolling_bowl_first_choice_rate"]), 3),
            "rolling_chase_win_rate": None if pd.isna(row["rolling_chase_win_rate"]) else round(float(row["rolling_chase_win_rate"]), 3),
            "rolling_bat_first_win_rate": None if pd.isna(row["rolling_bat_first_win_rate"]) else round(float(row["rolling_bat_first_win_rate"]), 3),
        })

    return history


def detect_strategy_lag(latest_row: pd.Series) -> dict | None:
    bowl_rate = latest_row["rolling_bowl_first_choice_rate"]
    chase_rate = latest_row["rolling_chase_win_rate"]
    bat_first_rate = latest_row["rolling_bat_first_win_rate"]

    if pd.isna(bowl_rate) or pd.isna(chase_rate) or pd.isna(bat_first_rate):
        return None

    if bowl_rate >= 0.60 and chase_rate <= 0.45 and bat_first_rate >= 0.55:
        return {
            "trend_key": "cricket_strategy_lag",
            "title": "Chasing bias may be lagging current conditions",
            "confidence": "medium",
            "insight": (
                "Teams are still frequently choosing to bowl first, "
                "but recent results suggest batting first has become more effective."
            ),
            "evidence": {
                "rolling_bowl_first_choice_rate": round(float(bowl_rate), 3),
                "rolling_chase_win_rate": round(float(chase_rate), 3),
                "rolling_bat_first_win_rate": round(float(bat_first_rate), 3),
            }
        }

    return None


def get_ipl_chasing_bias_insight(history_limit: int = 3, db_path: str = DB_PATH) -> dict:
    df = load_ipl_matches(db_path)

    if df.empty:
        return {"error": "No IPL match data available."}

    df = add_cricket_features(df)
    df = add_rolling_metrics(df, window=10)
    history = build_history(df)[-history_limit:]

    latest = df.iloc[-1]
    trend = detect_strategy_lag(latest)
    summary = {
        "matches_analyzed": int(len(df)),
        "history_points_returned": int(len(history)),
        "current_signal_active": trend is not None
    }

    chart_series = {
        "labels": [point["match_date"] for point in history],
        "bowl_first_choice_rate": [point["rolling_bowl_first_choice_rate"] for point in history],
        "chase_win_rate": [point["rolling_chase_win_rate"] for point in history],
        "bat_first_win_rate": [point["rolling_bat_first_win_rate"] for point in history],
    }

    return {
        "sport": "cricket",
        "competition": "IPL",
        "insight_type": "trend_detection",
        "summary": summary,
        "latest_metrics": {
            "rolling_bowl_first_choice_rate": None if pd.isna(latest["rolling_bowl_first_choice_rate"]) else round(float(latest["rolling_bowl_first_choice_rate"]), 3),
            "rolling_chase_win_rate": None if pd.isna(latest["rolling_chase_win_rate"]) else round(float(latest["rolling_chase_win_rate"]), 3),
            "rolling_bat_first_win_rate": None if pd.isna(latest["rolling_bat_first_win_rate"]) else round(float(latest["rolling_bat_first_win_rate"]), 3),
        },
        "chart_series": chart_series,
        "trend": trend,
        "generated_at_match": {
            "match_id": latest["match_id"],
            "match_date": latest["match_date"].strftime("%Y-%m-%d"),
            "team1": latest["team1"],
            "team2": latest["team2"],
            "winner": latest["winner"],
            "venue": latest["venue"],
        }
    }


if __name__ == "__main__":
    result = get_ipl_chasing_bias_insight()
    print(result)