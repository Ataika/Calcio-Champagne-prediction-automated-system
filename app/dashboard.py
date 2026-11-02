"""SHOW step: a Streamlit dashboard over champagne_results / champagne_model /
league_standings.

Five tabs: a season ranking table, one team's index trend with its predicted next
value, the spend-vs-output scatter that the trend line is fitted on, a Standings tab
checking Champagne Index against real league position (needs the optional
football-data.co.uk enrichment — see loader/load_data.py), and a Performance tab
that reads the benchmark results (run `docker compose run measure` to populate it —
see measure/benchmark.py).
"""
import json
import os
import pathlib

import joblib
import pandas as pd
import plotly.graph_objects as go
import psycopg2
import streamlit as st

RESULTS_PATH = pathlib.Path("/results/results.json")
LAB_MODEL_PATH = pathlib.Path("/models/champagne_rf_model.joblib")

st.set_page_config(page_title="Calcio Champagne", page_icon="⚽", layout="wide")


@st.cache_resource
def get_connection():
    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "db"),
        port=os.environ.get("POSTGRES_PORT", "5432"),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )


@st.cache_data(ttl=300)
def load_results() -> pd.DataFrame:
    return pd.read_sql("SELECT * FROM champagne_results", get_connection())


@st.cache_data(ttl=300)
def load_model() -> pd.DataFrame:
    return pd.read_sql(
        "SELECT * FROM champagne_model ORDER BY computed_at DESC LIMIT 1", get_connection()
    )


@st.cache_data(ttl=300)
def load_standings() -> pd.DataFrame:
    try:
        return pd.read_sql("SELECT * FROM league_standings", get_connection())
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=300)
def load_standings_model() -> pd.DataFrame:
    try:
        return pd.read_sql(
            "SELECT * FROM champagne_vs_position_model ORDER BY computed_at DESC LIMIT 1",
            get_connection(),
        )
    except Exception:
        return pd.DataFrame()


@st.cache_resource
def load_lab_model():
    if not LAB_MODEL_PATH.exists():
        return None
    return joblib.load(LAB_MODEL_PATH)


df = load_results()
model_df = load_model()
standings_df = load_standings()
standings_model_df = load_standings_model()

st.title("⚽ Calcio Champagne")
st.caption(
    "Does a team's spending on attacking-position transfers predict a rise in its "
    "Champagne Index — attacking output per match — the following season?"
)

with st.expander("ℹ️ Methodology"):
    st.markdown(
        """
**Why goals + assists per match?** "Attacking output per match" (goals plus
assists, divided by matches played) is a standard, recognized way to measure a
team's attacking production in football analytics — it's not a metric invented
for this project. It rewards both scoring and creating goals, and dividing by
matches makes it comparable across teams that played different numbers of
games in a season.

**Why a simple linear trend and not a trained ML model?** The underlying data
is team-season level — one row per team per competition per season, not
individual match events. With that little granularity (hundreds, not millions,
of independent observations once you group by team-season), a trained model
with many parameters would be more likely to fit noise than to find a real
signal. A simple linear regression (`scipy.stats.linregress`) reports its
correlation and p-value openly, so the strength (or weakness) of any
relationship is visible rather than hidden behind a model's internal weights.

**What does r = -0.663 actually mean?** Across the top-5 European leagues,
a team's Champagne Index and its final league position move together fairly
strongly: teams with a higher attacking-output score tend to finish higher
(closer to 1st) in the table, and that pattern is very unlikely to be
coincidence (p < 0.0001 across 484 team-seasons) — in plain terms, "goals +
assists per match" really does track with how good a team's season was.
        """
    )

tab_ranking, tab_team, tab_model, tab_standings, tab_lab, tab_perf = st.tabs(
    ["Ranking", "Team trend", "Spend vs. output", "Standings", "🧪 Lab", "Performance"]
)

with tab_ranking:
    competitions = sorted(df["competition_name"].dropna().unique())
    seasons_sorted = (
        df.dropna(subset=["season_key"])
        .drop_duplicates("season_name")
        .sort_values("season_key", ascending=False)["season_name"]
        .tolist()
    )

    col1, col2 = st.columns(2)
    competition = col1.selectbox("Competition", ["All"] + competitions)
    season = col2.selectbox("Season", ["Latest per team"] + seasons_sorted)

    view = df.copy()
    if competition != "All":
        view = view[view["competition_name"] == competition]
    if season == "Latest per team":
        view = view[view["is_latest_season"]]
    else:
        view = view[view["season_name"] == season]

    view = view.sort_values("champagne_index", ascending=False)
    st.dataframe(
        view[
            [
                "team_name", "competition_name", "season_name", "matches",
                "total_goals", "total_assists", "champagne_index",
                "total_spend", "predicted_next_index",
            ]
        ].head(50),
        use_container_width=True,
        hide_index=True,
    )

with tab_team:
    team_name = st.selectbox("Team", sorted(df["team_name"].dropna().unique()))
    team_df = df[df["team_name"] == team_name].sort_values("season_key")

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=team_df["season_name"], y=team_df["champagne_index"],
            name="Champagne index", mode="lines+markers",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=team_df["season_name"], y=team_df["predicted_next_index"],
            name="Predicted next season", mode="markers",
            marker=dict(symbol="diamond", size=10),
        )
    )
    fig.update_layout(yaxis_title="Champagne index (goals+assists per match)")
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        team_df[
            [
                "season_name", "competition_name", "matches", "champagne_index",
                "total_spend", "attacking_spend", "delta_index", "predicted_next_index",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )

with tab_model:
    if not model_df.empty:
        m = model_df.iloc[0]
        c1, c2, c3 = st.columns(3)
        c1.metric("Correlation (r)", f"{m['r_value']:.3f}")
        c2.metric("p-value", f"{m['p_value']:.4f}")
        c3.metric("Team-seasons fitted", int(m["n_observations"]))

        sample = df.dropna(subset=["delta_index"])
        fig2 = go.Figure()
        fig2.add_trace(
            go.Scatter(
                x=sample["total_spend"], y=sample["delta_index"], mode="markers",
                name="Team-season", text=sample["team_name"] + " " + sample["season_name"],
                hovertemplate="%{text}<br>spend=%{x}<br>Δindex=%{y}<extra></extra>",
                opacity=0.5,
            )
        )
        if sample["total_spend"].max() > 0:
            x_range = [0, sample["total_spend"].max()]
            y_range = [float(m["intercept"]) + float(m["slope"]) * x for x in x_range]
            fig2.add_trace(
                go.Scatter(x=x_range, y=y_range, mode="lines", name="Fitted trend")
            )
        fig2.update_layout(
            xaxis_title="Incoming transfer spend that season",
            yaxis_title="Δ Champagne index next season",
        )
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No model stats yet — run the pipeline first.")

with tab_standings:
    if standings_df.empty:
        st.info(
            "No match data loaded. Download the football-data.co.uk CSVs into "
            "data/matches/{E0,SP1,I1,D1,F1}/{season}.csv and re-run "
            "`docker compose up` — see README. This tab checks whether a high "
            "Champagne Index actually translates into a higher league position."
        )
    else:
        leagues = sorted(standings_df["league_code"].dropna().unique())
        seasons = sorted(standings_df["season_name"].dropna().unique())
        col1, col2 = st.columns(2)
        league = col1.selectbox("League", leagues)
        season_pick = col2.selectbox("Season", seasons, index=len(seasons) - 1)

        table_view = standings_df[
            (standings_df["league_code"] == league) & (standings_df["season_name"] == season_pick)
        ].sort_values("position")
        st.dataframe(
            table_view[
                [
                    "position", "team_name", "played", "wins", "draws", "losses",
                    "goals_for", "goals_against", "goal_diff", "points", "champagne_index",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

        if not standings_model_df.empty:
            m = standings_model_df.iloc[0]
            c1, c2, c3 = st.columns(3)
            c1.metric("Correlation (r)", f"{m['r_value']:.3f}")
            c2.metric("p-value", f"{m['p_value']:.4f}")
            c3.metric("Team-seasons", int(m["n_observations"]))
            st.caption(
                "Negative r means a higher Champagne Index goes with a better "
                "(lower-numbered) league position — i.e. attacking output does "
                "track with where a team finishes."
            )

        sample = standings_df.dropna(subset=["champagne_index", "position"])
        fig3 = go.Figure()
        fig3.add_trace(
            go.Scatter(
                x=sample["champagne_index"], y=sample["position"], mode="markers",
                text=sample["team_name"] + " " + sample["season_name"] + " (" + sample["league_code"] + ")",
                hovertemplate="%{text}<br>index=%{x}<br>position=%{y}<extra></extra>",
                opacity=0.5,
            )
        )
        fig3.update_layout(
            xaxis_title="Champagne index",
            yaxis_title="League position (1 = champion)",
            yaxis=dict(autorange="reversed"),
        )
        st.plotly_chart(fig3, use_container_width=True)

with tab_lab:
    lab = load_lab_model()
    if lab is None:
        st.info(
            "No trained model found yet. It's written by the pipeline automatically "
            "on `docker compose up` — reload this tab once that's finished."
        )
    else:
        st.caption(
            "Play with a hypothetical team-season and see what the model (the same "
            "RandomForest from the 'Upgrade the prediction model' work, R²≈0.15 on "
            "held-out data — a real but modest signal) predicts for next season. "
            "Not a real forecast, an educational toy: drag the sliders and watch "
            "the prediction move."
        )

        prefill_options = ["— blank —"] + sorted(df["team_name"].dropna().unique())
        prefill_team = st.selectbox("Start from a real team's latest season (optional)", prefill_options)

        ranges = lab["feature_ranges"]
        if prefill_team != "— blank —":
            row = df[(df["team_name"] == prefill_team) & (df["is_latest_season"])]
            row = row.iloc[0] if not row.empty else None
        else:
            row = None

        def default_for(col):
            if row is not None and pd.notna(row.get(col)):
                return float(row[col])
            return ranges[col]["median"]

        c1, c2 = st.columns(2)
        with c1:
            champagne_index = st.slider(
                "Current Champagne index", 0.0, max(3.0, ranges["champagne_index"]["max"]),
                value=min(default_for("champagne_index"), max(3.0, ranges["champagne_index"]["max"])), step=0.05,
            )
            total_spend = st.slider(
                "Total transfer spend (€)", 0, int(max(2e8, ranges["total_spend"]["max"])),
                value=int(min(default_for("total_spend"), max(2e8, ranges["total_spend"]["max"]))), step=1_000_000,
            )
            attacking_spend = st.slider(
                "...of which on attacking players (€)", 0, int(total_spend) if total_spend > 0 else 1,
                value=min(int(default_for("attacking_spend")), int(total_spend) if total_spend > 0 else 1),
                step=500_000,
            )
        with c2:
            squad_avg_age = st.slider(
                "Squad average age",
                float(min(16.0, ranges["squad_avg_age"]["min"])),
                float(max(40.0, ranges["squad_avg_age"]["max"])),
                value=float(default_for("squad_avg_age")), step=0.5,
            )
            market_value_change = st.slider(
                "Squad market-value change vs. last season (€)",
                int(min(-5e7, ranges["market_value_change"]["min"])),
                int(max(5e7, ranges["market_value_change"]["max"])),
                value=int(default_for("market_value_change")), step=500_000,
            )

        X = pd.DataFrame([{
            "champagne_index": champagne_index, "total_spend": total_spend,
            "attacking_spend": attacking_spend, "squad_avg_age": squad_avg_age,
            "market_value_change": market_value_change,
        }])[lab["feature_cols"]]
        predicted_delta = float(lab["model"].predict(X)[0])
        predicted_next = champagne_index + predicted_delta

        m1, m2, m3 = st.columns(3)
        m1.metric("Predicted Δ next season", f"{predicted_delta:+.2f}")
        m2.metric("Predicted next-season index", f"{predicted_next:.2f}")

        if not standings_model_df.empty:
            sm = standings_model_df.iloc[0]
            if pd.notna(sm.get("slope")) and pd.notna(sm.get("intercept")):
                approx_position = float(sm["slope"]) * predicted_next + float(sm["intercept"])
                approx_position = max(1, round(approx_position))
                m3.metric("Very roughly, league position", f"~{approx_position}")
                st.caption(
                    f"Position estimate inverts the Champagne Index ↔ league position "
                    f"trend (r={sm['r_value']:.3f}) — real position depends on dozens "
                    "of things this toy doesn't model (fixtures, injuries, luck...). "
                    "Treat it as a vibe, not a prediction."
                )
            else:
                st.caption("Load the football-data.co.uk match enrichment to unlock a position estimate.")

with tab_perf:
    if RESULTS_PATH.exists():
        data = json.loads(RESULTS_PATH.read_text())
        c1, c2, c3 = st.columns(3)
        c1.metric("Load time", f"{data.get('load_seconds', '?')} s")
        c2.metric("DB size on disk", f"{data.get('db_size_mb', '?')} MB")
        c3.metric("Peak memory (db)", f"{data.get('peak_memory_mb', {}).get('db', '?')} MB")

        st.subheader("Query time: with vs. without index")
        st.table(
            pd.DataFrame(
                {
                    "without index (s)": [data.get("query_without_index_seconds")],
                    "with index (s)": [data.get("query_with_index_seconds")],
                }
            )
        )

        st.subheader("Growth test (25% / 50% / 100% of player_performances)")
        growth = data.get("growth_test", [])
        if growth:
            st.table(pd.DataFrame(growth))

        st.caption(f"Benchmark machine: {data.get('machine', 'n/a')}")
    else:
        st.info(
            "No benchmark results yet. Run `docker compose run measure` and reload this tab."
        )
