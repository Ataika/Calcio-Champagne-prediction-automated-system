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

st.set_page_config(page_title="Calcio Champagne", layout="wide")

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&display=swap');

html, body, [class*="css"] { font-family: 'Inter', -apple-system, sans-serif; }
h1, h2, h3, .stTabs [data-baseweb="tab"] p {
    font-family: 'Space Grotesk', 'Inter', sans-serif !important;
    letter-spacing: 0.01em;
}
h1 { font-weight: 700 !important; font-size: 2.6rem !important; }
h2 { font-weight: 600 !important; }

@keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
.main .block-container { animation: fadeIn 0.4s ease-out; }

.lede {
    font-size: 1.05rem;
    line-height: 1.6;
    color: rgba(250,250,250,0.85);
    max-width: 68ch;
    margin: 0.4rem 0 1.2rem 0;
}

div[data-testid="stMetric"] {
    background: linear-gradient(135deg, rgba(212,175,55,0.12), rgba(212,175,55,0.02));
    border: 1px solid rgba(212,175,55,0.35);
    border-radius: 12px;
    padding: 14px 16px;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}
div[data-testid="stMetric"]:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 18px rgba(212,175,55,0.18);
}
div[data-testid="stMetricLabel"] { font-size: 0.85rem !important; opacity: 0.75; }
div[data-testid="stMetricValue"] { font-family: 'Space Grotesk', sans-serif !important; }

.stTabs [data-baseweb="tab"] p { font-size: 1rem !important; font-weight: 600 !important; }
button[data-baseweb="tab"] {
    transition: color 0.15s ease, transform 0.15s ease;
}
button[data-baseweb="tab"]:hover {
    color: #D4AF37 !important;
    transform: translateY(-1px);
}

div[data-testid="stExpander"] {
    border-radius: 10px;
    border: 1px solid rgba(212,175,55,0.25) !important;
}

.cluster-card {
    border: 1px solid rgba(212,175,55,0.25);
    border-radius: 10px;
    padding: 12px 16px;
    margin-bottom: 10px;
}
.cluster-card b { color: #D4AF37; }
</style>
""",
    unsafe_allow_html=True,
)


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


@st.cache_data(ttl=300)
def load_club_clusters() -> pd.DataFrame:
    try:
        return pd.read_sql("SELECT * FROM club_style_clusters", get_connection())
    except Exception:
        return pd.DataFrame()


TOP5_COMPETITION_IDS = {"GB1", "ES1", "IT1", "L1", "FR1"}


@st.cache_data(ttl=300)
def lab_team_options(_df: pd.DataFrame) -> list[str]:
    """Top-5-league, latest-season, 10+ matches only — the full team list is
    12,600+ names across every division and cup since 1960, which makes the
    dropdown slow to render and mostly irrelevant to a 'realistic starting
    point' picker."""
    pool = _df[
        _df["competition_id"].isin(TOP5_COMPETITION_IDS)
        & _df["is_latest_season"]
        & (_df["matches"].fillna(0) >= 10)
    ]
    return sorted(pool["team_name"].dropna().unique())


df = load_results()
model_df = load_model()
standings_df = load_standings()
standings_model_df = load_standings_model()
clusters_df = load_club_clusters()

st.title("Calcio Champagne")
st.markdown(
    """
<div class="lede">
The <b>Champagne Index</b> is goals plus assists, divided by matches played, for a
team in one competition in one season. It is not a metric invented for this
project — "attacking output per match" is a standard way football analytics
measures how much a team creates, and dividing by matches makes it
comparable across teams that played different numbers of games. This
dashboard asks one question: does a team's transfer spending on attacking
players predict a rise in that number the following season? The short
answer, across the full dataset, is no — see "Spend vs. output" below.
What the index <i>does</i> predict is real results: across the top-5
European leagues it correlates at r&nbsp;=&nbsp;&minus;0.663 with final
league position (484 team-seasons, p&nbsp;&lt;&nbsp;0.0001) — a higher
index tracks with finishing higher in the table.
</div>
""",
    unsafe_allow_html=True,
)

with st.expander("Methodology — why a linear trend, not a trained model"):
    st.markdown(
        """
The underlying data is team-season level — one row per team per competition
per season, not individual match events. With that little granularity
(hundreds, not millions, of independent observations once grouped by
team-season), a trained model with many parameters would be more likely to
fit noise than to find a real signal. A simple linear regression
(`scipy.stats.linregress`) reports its correlation and p-value openly, so
the strength — or weakness — of any relationship is visible rather than
hidden behind a model's internal weights. The richer RandomForest model
used in the Lab tab is a deliberate exception: see its own note there for
why that tradeoff is different.
        """
    )

tab_ranking, tab_team, tab_model, tab_standings, tab_lab, tab_styles, tab_perf = st.tabs(
    ["Ranking", "Team trend", "Spend vs. output", "Standings", "Lab", "Club styles", "Performance"]
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
    max_idx = view["champagne_index"].max()
    max_idx = float(max_idx) if pd.notna(max_idx) and max_idx > 0 else 1.0
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
        column_config={
            "champagne_index": st.column_config.ProgressColumn(
                "Champagne index", min_value=0, max_value=max_idx, format="%.2f",
            ),
            "total_spend": st.column_config.NumberColumn("Total spend", format="€%d"),
        },
    )

    with st.expander("Season-by-season race"):
        if competition == "All":
            st.caption("Pick a specific competition above to animate its teams across seasons.")
        else:
            race_pool = df[df["competition_name"] == competition]
            top_teams = (
                race_pool.groupby("team_name")["champagne_index"].max()
                .sort_values(ascending=False).head(15).index.tolist()
            )
            picked = st.multiselect("Teams to race", top_teams, default=top_teams[:6])
            race_df = race_pool[race_pool["team_name"].isin(picked)].dropna(
                subset=["season_key", "champagne_index"]
            )
            if not race_df.empty and picked:
                seasons_asc = sorted(race_df["season_name"].unique(), key=lambda s: race_df[race_df["season_name"] == s]["season_key"].iloc[0])
                x_max = float(race_df["champagne_index"].max()) * 1.1

                frames = []
                for s in seasons_asc:
                    snap = race_df[race_df["season_name"] == s].set_index("team_name")["champagne_index"]
                    snap = snap.reindex(picked).fillna(0).sort_values()
                    frames.append(go.Frame(
                        data=[go.Bar(x=snap.values, y=snap.index, orientation="h")],
                        name=s,
                    ))

                first = frames[0].data[0]
                fig_race = go.Figure(
                    data=[go.Bar(x=first.x, y=first.y, orientation="h", marker_color="#D4AF37")],
                    frames=frames,
                )
                fig_race.update_layout(
                    xaxis=dict(range=[0, x_max], title="Champagne index"),
                    height=420,
                    updatemenus=[dict(
                        type="buttons", showactive=False,
                        buttons=[
                            dict(label="Play", method="animate",
                                 args=[None, {"frame": {"duration": 700, "redraw": True},
                                               "fromcurrent": True, "transition": {"duration": 300}}]),
                            dict(label="Pause", method="animate",
                                 args=[[None], {"frame": {"duration": 0}, "mode": "immediate"}]),
                        ],
                    )],
                    sliders=[dict(
                        steps=[dict(method="animate", args=[[s], {"frame": {"duration": 300, "redraw": True}}], label=s)
                               for s in seasons_asc],
                    )],
                )
                st.plotly_chart(fig_race, use_container_width=True)
            else:
                st.caption("Pick at least one team.")

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

        full_sample = df.dropna(subset=["delta_index"])
        c1, c2 = st.columns([2, 1])
        top5_only = c1.checkbox(
            "Top-5 European leagues only "
            f"(the full dataset is {len(full_sample):,} team-seasons across every "
            "division and cup since 1960 — unreadable as one scatter plot)",
            value=True,
        )
        min_matches = c2.slider("Min. matches that season", 0, 30, value=10)

        sample = full_sample[full_sample["matches"].fillna(0) >= min_matches]
        if top5_only:
            sample = sample[sample["competition_id"].isin(TOP5_COMPETITION_IDS)]
        st.caption(
            f"Showing {len(sample):,} of {len(full_sample):,} team-seasons. The "
            "fitted trend line uses the full, unfiltered dataset — these controls "
            "only change what's plotted."
        )

        fig2 = go.Figure()
        fig2.add_trace(
            go.Scatter(
                x=sample["total_spend"], y=sample["delta_index"], mode="markers",
                name="Team-season", text=sample["team_name"] + " " + sample["season_name"],
                hovertemplate="%{text}<br>spend=%{x}<br>Δindex=%{y}<extra></extra>",
                opacity=0.45, marker=dict(size=6),
            )
        )
        if sample["total_spend"].max() > 0:
            x_range = [0, sample["total_spend"].max()]
            y_range = [float(m["intercept"]) + float(m["slope"]) * x for x in x_range]
            fig2.add_trace(
                go.Scatter(x=x_range, y=y_range, mode="lines", name="Fitted trend",
                           line=dict(color="#D4AF37", width=3))
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

@st.fragment
def render_lab():
    """Isolated as a fragment on purpose: without it, every slider drag here
    reruns the ENTIRE script — including the 100k+-point 'Spend vs. output'
    and 'Club styles' scatter plots on other tabs — which is where the Lab
    tab's lag was actually coming from. A fragment reruns only this function;
    the RandomForest itself was never the slow part, re-rendering everything
    else on every drag was."""
    lab = load_lab_model()
    if lab is None:
        st.info(
            "No trained model found yet. It's written by the pipeline automatically "
            "on `docker compose up` — reload this tab once that's finished."
        )
        return

    st.markdown(
        "Play with a hypothetical team-season and see what the model (the same "
        "RandomForest from the prediction-model upgrade, R²≈0.15 on held-out "
        "data — a real but modest signal) predicts for next season. Not a real "
        "forecast, an educational toy: drag the sliders and watch the "
        "prediction move."
    )

    prefill_options = ["— blank —"] + lab_team_options(df)
    prefill_team = st.selectbox(
        "Start from a real team's latest season (optional)", prefill_options,
        help="Restricted to the top-5 European leagues with 10+ matches played, "
             "so this list is ~250 teams, not the full 12,600+ across every "
             "division and cup since 1960.",
    )

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


with tab_lab:
    render_lab()

CLUSTER_BLURBS = {
    "Big-spending elite": (
        "The highest attacking output in the dataset (2.04) — but also the "
        "lowest spend efficiency (0.99 index per €M), because they spend the "
        "most by far (€8.3M average). They're buying that output, not finding "
        "it cheaply."
    ),
    "Shoestring overachievers": (
        "Near-elite attacking output (1.63) on essentially no budget (€52k "
        "average spend) — by far the best spend efficiency of any cluster "
        "(28.99 index per €M, ~29x the big spenders). The smart-recruitment "
        "or academy-fed clubs."
    ),
    "Mid-table grinders": (
        "Modest everywhere: below-average attacking output (0.66), average "
        "defensive numbers, modest spend (€565k). The statistical middle of "
        "the table, not a distinct style so much as the absence of one."
    ),
    "Lower-tier / data-sparse": (
        "Not a real tactical style. Near-zero on every metric because these "
        "are teams in competitions where cards and goals-conceded simply "
        "aren't tracked in the source data — a data-coverage artifact, not a "
        "playing style."
    ),
}

with tab_styles:
    if clusters_df.empty:
        st.info(
            "No cluster data yet. Run `docker compose exec pipeline python "
            "club_style_clustering.py` and reload this tab."
        )
    else:
        st.markdown(
            "K-Means on 5 features (Champagne Index, spend efficiency, discipline, "
            "goals conceded per match, clean-sheet rate), first-team squads only, "
            "15+ matches played."
        )

        available_leagues = sorted(clusters_df["competition_name"].dropna().unique())
        default_leagues = [
            l for l in available_leagues
            if l in {"Premier League", "LaLiga", "Serie A", "Bundesliga", "Ligue 1"}
        ] or available_leagues[:5]
        picked_leagues = st.multiselect(
            "Competitions to plot (defaults to the top-5; the full dataset is "
            f"{len(clusters_df):,} team-seasons across every league on record, "
            "which is unreadable as one scatter plot)",
            available_leagues, default=default_leagues,
        )
        plot_df = clusters_df[clusters_df["competition_name"].isin(picked_leagues)]

        if plot_df.empty:
            st.caption("Pick at least one competition.")
        else:
            st.caption(f"Plotting {len(plot_df):,} team-seasons.")
            figc = go.Figure()
            for name, sub in plot_df.groupby("cluster_name"):
                figc.add_trace(go.Scatter(
                    x=sub["spend_efficiency"], y=sub["champagne_index"], mode="markers",
                    name=name, opacity=0.5, marker=dict(size=6),
                    text=sub["team_name"] + " " + sub["season_name"],
                    hovertemplate="%{text}<br>spend_eff=%{x:.2f}<br>index=%{y:.2f}<extra></extra>",
                ))
            figc.update_layout(
                xaxis_title="Spend efficiency (index per €M spent)",
                yaxis_title="Champagne index",
            )
            st.plotly_chart(figc, use_container_width=True)

        st.subheader("What each cluster means")
        profile = clusters_df.groupby("cluster_name")[
            ["champagne_index", "spend_efficiency", "discipline_index",
             "goals_conceded_per_match", "clean_sheet_rate", "total_spend"]
        ].mean()

        for cluster_name in profile.index:
            p = profile.loc[cluster_name]
            st.markdown(
                f"""<div class="cluster-card">
<b>{cluster_name}</b> — avg Champagne index {p['champagne_index']:.2f},
spend efficiency {p['spend_efficiency']:.2f} index/€M,
discipline {p['discipline_index']:.2f} cards/match,
{p['goals_conceded_per_match']:.2f} conceded/match,
{p['clean_sheet_rate']:.0%} clean-sheet rate,
€{p['total_spend']:,.0f} avg spend.<br>
{CLUSTER_BLURBS.get(cluster_name, "")}
</div>""",
                unsafe_allow_html=True,
            )

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
