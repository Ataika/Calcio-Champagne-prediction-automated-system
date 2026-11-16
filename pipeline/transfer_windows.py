"""PROCESS step: summer window or winter window? Every dated incoming transfer
with a recorded positive fee is assigned to a window by month (July–September
= summer, January–February = winter, anything else = other), then summed per
league-season. Recorded fees only: the ~95% of rows with a zero fee — loans,
free moves and undisclosed amounts — are excluded, so these are shares of the
*disclosed* market, not of all football spending.
"""
import pandas as pd
from psycopg2.extras import execute_values

REPORT = "transfer windows"


def _window(month):
    if month in (7, 8, 9):
        return "summer"
    if month in (1, 2):
        return "winter"
    return "other"


def compute(conn):
    transfers = pd.read_sql("""
        SELECT t.season_name, t.transfer_date, t.transfer_fee,
               perf.competition_id
        FROM transfer_history t
        JOIN (SELECT DISTINCT team_id, season_name, competition_id FROM player_performances) perf
          ON perf.team_id = t.to_team_id AND perf.season_name = t.season_name
        WHERE t.transfer_fee > 0 AND t.transfer_date IS NOT NULL
    """, conn)
    if transfers.empty:
        return pd.DataFrame()

    transfers["transfer_window"] = pd.to_datetime(transfers["transfer_date"]).dt.month.map(_window)
    grouped = transfers.groupby(["competition_id", "season_name", "transfer_window"]).agg(
        transfers=("transfer_fee", "size"),
        total_fee=("transfer_fee", "sum"),
        mean_fee=("transfer_fee", "mean"),
    ).reset_index()
    season_total = grouped.groupby(["competition_id", "season_name"])["total_fee"].transform("sum")
    grouped["fee_share"] = (grouped["total_fee"] / season_total).round(3)
    grouped["total_fee"] = grouped["total_fee"].round(0)
    grouped["mean_fee"] = grouped["mean_fee"].round(0)
    return grouped


COLUMNS = ["competition_id", "season_name", "transfer_window", "transfers", "total_fee", "mean_fee", "fee_share"]


def write(conn, frame):
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS transfer_window_split;")
        cur.execute("""
            CREATE TABLE transfer_window_split (
                competition_id TEXT,
                season_name TEXT,
                transfer_window TEXT,  -- 'window' is a reserved word in SQL
                transfers INTEGER,
                total_fee NUMERIC,
                mean_fee NUMERIC,
                fee_share NUMERIC
            );
        """)
        if not frame.empty:
            execute_values(cur, f"INSERT INTO transfer_window_split ({', '.join(COLUMNS)}) VALUES %s",
                           list(frame[COLUMNS].itertuples(index=False)))
    conn.commit()
