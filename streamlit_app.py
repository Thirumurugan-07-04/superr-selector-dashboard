"""Interactive companion dashboard for the SupeRR Selector pressure methodology."""

from __future__ import annotations

import json
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st


ROOT = Path(__file__).resolve().parent
STYLE_PATH = Path(__file__).with_name("rr_style.css")


def locate_data_file(filename: str) -> Path:
    """Accept either simple root uploads or the original data-folder layout."""
    for candidate in (ROOT / filename, ROOT / "data" / filename):
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"Missing {filename}. Upload it beside streamlit_app.py, or place it in a data folder."
    )


PRESSURE_DATA = locate_data_file("pressure_states.csv.gz")
PRESSURE_REPORT = locate_data_file("pressure_report.json")
BATTER_BOARD = locate_data_file("batter_board.csv")
BOWLER_BOARD = locate_data_file("bowler_board.csv")

st.set_page_config(
    page_title="Under Pressure | Royals analytics",
    page_icon=":material/sports_cricket:",
    layout="wide",
)
st.html(STYLE_PATH)


def page_hero(kicker: str, title: str, description: str) -> None:
    """Render a consistent sports-dashboard header using trusted static content."""
    st.html(
        f"""
        <section class="rr-hero">
          <div class="rr-kicker">{kicker}</div>
          <h1>{title}</h1>
          <p>{description}</p>
        </section>
        """
    )


def section_label(text: str) -> None:
    st.html(f'<div class="rr-section-label">{text}</div>')


@st.cache_data(show_spinner="Loading scored match situations...")
def load_data() -> tuple[pd.DataFrame, dict]:
    data = pd.read_csv(
        PRESSURE_DATA,
        usecols=[
            "match_id", "competition", "innings", "match_date", "over", "striker", "bowler",
            "score_before", "wickets_before", "legal_balls_before", "par_score", "pressure_score",
            "pressure_band", "high_pressure_ball", "wicket_on_ball", "total_runs", "batter_runs",
            "legal_delivery",
        ],
        low_memory=False,
    )
    data["match_date"] = pd.to_datetime(data["match_date"], errors="coerce")
    data = data.loc[data["legal_delivery"]].copy()
    data["match_label"] = (
        data["match_date"].dt.strftime("%d %b %Y").fillna("Unknown date")
        + " | " + data["competition"].astype(str)
        + " | Match " + data["match_id"].astype(str)
    )
    with PRESSURE_REPORT.open(encoding="utf-8") as file:
        report = json.load(file)
    return data, report


@st.cache_data(show_spinner="Loading Top 10 pressure boards...")
def load_player_boards() -> tuple[pd.DataFrame, pd.DataFrame]:
    batters = pd.read_csv(BATTER_BOARD)
    bowlers = pd.read_csv(BOWLER_BOARD)
    return batters, bowlers


def load_par_reference(data: pd.DataFrame) -> tuple[dict[tuple[int, int], float], dict[int, float]]:
    """Return the same historical par reference used by the scored dataset."""
    first_innings = data.loc[data["innings"] == 1].copy()
    first_innings["wicket_bucket"] = first_innings["wickets_before"].clip(upper=7)
    by_state = first_innings.groupby(["legal_balls_before", "wicket_bucket"])["par_score"].mean()
    by_ball = first_innings.groupby("legal_balls_before")["par_score"].mean()
    return by_state.to_dict(), by_ball.to_dict()


def clip_score(value: float) -> float:
    return max(0.0, min(100.0, value))


def practical_pressure_calculation(
    innings_type: str,
    legal_balls: int,
    score: int,
    wickets: int,
    target: int,
    recent_wickets: int,
    dot_streak: int,
    par_by_state: dict[tuple[int, int], float],
    par_by_ball: dict[int, float],
) -> tuple[float, str, pd.DataFrame]:
    """Mirror the submitted pressure formula from real match-state inputs."""
    phase_stress = clip_score(100 * legal_balls / 120)
    wicket_stress = clip_score(100 * wickets / 6)
    collapse_stress = 100.0 if recent_wickets >= 2 else 50.0 if recent_wickets == 1 and wickets >= 3 else 0.0
    dot_ball_stress = clip_score(100 * dot_streak / 3)

    if innings_type == "Chase":
        balls_remaining = max(1, 120 - legal_balls)
        runs_required = max(0, target - score)
        required_rate = runs_required / (balls_remaining / 6)
        urgency_stress = clip_score(100 * (required_rate - 6) / 8)
        urgency_detail = f"Need {runs_required} from {balls_remaining} balls. Required rate: {required_rate:.1f}."
    else:
        par_score = float(par_by_state.get((legal_balls, min(wickets, 7)), par_by_ball.get(legal_balls, 0.0)))
        par_deficit = max(0.0, par_score - score)
        urgency_stress = clip_score(100 * par_deficit / 20)
        urgency_detail = f"Historical par: {par_score:.1f}. Current deficit: {par_deficit:.1f} runs."

    components = [
        ("Urgency or par deficit", 35, urgency_stress, urgency_detail),
        ("Wicket stress", 25, wicket_stress, f"{wickets} wickets lost. Full wicket stress begins at 6 wickets."),
        ("Match phase", 20, phase_stress, f"{legal_balls} legal balls completed. Pressure rises as fewer balls remain."),
        ("Recent collapse", 10, collapse_stress, f"{recent_wickets} wickets in the last 18 legal balls."),
        ("Dot-ball pressure", 10, dot_ball_stress, f"Current batter has faced {dot_streak} consecutive dot balls."),
    ]
    table = pd.DataFrame(components, columns=["Component", "Weight", "Stress score", "How it was calculated"])
    table["Contribution"] = table["Weight"] / 100 * table["Stress score"]
    pressure = float(table["Contribution"].sum())
    band = "Extreme" if pressure >= 80 else "High" if pressure >= 60 else "Medium" if pressure >= 40 else "Low"
    return pressure, band, table


def render_methodology(data: pd.DataFrame, report: dict) -> None:
    page_hero(
        "SupeRR Selector Season 2",
        "Under pressure",
        "A transparent ball-by-ball system for finding cricket’s most reliable performers when the game tightens.",
    )
    section_label("Pressure overview")

    with st.container(horizontal=True):
        st.metric("Legal balls scored", f"{report['legal_balls_scored']:,}", border=True)
        st.metric("High-pressure balls", f"{report['high_pressure_legal_balls']:,}", border=True)
        st.metric("High-pressure share", f"{report['high_pressure_share']:.1%}", border=True)
        st.metric("High-pressure cutoff", "60 / 100", border=True)

    left, right = st.columns([1.25, 1])
    with left:
        with st.container(border=True):
            st.subheader("How a ball receives a pressure score")
            components = pd.DataFrame(
                [
                    ["Urgency or par deficit", "35%", "Chase: required run-rate stress. First innings: score below par."],
                    ["Wicket stress", "25%", "Fewer wickets available raises risk."],
                    ["Match phase", "20%", "Pressure rises as fewer balls remain in the innings."],
                    ["Collapse stress", "10%", "Recent wickets or a fast early collapse."],
                    ["Dot-ball stress", "10%", "Consecutive dots increase pressure on the batter."],
                ],
                columns=["Component", "Weight", "Plain-English meaning"],
            )
            st.dataframe(components, hide_index=True, width="stretch")
            st.latex(r"Pressure = 0.35U + 0.25W + 0.20P + 0.10C + 0.10D")
            st.caption("The score is calculated before the ball result. A wicket or boundary cannot make its own ball appear pressured.")
    with right:
        with st.container(border=True):
            st.subheader("Pressure bands in the scored data")
            band_order = ["Low", "Medium", "High", "Extreme"]
            band_counts = (
                data["pressure_band"]
                .value_counts()
                .reindex(band_order, fill_value=0)
                .rename_axis("Pressure band")
                .reset_index(name="Legal balls")
            )
            chart = alt.Chart(band_counts).mark_bar().encode(
                x=alt.X("Pressure band:N", sort=band_order),
                y=alt.Y("Legal balls:Q"),
                color=alt.Color("Pressure band:N", scale=alt.Scale(domain=band_order, range=["#7AA6C2", "#F3C969", "#EA9A50", "#CF5C5C"]), legend=None),
                tooltip=["Pressure band:N", "Legal balls:Q"],
            ).properties(height=280)
            st.altair_chart(chart, width="stretch")

    with st.container(border=True):
        st.subheader("What this stage does and does not do")
        st.write("This stage identifies difficult moments. The next stage will value batter performance only inside those moments: scoring, survival, rescue ability and reliability.")


def render_calculator(par_by_state: dict[tuple[int, int], float], par_by_ball: dict[int, float]) -> None:
    page_hero(
        "Interactive tool",
        "Pressure calculator",
        "Enter a real cricket situation. The dashboard calculates every pressure percentage using the submitted formula.",
    )

    st.caption("Example loaded: 61 needed from 34 balls, 4 wickets down, after a recent wicket and two dots.")
    with st.form("practical_pressure_calculator"):
        innings_type = st.segmented_control("Innings", ["Chase", "First innings"], default="Chase", required=True)
        left, middle, right = st.columns(3)
        with left:
            completed_overs = st.number_input("Completed overs", min_value=0, max_value=19, value=14, step=1, help="Enter fully completed overs. For 14.2 overs, enter 14 here and 2 balls below.")
            balls_in_over = st.number_input("Balls in the current over", min_value=0, max_value=5, value=2, step=1, help="Use 0 after a completed over. A cricket over has six legal balls.")
        with middle:
            score = st.number_input("Current team score", min_value=0, max_value=300, value=120, step=1)
            wickets = st.number_input("Wickets lost", min_value=0, max_value=9, value=4, step=1)
        with right:
            target = st.number_input("Target score", min_value=1, max_value=301, value=181, step=1, disabled=innings_type != "Chase", help="Used only for a chase. Leave the default when calculating a first innings.")
            recent_wickets = st.number_input("Wickets in the last 18 legal balls", min_value=0, max_value=5, value=1, step=1)
            dot_streak = st.number_input("Consecutive dots faced by the current batter", min_value=0, max_value=6, value=2, step=1)
        calculate = st.form_submit_button("Calculate pressure", icon=":material/calculate:")

    if calculate or "calculator_has_run" not in st.session_state:
        st.session_state.calculator_has_run = True
        legal_balls = int(completed_overs * 6 + balls_in_over)
        if legal_balls >= 120:
            st.error("Use a point before the final legal ball of the 20-over innings.", icon=":material/error:")
            return
        score_value, band, breakdown = practical_pressure_calculation(
            innings_type, legal_balls, int(score), int(wickets), int(target), int(recent_wickets), int(dot_streak), par_by_state, par_by_ball
        )
        st.metric("Calculated pressure score", f"{score_value:.1f} / 100", f"{band} pressure", border=True)
        st.caption("High pressure begins at 60. The score uses the match situation before the next ball is bowled.")
        display = breakdown.copy()
        display["Weight"] = display["Weight"].map("{}%".format)
        display["Stress score"] = display["Stress score"].map("{:.1f}".format)
        display["Contribution"] = display["Contribution"].map("{:.1f}".format)
        with st.container(border=True):
            st.subheader("How the score was built")
            st.dataframe(display, hide_index=True, width="stretch")
            st.caption("Contribution = component stress score × its weight. The five contributions add up to the final pressure score.")


def render_explorer(data: pd.DataFrame) -> None:
    page_hero(
        "Ball-by-ball view",
        "Match pressure explorer",
        "Choose a match and watch pressure build, break and return across an innings.",
    )

    matches = data[["match_id", "match_label"]].drop_duplicates().sort_values("match_label")
    chosen_label = st.selectbox("Choose a match", matches["match_label"].tolist())
    chosen_match = int(matches.loc[matches["match_label"] == chosen_label, "match_id"].iloc[0])
    available_innings = sorted(data.loc[data["match_id"] == chosen_match, "innings"].unique())
    innings = st.segmented_control("Innings", available_innings, default=available_innings[0], required=True)
    match_data = data.loc[(data["match_id"] == chosen_match) & (data["innings"] == innings)].copy()
    match_data["Ball"] = range(1, len(match_data) + 1)
    match_data["Over.ball"] = match_data["over"].astype(str) + "." + (match_data.groupby("over").cumcount() + 1).astype(str)

    with st.container(horizontal=True):
        st.metric("Average pressure", f"{match_data['pressure_score'].mean():.1f}", border=True)
        st.metric("High-pressure balls", f"{int(match_data['high_pressure_ball'].sum())}", border=True)
        st.metric("Wickets", f"{int(match_data['wicket_on_ball'].sum())}", border=True)
        st.metric("Final score", f"{int(match_data['score_before'].iloc[-1] + match_data['total_runs'].iloc[-1])}/{int(match_data['wicket_on_ball'].sum())}", border=True)

    with st.container(border=True):
        line = alt.Chart(match_data).mark_line(color="#1F4E78", strokeWidth=3).encode(
            x=alt.X("Ball:Q", title="Delivery in innings"),
            y=alt.Y("pressure_score:Q", title="Pressure Score", scale=alt.Scale(domain=[0, 100])),
            tooltip=["Over.ball:N", "striker:N", "bowler:N", alt.Tooltip("pressure_score:Q", format=".1f"), "pressure_band:N", "score_before:Q", "wickets_before:Q"],
        )
        wickets = alt.Chart(match_data.loc[match_data["wicket_on_ball"]]).mark_point(shape="diamond", size=85, color="#C43838").encode(
            x="Ball:Q", y="pressure_score:Q", tooltip=["Over.ball:N", "striker:N", "pressure_score:Q"],
        )
        cutoff = alt.Chart(pd.DataFrame({"cutoff": [60]})).mark_rule(color="#D77B13", strokeDash=[6, 4]).encode(y="cutoff:Q")
        st.altair_chart((line + wickets + cutoff).properties(height=380), width="stretch")
        st.caption("Red diamonds show wickets. The dashed line is the high-pressure cutoff of 60.")

    only_high = st.toggle("Show only high-pressure balls", value=True)
    table = match_data.loc[match_data["high_pressure_ball"]].copy() if only_high else match_data.copy()
    st.dataframe(
        table[["Over.ball", "striker", "bowler", "score_before", "wickets_before", "pressure_score", "pressure_band", "batter_runs", "wicket_on_ball"]],
        column_config={
            "pressure_score": st.column_config.NumberColumn("Pressure score", format="%.1f"),
            "score_before": st.column_config.NumberColumn("Score before"),
            "wickets_before": st.column_config.NumberColumn("Wickets before"),
            "batter_runs": st.column_config.NumberColumn("Batter runs"),
            "wicket_on_ball": st.column_config.CheckboxColumn("Wicket"),
        },
        hide_index=True,
        width="stretch",
    )


def render_top10(batters: pd.DataFrame, bowlers: pd.DataFrame) -> None:
    page_hero(
        "Performance boards",
        "Top 10 under pressure",
        "Separate batter and bowler leaderboards built from performance in difficult match situations, with minimum evidence rules.",
    )
    batter_top10 = batters.loc[batters["eligible_for_final_ranking"]].sort_values("rank").head(10)
    bowler_top10 = bowlers.loc[bowlers["eligible"]].sort_values("rank").head(10)
    with st.container(horizontal=True):
        st.metric("No. 1 batter", batter_top10.iloc[0]["striker"], f"{batter_top10.iloc[0]['final_pressure_value']:.1f} Pressure Value", border=True)
        st.metric("No. 1 bowler", bowler_top10.iloc[0]["bowler"], f"{bowler_top10.iloc[0]['final_pressure_value']:.1f} Pressure Value", border=True)
    with st.container(horizontal=True):
        st.metric("Eligible batters", str(int(batters["eligible_for_final_ranking"].sum())), border=True)
        st.metric("Eligible bowlers", str(int(bowlers["eligible"].sum())), border=True)
        st.metric("Batter evidence rule", "150 balls, 5 matches", border=True)
        st.metric("Bowler evidence rule", "150 balls, 5 matches", border=True)

    left, right = st.columns(2)
    with left:
        st.subheader("Top 10 batters")
        st.dataframe(
            batter_top10[["rank", "striker", "final_pressure_value", "pressure_balls", "pressure_matches"]],
            column_config={
                "rank": st.column_config.NumberColumn("Rank", format="%d"),
                "striker": "Batter",
                "final_pressure_value": st.column_config.NumberColumn("Pressure Value", format="%.1f"),
                "pressure_balls": st.column_config.NumberColumn("Pressure balls"),
                "pressure_matches": st.column_config.NumberColumn("Pressure matches"),
            },
            hide_index=True,
            width="stretch",
        )
    with right:
        st.subheader("Top 10 bowlers")
        st.dataframe(
            bowler_top10[["rank", "bowler", "final_pressure_value", "pressure_balls", "pressure_matches"]],
            column_config={
                "rank": st.column_config.NumberColumn("Rank", format="%d"),
                "bowler": "Bowler",
                "final_pressure_value": st.column_config.NumberColumn("Pressure Value", format="%.1f"),
                "pressure_balls": st.column_config.NumberColumn("Pressure balls"),
                "pressure_matches": st.column_config.NumberColumn("Pressure matches"),
            },
            hide_index=True,
            width="stretch",
        )

    with st.container(border=True):
        st.subheader("Final formulas")
        st.write("Batters: 45% scoring impact, 25% survival, 20% rescue ability, 10% reliability.")
        st.write("Bowlers: 45% competition-adjusted run prevention, 25% wicket advantage, 20% dot-ball advantage, 10% reliability.")


st.html('<div class="rr-navigation-label">Choose a dashboard section</div>')
view = st.segmented_control(
    "Dashboard section",
    ["Methodology", "Calculator", "Match explorer", "Top 10"],
    default="Methodology",
    required=True,
    width="stretch",
    label_visibility="collapsed",
)
st.caption("Start with Methodology, then try the Calculator or view the final Top 10 rankings.")

data, report = load_data()
batters, bowlers = load_player_boards()
par_by_state, par_by_ball = load_par_reference(data)

if view == "Methodology":
    render_methodology(data, report)
elif view == "Calculator":
    render_calculator(par_by_state, par_by_ball)
elif view == "Match explorer":
    render_explorer(data)
elif view == "Top 10":
    render_top10(batters, bowlers)
