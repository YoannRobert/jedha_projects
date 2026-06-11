import altair as alt
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

from plotly.subplots import make_subplots


# ---------------------------------------------------------
# Constantes
DATASET_BASE_URL = "https://full-stack-assets.s3.eu-west-3.amazonaws.com/Deployment"
RENTALS_DATASET_URL = f"{DATASET_BASE_URL}/get_around_delay_analysis.xlsx"
STATE_TR = {"canceled" : "annulé", "ended": "terminé"}

# ---------------------------------------------------------
# Personnalisation

METRIC_WIDTH = 175

# Palette officielle Getaround (design system Cobalt)
DEFAULT_COLOR = "#B01AA7" # magenta du logo
ALT_COLOR = "#302652"  # navy
GETAROUND_COLORS = {
    "primary": "#B01AA7",        # magenta du logo
    "primary_alt": "#BC00CC",    # purple-1100 du CSS Cobalt
    "accent": "#8C01DE",         # violet tonic
    "highlight": "#E4FC56",      # lime
    "highlight_soft": "#F6FFC2", # lime alt
    "dark": "#302652",           # navy
    "text": "#1A191A",           # quasi-noir
    "muted": "#797579",          # grey-1100
    "background": "#F1F1F1",     # grey-200
    # Couleurs sémantiques
    "success": "#49B142",
    "danger": "#E41616",
    "warning": "#F0AD35",
    "info": "#1F81F3",
}
GETAROUND_CATEGORICAL = [  # Séquence catégorielle pour Plotly
    "#B01AA7",  # magenta logo
    ALT_COLOR,
    "#E87727",  # orange
    "#49B142",  # green
    "#E41616",  # danger
    #"#F1F1F1",  # grey-200
    "#302652",  # navy
    "#8C01DE",  # violet
]
GETAROUND_SEQUENTIAL = [  # Échelle séquentielle monochrome (rampe purple Cobalt)
    "#F0E1EE", "#E1B4E2", "#DB66E0", "#BC00CC",
    "#B01AA7", "#920E9D", "#77157F", "#5E1964", "#341936",
]

pio.templates["getaround"] = go.layout.Template(
    layout=dict(
        #colorway=GETAROUND_CATEGORICAL,
        width=1000,
    )
)
pio.templates.default = "plotly_dark+getaround"

# ---------------------------------------------------------
# Fonctions
def make_pies(
        configs: list[dict],
        margin: dict | None=None,
        y_pos: float=1.1,
        rotation: int=0
):
    n = len(configs)
    if 1 <= n <= 3:
        nb_rows = 1
        nb_cols = n
        specs = [[{"type": "domain"}] * nb_cols]
    else:
        nb_rows = 1 + (n - 1) // 2
        nb_cols = 2
        specs = [[{"type": "domain"}] * nb_cols] * nb_rows

    fig = make_subplots(
        rows=nb_rows,
        cols=nb_cols,
        specs=specs,
        subplot_titles=[cfg["title"] for cfg in configs],
        vertical_spacing=0.1,
        horizontal_spacing=0.05,
    )

    for idx, cfg in enumerate(configs, start=1):
        row_idx, col_idx = 1 + (idx - 1) // nb_cols, 1 + (idx - 1) % nb_cols
        color_map = cfg["cm"]
        counts = cfg["data"].value_counts()
        labels = counts.index.tolist()
        values = counts.values.tolist()
        colors = [color_map[label] for label in labels]
        try:
            extra_rotation = cfg["extra_rotation"]
        except KeyError:
            extra_rotation = 0

        fig.add_trace(
            go.Pie(
                labels=labels,
                values=values,
                marker=dict(colors=colors),
                textinfo="label+percent",
                textposition="auto",
                textfont=dict(size=18),
                rotation=rotation + extra_rotation,
                showlegend=False,
            ),
            row=row_idx,
            col=col_idx,
        )

    if margin is None:
        margin = dict(t=50, b=20, l=20, r=20)
    fig.update_layout(
        width=400 * nb_cols,
        height=400 * nb_rows,
        margin=margin,
    )

    if nb_rows == 1:
        for annotation in fig.layout.annotations:
            annotation.yanchor = "top"
            annotation.y = y_pos

    st.plotly_chart(fig, use_container_width=True)


def add_consecutive_flag(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["is_consecutive"] = (
        df["time_delta_with_previous_rental_in_minutes"]
        .notna()
    )
    return df


def add_friction_flag(df: pd.DataFrame) -> pd.DataFrame:
    # Friction si le retard (seulement s'il est positif) est supérieur
    # au délai entre les deux locations successives
    col_a = "previous_rental_delay_at_checkout_in_minutes"
    col_b = "time_delta_with_previous_rental_in_minutes"
    df = df.copy()
    df["has_friction"] = np.where(
        df[col_a].isna().astype(int) + df[col_b].isna().astype(int) > 0,
        False,
        (df[col_a] - df[col_b] > 0) & (df[col_a] > 0)
    )
    return df


def merge_with_previous_rental(df: pd.DataFrame) -> pd.DataFrame:
    # Jointure pour ajouter le délai au check-out de la location précédente
    df = df.copy()
    col_a = "rental_id"
    col_b = "delay_at_checkout_in_minutes"
    col_a2 = f"previous_ended_{col_a}"
    col_b2 = f"previous_rental_{col_b}"
    df_previous_rental = df[[col_a, col_b]].rename(columns={col_a: col_a2, col_b: col_b2})
    return df.merge(df_previous_rental, on=col_a2, how="left")


@st.cache_data
def load_data():
    return pd.read_excel(RENTALS_DATASET_URL, sheet_name="rentals_data")

@st.cache_data
def assess_thresholds(
        df: pd.DataFrame,
        t_min: int=0,
        t_max: int=720,
        t_step: int=1,
        scope: str="all"
) -> pd.DataFrame:
    df = df.copy()
    if scope not in ["all", "mobile", "connect"]:
        raise ValueError("scope must be either 'all', 'mobile' or 'connect'")
    if scope in ["mobile", "connect"]:
        df = df[df["checkin_type"] == scope]
    #df = add_friction_flag(merge_with_previous_rental(add_consecutive_flag(df)))
    cons_df = df[df["is_consecutive"]]
    fric_df = df[df["has_friction"]]
    nb_cons = cons_df.shape[0]
    nb_fric = fric_df.shape[0]
    prev_delay_col = "previous_rental_delay_at_checkout_in_minutes"
    time_delta_col = "time_delta_with_previous_rental_in_minutes"
    list_dict = []
    for t in range(t_min, t_max + 1, t_step):
        nb_solved = (fric_df[prev_delay_col] - fric_df[time_delta_col] <= t).astype(int).sum()
        nb_blocked = (cons_df[time_delta_col] < t).sum()
        list_dict.append(
            {
                "scope": scope,
                "threshold": t,
                "nb_solved": nb_solved,
                "resolution_rate": round(100 * nb_solved / nb_fric, 1),
                "nb_blocked": nb_blocked,
                "blocking_rate": round(100 * nb_blocked / nb_cons, 1),
            }
        )
    return pd.DataFrame(list_dict)


def polynomial_fit(df, degree, mode: str="diff"):
    mask = df[["threshold", "resolution_rate", "blocking_rate"]].notna().all(axis=1)
    x = df.loc[mask, "threshold"].values
    if mode == "diff":
        y = df.loc[mask, "resolution_rate"].values - df.loc[mask, "blocking_rate"].values
    elif mode == "res":
        y = df.loc[mask, "resolution_rate"].values
    elif mode == "blk":
        y = df.loc[mask, "blocking_rate"].values
    else:
        raise ValueError("mode must be either 'diff', 'res' or 'blk'")
    bounds = [x.min(), x.max()]
    return np.polynomial.Polynomial.fit(x, y, deg=list(range(1, degree + 1)), domain=bounds, window=bounds)


def compute_blocking_rate(df: pd.DataFrame, t: int | float, scope: str="all") -> int | float:
    return df[(df["scope"] == scope) & (df["threshold"] <= float(t))]["blocking_rate"].max()


def compute_blocked_rentals(df: pd.DataFrame, t: int | float, scope: str="all") -> int | float:
    return df[(df["scope"] == scope) & (df["threshold"] <= float(t))]["nb_blocked"].max()


def compute_resolution_rate(df: pd.DataFrame, t: int | float, scope: str="all") -> int | float:
    return df[(df["scope"] == scope) & (df["threshold"] <= float(t))]["resolution_rate"].max()


def compute_friction_free_rentals(df: pd.DataFrame, t: int | float, scope: str="all") -> int | float:
    return df[(df["scope"] == scope) & (df["threshold"] <= float(t))]["nb_solved"].max()

# ---------------------------------------------------------
# Pré-traitements
rentals = load_data()
nb_rows = rentals.shape[0]
nb_rentals = rentals['rental_id'].nunique()
nb_cars = rentals['car_id'].nunique()

for col in [
    "delay_at_checkout_in_minutes",
    "previous_ended_rental_id",
    "time_delta_with_previous_rental_in_minutes"
]:
    rentals[col] = rentals[col].astype("Int64")

NB_CANCELED = rentals[rentals["state"] == "canceled"].shape[0]
NB_CANCELED_PCT = round(NB_CANCELED / nb_rentals * 100, 2)
rentals_by_state = (
    rentals
    .copy()
    .groupby("state")
    .size()
    .rename("nb_rentals")
    .to_frame()
    .assign(rentals_ratio_pct=lambda x: round(x / nb_rentals * 100, 2))
    .reset_index()
    .replace({"state": STATE_TR})
    .set_index("state", drop=True)
)
rentals_by_checkin_type = (
    rentals
    .copy()
    .groupby("checkin_type")
    .size()
    .rename("nb_rentals")
    .to_frame()
    .assign(rentals_ratio_pct=lambda x: round(x / nb_rentals * 100, 2))
)
checkin_type_by_car = (
    rentals
    .copy()
    .drop_duplicates(subset=["car_id"])
    .groupby("checkin_type")
    .size()
    .rename("nb_cars")
    .to_frame()
    .assign(cars_ratio_pct=lambda x: round(x / nb_cars * 100, 2))
)
delays = rentals.copy()["delay_at_checkout_in_minutes"].dropna()
late_vs_checkin_type = (
    rentals
    .copy()
    [["checkin_type", "delay_at_checkout_in_minutes"]]
    .dropna()
    .assign(
        late=lambda x: (
                x["delay_at_checkout_in_minutes"] >= 0
        ).map({True: "En retard", False: "En avance"})
    )
    .drop(columns=["delay_at_checkout_in_minutes"])
)

late = late_vs_checkin_type["late"]
late_mobile = late_vs_checkin_type[late_vs_checkin_type["checkin_type"] == "mobile"]["late"]
late_connect = late_vs_checkin_type[late_vs_checkin_type["checkin_type"] == "connect"]["late"]

NB_LATE_PCT = round((delays >= 0).sum() / len(delays) * 100, 2)

# Application de la méthode de Tukey pour filtrer les délais aberrants
# Filtrage pour la visualisation uniquement
median_delays = delays.median()
mean_delays = delays.mean()
q1_delays = delays.quantile(0.25)
q3_delays = delays.quantile(0.75)
iqr_delays = q3_delays - q1_delays
k_delays = 3  # facteur 3+ quand il y a des valeurs vraiment extrêmes
lower_bound = q1_delays - k_delays * iqr_delays
upper_bound = q3_delays + k_delays * iqr_delays
filtered_delays = delays[(delays >= lower_bound) & (delays <= upper_bound)]
kept_ratio_delays = len(filtered_delays) / len(delays)

rentals = add_consecutive_flag(rentals)
rentals = merge_with_previous_rental(rentals)
rentals = add_friction_flag(rentals)

NB_CONSECUTIVE = int(rentals["is_consecutive"].sum())
NB_CONSECUTIVE_PCT = round(NB_CONSECUTIVE / nb_rentals * 100, 2)
NB_FRICTION = int(rentals["has_friction"].sum())
NB_FRICTION_GLOBAL_PCT = round(NB_FRICTION / nb_rentals * 100, 2)

FRICTION_TR = {True: "Friction", False: "Pas de friction"}
friction_global_shares = rentals["has_friction"].copy().replace(FRICTION_TR)
friction_consecutive_rental_shares = rentals[rentals["is_consecutive"]].copy()["has_friction"]
friction_consecutive_rental_shares = friction_consecutive_rental_shares.replace(FRICTION_TR)
friction_per_checkin_type = rentals[(rentals["is_consecutive"]) & (rentals["has_friction"])].copy()
friction_per_checkin_type = friction_per_checkin_type["checkin_type"]

state_vs_consecutive_rentals = rentals[["state", "is_consecutive"]].copy().replace(STATE_TR)
state_vs_friction = rentals[["state", "has_friction"]].copy().replace({"state": STATE_TR})

time_col = "time_delta_with_previous_rental_in_minutes"
bins_col = "time_delta_bins"
time_delta = rentals.copy().loc[:, time_col]
max_time_delta = int(time_delta.max())
rentals[bins_col] = pd.cut(rentals[time_col], bins=range(0, max_time_delta + 1, 60), right=True)
friction_counts_per_time_delta_bins = (
    rentals[[bins_col, "has_friction", time_col]]
    .copy()
    .groupby(bins_col, observed=True)
    .agg({"has_friction": "sum", time_col: "count"})
    .rename(columns={"has_friction": "Nombre de cas de friction", time_col: "Nombre de locations"})
    .reset_index()
    .assign(a=lambda df: df[bins_col].apply(lambda x: 0.5*(x.left + x.right)))
    .rename(columns={"a": "Délai entre deux locations successives (min)"})
    .drop(columns=bins_col)
)

# ---------------------------------------------------------
st.set_page_config(
    page_title="Getaround - Analyse des délais au check-out",
    page_icon="️🚗",
    layout="wide"
)

st.title("Getaround — Analyse des délais au check-out")

tab_names = ["Vue d'ensemble", "Simulateur de seuils", "Recommandations"]
tabs = st.tabs(tab_names)

with tabs[0]:
    col = st.columns(spec=1, width=1200)
    col[0].markdown("""
    **Contexte :**  
    Ce tableau de bord permet d'explorer et d'analyser les données relatives aux **délais au moment du check-out**. 
    Il vise à aider à calibrer l'instauration d'un **délai tampon** entre deux locations consécutives.

    **Objectif :**  
    L'objectif de cette fonctionnalité est de **réduire la friction**, 
    occasionnées par le retard au check-out du client précédent et 
    empêchant le client suivant de disposer du véhicule à l'heure prévue.
    L'ajout d'un **délai tampon** réduit la friction. 
    Cependant, il cause aussi une baisse du nombre de locations, 
    donc de chiffre d'affaires pour Getaround ou pour les propriétaires de véhicule.
    Un **optimum** est alors à trouver pour **équilibrer les coûts et les bénéfices**.
    """)

    st.header(tab_names[0])

    nb_cols = 6
    with st.container(horizontal=True, gap="small", border=True, width=1200):
        cols = st.columns(spec=nb_cols, gap="small", width=1200)
        with cols[0]:
            st.metric(label="Nombre de véhicules", value=nb_cars, width="stretch")
        with cols[1]:
            st.metric(label="Nombre de locations", value=nb_rentals, width="stretch")
        with cols[2]:
            st.metric(label="Annulées", value=f"{NB_CANCELED_PCT:.1f} %", delta=NB_CANCELED,
                      delta_description="au total",
                      delta_color="off", delta_arrow="off", width="stretch")
        with cols[3]:
            st.metric(label="En retard", value=f"{NB_LATE_PCT:.1f} %", width="stretch")
        with cols[4]:
            st.metric(label="Consécutives", delta=NB_CONSECUTIVE, delta_arrow="off",
                      delta_description="au total",
                      delta_color="off", value=f"{NB_CONSECUTIVE_PCT} %", width="stretch")
        with cols[5]:
            st.metric(label="En friction", delta=NB_FRICTION, delta_arrow="off",
                      delta_description="au total",
                      delta_color="off", value=f"{NB_FRICTION_GLOBAL_PCT} %", width="stretch")

    st.subheader("Répartition des locations et des voitures selon leur type de check-in")
    with st.container(horizontal=True, gap="small", border=True, width=1200):
        color_map_checkin = {"connect": DEFAULT_COLOR, "mobile": ALT_COLOR}
        pie_configs = [
            # {
            #     "data": rentals["state"].map(STATE_TR),
            #     "title": "Répartition des locations par état",
            #     "cm": {"annulé": DEFAULT_COLOR, "terminé": ALT_COLOR},
            # },
            {
                "data": rentals["checkin_type"],
                "title": "Répartition des locations par type de check-in",
                "cm": color_map_checkin,
            },
            {
                "data": rentals.drop_duplicates(subset=["car_id"])["checkin_type"],
                "title": "Répartition des voitures par type de check-in",
                "cm": color_map_checkin,
            },
        ]
        make_pies(configs=pie_configs, rotation=90)

    st.subheader("Délai au check-out")

    st.markdown("#### En retard vs en avance")

    color_map = {"En retard": DEFAULT_COLOR, "En avance": ALT_COLOR}
    txt = "Quelle part des conducteurs "
    pie_configs = [
        {
            "data": late,
            "title": txt + "arrivent<br>en retard au check-out ?",
            "cm": color_map
        },
        {
            "data": late_mobile,
            "title": txt + "utilisant le<br>check-in mobile arrivent en retard au<br>check-out ?",
            "cm": color_map
        },
        {
            "data": late_connect,
            "title": txt + "utilisant le<br>check-in connect arrivent en retard au<br>check-out ?",
            "cm": color_map,
            "extra_rotation": 180
        },
    ]
    with st.container(horizontal=True, gap="small", border=True, width=1200):
        make_pies(configs=pie_configs, y_pos=1.25, margin=dict(t=80, b=20, l=20, r=20))

    st.markdown("#### Distribution des délais au check-out")

    st.markdown(
        f"{1 - kept_ratio_delays:.1%} des valeurs jugées comme extrêmes ne sont pas prises en compte"
        + " (écartées de plus de 3 IQR par rapport à Q1 et Q3)."
    )
    with st.container(horizontal=True, gap="small", border=True, width=1200):
        fig = px.histogram(filtered_delays, nbins=100, color_discrete_sequence=[DEFAULT_COLOR])
        fig.update_traces(name="Délai au check-out", showlegend=True)
        fig.update_xaxes(title="Délai au check-out (min)")
        fig.update_yaxes(title="Effectif")
        fig.update_traces(marker_line_color="black", marker_line_width=1, opacity=0.8)

        line_configs = [
            {"name": "Restitution à l'heure", "x": 0},
            {"name": f"Délai moyen ({mean_delays:.0f} min)", "x": mean_delays},
            {"name": f"Délai médian ({median_delays:.0f} min)", "x": median_delays},
            {"name": f"Q1 ({q1_delays:.0f} min)", "x": q1_delays},
            {"name": f"Q3 ({q3_delays:.0f} min)", "x": q3_delays}
        ]
        for col_idx, cfg in enumerate(line_configs, start=1):
            fig.add_trace(
                go.Scatter(
                    x=[cfg["x"]] * 2,
                    y=[0, 1],
                    mode="lines",
                    line=dict(color=GETAROUND_CATEGORICAL[col_idx - 1], dash="dash"),
                    name=cfg["name"],
                    yaxis="y2",  # axe secondaire pour s'étendre sur toute la hauteur
                )
            )
        fig.update_layout(
            width=800,
            height=400,
            showlegend=True,
            legend=dict(xref="paper", yref="paper", x=1, y=1, xanchor="right", yanchor="top"),
            margin=dict(t=60, b=20, l=20, r=20),
            yaxis2=dict(
                overlaying="y",
                range=[0, 1],
                showgrid=False,
                showticklabels=False,
                visible=False,  # Axe secondaire invisible
            ),
            title=dict(
                text="Distribution du délai au check-out",
                y=0.95,
                yanchor="top"
            ),
        )
        st.plotly_chart(fig, use_container_width=True)

        fig = px.box(
            rentals[
                (rentals["state"] == "ended")
                & (lower_bound <= rentals["delay_at_checkout_in_minutes"])
                & (rentals["delay_at_checkout_in_minutes"] <= upper_bound)
                ],
            y="checkin_type",
            x="delay_at_checkout_in_minutes",
            orientation="h",
            color="checkin_type",
            color_discrete_sequence=[DEFAULT_COLOR, ALT_COLOR],
            title="Distribution du délai au check out par type de check-in"
        )
        fig.update_traces(
            hoveron="boxes",
            boxmean=True,  # ajoute la moyenne (point ou ligne pointillée)
        )
        fig.update_yaxes(title="Type de check-in")
        fig.update_xaxes(title="Délai au check-out (min)")
        fig.update_layout(height=400, showlegend=False, margin=dict(t=60, b=20, l=20, r=20), )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Locations consécutives")

    pie_configs = [
        {
            "data": rentals["is_consecutive"].map({True: "Consécutives", False: "Non consécutives"}),
            "title": "Quelle est la proportion des locations consécutives ?",
            "cm": {"Consécutives": DEFAULT_COLOR, "Non consécutives": ALT_COLOR},
            "extra_rotation": 110
        },
        {
            "data": (
                (rentals["delay_at_checkout_in_minutes"] > 0)
                .map({True: "En retard", False: "Pas en retard"})
            ),
            "title": "Quelle part des locations initiales<br>étaient en retard au check-out ?",
            "cm": {"En retard": DEFAULT_COLOR, "Pas en retard": ALT_COLOR}
        }
    ]
    with st.container(horizontal=True, gap="small", border=True, width=1200):
        make_pies(configs=pie_configs, y_pos=1.2, margin=dict(t=70, b=10, l=10, r=10))

    st.subheader("Friction")

    color_map_friction = {"Friction": DEFAULT_COLOR, "Pas de friction": ALT_COLOR}
    pie_configs = [
        {
            "data": friction_consecutive_rental_shares,
            "title": "Quelle part des locations consécutives<br>occasionne une friction ?",
            "cm": color_map_friction,
        },
        {
            "data": friction_global_shares,
            "title": "Quelle part globale des locations<br>occasionne une friction ?",
            "cm": color_map_friction,
        },
        {
            "data": friction_per_checkin_type,
            "title": "Quelle est la répartition des types de<br>check-in qui occasionne une friction ?",
            "cm": {"connect": DEFAULT_COLOR, "mobile": ALT_COLOR},
        },
    ]
    with st.container(horizontal=True, gap="small", border=True, width=1200):
        make_pies(configs=pie_configs, rotation=45, y_pos=1.25, margin=dict(t=80, b=20, l=20, r=20))

    st.markdown("#### Taux d'annulation")

    cons = state_vs_consecutive_rentals[state_vs_consecutive_rentals["is_consecutive"]]["state"]
    not_cons = state_vs_consecutive_rentals[~state_vs_consecutive_rentals["is_consecutive"]]["state"]
    fric = state_vs_friction[state_vs_friction["has_friction"] == True]["state"]
    no_fric = state_vs_friction[state_vs_friction["has_friction"] == False]["state"]
    nb_cancelled_consecutive_pct = (cons == "annulé").sum() / cons.shape[0] * 100
    nb_cancelled_not_consecutive_pct = (not_cons == "annulé").sum() / not_cons.shape[0] * 100
    nb_cancelled_friction_pct = (fric == "annulé").sum() / fric.shape[0] * 100
    nb_cancelled_no_friction_pct = (no_fric == "annulé").sum() / no_fric.shape[0] * 100
    nb_cols = 4
    with st.container(horizontal=True, gap="small", border=True, width=1200):
        cols = st.columns(spec=nb_cols, gap="small", width=1200)
        with cols[0]:
            st.metric(label="Locations consécutives", value=f"{nb_cancelled_consecutive_pct:.1f} %",
                      delta=f"{nb_cancelled_consecutive_pct - NB_CANCELED_PCT:,.1f} %",
                      delta_description="vs moyenne", delta_color="inverse", width="stretch")
        with cols[1]:
            st.metric(label="Locations non consécutives", value=f"{nb_cancelled_not_consecutive_pct:.1f} %",
                      delta=f"{nb_cancelled_not_consecutive_pct - NB_CANCELED_PCT:,.1f} %",
                      delta_description="vs moyenne", delta_color="inverse", width="stretch")
        with cols[2]:
            st.metric(label="Locations en friction", value=f"{nb_cancelled_friction_pct:.1f} %",
                      delta=f"{nb_cancelled_friction_pct - NB_CANCELED_PCT:,.1f} %",
                      delta_description="vs moyenne", delta_color="inverse", width="stretch")
        with cols[3]:
            st.metric(label="Locations pas en friction", value=f"{nb_cancelled_no_friction_pct:.1f} %",
                      delta=f"{nb_cancelled_no_friction_pct - NB_CANCELED_PCT:,.1f} %",
                      delta_description="vs moyenne", delta_color="inverse", width="stretch")

    st.subheader("Délai entre deux locations consécutives")

    with st.container(horizontal=True, gap="small", border=True, width=1200):

        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=friction_counts_per_time_delta_bins["Délai entre deux locations successives (min)"],
                y=friction_counts_per_time_delta_bins["Nombre de locations"],
                width=60,  # en unités de l'axe X
                name="Nombre de locations",
                marker=dict(color=DEFAULT_COLOR, line=dict(color="black", width=1)),
                opacity=0.8
            )
        )

        fig.add_trace(
            go.Scatter(
                x=friction_counts_per_time_delta_bins["Délai entre deux locations successives (min)"],
                y=friction_counts_per_time_delta_bins["Nombre de cas de friction"],
                mode="lines",
                line=dict(color=GETAROUND_CATEGORICAL[3]),
                name="Nombre de cas de friction",
                yaxis="y2"
            )
        )

        # Trick to set the range of y2 axis and avoid double grids
        max_y1 = float(friction_counts_per_time_delta_bins["Nombre de locations"].max())
        max_y2 = float(friction_counts_per_time_delta_bins["Nombre de cas de friction"].max())
        n1 = int(np.log10(max_y1))
        n3 = int(np.log10(max_y2))
        max_y1_round_down = int(int(max_y1 / 10 ** n1) * 10 ** n1)
        max_y2_round_up = int(int(1 + max_y2 / 10 ** n3) * 10 ** n3)
        max_y2_round_up = max_y1 / max_y1_round_down * max_y2_round_up

        t_med, t_mean, t_q1 = time_delta.median(), time_delta.mean(), time_delta.quantile(0.25)
        line_configs = [
            {"name": f"Délai médian ({t_med:.0f} min)", "x": t_med},
            {"name": f"Délai moyen ({t_mean:.0f} min)", "x": t_mean},
            {"name": f"Q1 délai ({t_q1:.0f} min)", "x": t_q1},
        ]
        range_y3 = [0, 1]
        for col_idx, cfg in enumerate(line_configs, start=1):
            fig.add_trace(
                go.Scatter(
                    x=[cfg["x"]] * 2,
                    y=range_y3,
                    mode="lines",
                    line=dict(color=GETAROUND_CATEGORICAL[col_idx - 1], dash="dash"),
                    name=cfg["name"],
                    yaxis="y3"
                )
            )

        fig.update_layout(
            showlegend=True,
            title=dict(text="Distributions du délai entre deux locations consécutives et " +
                            "du nombre de cas de friction"),
            xaxis=dict(
                title="Délai entre deux locations consécutives (min)",
                dtick=60
            ),
            yaxis=dict(
                title="Nombre de locations",
                range=[0, max_y1],
            ),
            yaxis2=dict(
                overlaying="y",
                side="right",
                title="Nombre de frictions",
                range=[0, max_y2_round_up]
            ),
            yaxis3=dict(
                overlaying="y",
                visible=False,  # Axe secondaire invisible
                range=range_y3,  # et calé sur 0-1 (proportion de la hauteur)
                showgrid=False,
                showticklabels=False,
            ),
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.2,
                xanchor="center",
                x=0.5,
            ),
        )
        st.plotly_chart(fig, use_container_width=True)

SCOPE_CHOICES = ["all", "connect", "mobile"]
with ((tabs[1])):

    st.header(tab_names[1])

    col1, col2 = st.columns([4, 1], gap="small", vertical_alignment="top", width=1200)
    with col2:
        with st.container(horizontal=True, gap="small", border=True, width=400):
            min_threshold_slider, max_threshold_slider = st.slider(
                label="Valeurs min et max de l'intervalle de seuils à simuler",
                min_value=0,
                max_value=720,
                value=(0, 720),
                step=10,
                width=400
            )
            step_threshold_slider = st.slider(
                label="Valeur du pas de seuils à simuler",
                min_value=1,
                max_value=min(60, max_threshold_slider - min_threshold_slider),
                value=1,
                step=1,
                width=400
            )

            degree_slider = st.slider(
                label="Degré maximal pour la régression polynomiale",
                min_value=2,
                max_value=13,
                value=7,
                step=1,
                width=400
            )

            step_smoothed_threshold_slider = st.slider(
                label="Valeur du pas de seuils pour la régression polynomiale",
                min_value=5,
                max_value=min(60, max_threshold_slider - min_threshold_slider),
                value=15,
                step=5,
                width=400
            )
            display_threshold = st.slider(
                label="Afficher les indicateurs pour ce seuil",
                min_value=min_threshold_slider,
                max_value=max_threshold_slider,
                value=120,
                step=1,
                width=400
            )

            scope_choices_fr = ["tous", "connect", "mobile"]
            selected_scopes_fr = st.pills(
                label="Scope à visualiser",
                options=scope_choices_fr,
                default=scope_choices_fr,
                selection_mode="multi",
                width=400
            )
            selected_scopes = ["all" if scope == "tous" else scope for scope in selected_scopes_fr]

            if not selected_scopes:
                st.warning(body="You must select at least scope.", icon=":material/warning:")
            if "tous" in selected_scopes:
                selected_scopes.remove("tous")
                selected_scopes.append("all")


    first = True
    t_min = min_threshold_slider
    t_max = max_threshold_slider
    t_step = step_threshold_slider
    for scope in SCOPE_CHOICES:
        if first:
            results = assess_thresholds(rentals, scope=scope, t_min=t_min, t_max=t_max, t_step=t_step)
            first = False
        else:
            results_2 = assess_thresholds(rentals, scope=scope, t_min=t_min, t_max=t_max, t_step=t_step)
            results = pd.concat(objs=[results, results_2], ignore_index=True)
    results.reset_index(drop=True, inplace=True)

    # Lissage par régression polynomiale de la différence entre
    # le taux de résolution et le taux de blocage.
    thresholds_smooth = np.arange(min_threshold_slider, max_threshold_slider, step_smoothed_threshold_slider)
    rate_diffs = {}
    optimal_thresholds = {}
    for scope in ["connect", "mobile", "all"]:
        poly = polynomial_fit(results[results["scope"] == scope], degree=degree_slider)
        rate_diffs[scope] = poly
        optimal_thresholds[scope] = thresholds_smooth[np.argmax(poly(thresholds_smooth))]

    with col1:
        with st.container(horizontal=True, gap="small", border=True, width=1200):

            fig = make_subplots(rows=2, cols=1, specs=[[{}], [{"secondary_y": True}]], vertical_spacing=0.1)

            # Récupération des bornes hautes des domaines de chaque sous-graphique
            x_right = [fig.layout["xaxis"].domain[1], fig.layout["xaxis2"].domain[1]]
            y_bottom = [fig.layout["yaxis"].domain[0], fig.layout["yaxis2"].domain[0]]
            y_top = [fig.layout["yaxis"].domain[1], fig.layout["yaxis2"].domain[1]]

            i = 0
            for scope in SCOPE_CHOICES:
                visible = scope in selected_scopes
                for case in ["resolution", "blocking"]:
                    res = results[results["scope"] == scope]
                    case_fr = "blocage" if case == "blocking" else case
                    scope_2 = "mobile & connect" if scope == "all" else scope
                    dash = "solid" if case == "resolution" else "dot"

                    fig.add_trace(
                        go.Scatter(
                            x=res["threshold"],
                            y=res[f"{case}_rate"],
                            line=dict(color=GETAROUND_CATEGORICAL[i], dash=dash),
                            name=f"{case_fr} - {scope_2}",
                            legend="legend",
                            visible=visible,
                        ),
                        row=1, col=1
                    )

                fig.add_trace(
                    go.Scatter(
                        x=res["threshold"],
                        y=res["resolution_rate"] - res["blocking_rate"],
                        line=dict(color=GETAROUND_CATEGORICAL[i]),
                        name=f"{scope_2}",
                        legend="legend2",
                        visible=visible,
                    ),
                    row=2, col=1
                )

                poly = rate_diffs[scope]
                fig.add_trace(
                    go.Scatter(
                        x=thresholds_smooth,
                        y=poly(thresholds_smooth),
                        line=dict(color=GETAROUND_CATEGORICAL[i], dash="dot"),
                        name=f"Rég. polyn. ({scope_2})",
                        legend="legend2",
                        visible=visible,
                    ),
                    row=2, col=1
                )

                t = optimal_thresholds[scope]
                fig.add_trace(
                    go.Scatter(
                        x=[t] * 2,
                        y=[0, 1],
                        mode="lines",
                        line=dict(color=GETAROUND_CATEGORICAL[i], dash="dash"),
                        name=f"Seuil optimal = {t} min ({scope_2})",
                        yaxis="y3",
                        legend="legend2",
                        visible=visible,
                    ),
                    row=2, col=1, secondary_y=True
                )

                i += 1

            fig.add_trace(
                go.Scatter(
                    x=[display_threshold] * 2,
                    y=[0, 1],
                    mode="lines",
                    line=dict(color="red", width=3),
                    name=f"Seuil pour indicateurs = {display_threshold} min",
                    yaxis="y3",
                    legend="legend2",
                ),
                row=2, col=1, secondary_y=True
            )

            fig.update_xaxes(title_text="Seuil (min)")
            fig.update_yaxes(
                title_text="Taux (%)",
                row=1, col=1)

            fig.update_yaxes(
                title_text="Différence de taux (%)",
                secondary_y=False,
                row=2, col=1
            )

            legend_params = {
                "legend" if i == 0 else "legend2": dict(
                    xref="paper", yref="paper",
                    x=x_right[i] + 0.01, y=y_top[i],
                    xanchor="left", yanchor="top",
                )
                for i in [0, 1]
            }

            secondary_axis_params = {
                "yaxis3": dict(
                    overlaying="y2",
                    visible=False,  # Axe secondaire invisible
                    range=[0, 1],  # et calé sur 0-1 (proportion de la hauteur)
                    showgrid=False,
                    showticklabels=False,
                )
            }

            fig.update_layout(
                width=1200,
                height=600,
                #margin=dict(t=50, b=60, l=70, r=0),
                title="Taux de résolution et de blocage en fonction du seuil variable et visualisation des trois seuils optimaux",
                **legend_params,
                **secondary_axis_params
            )
            st.plotly_chart(fig, use_container_width=True)

    st.subheader("Résultats des indicateurs simulés")

    st.markdown("#### Seuils optimaux pour chaque scope")
    with st.container(horizontal=True, gap="small", border=True, width=1200):
        cols = st.columns(spec=3, gap="small", width=1200)
        with cols[0]:
            st.metric(label="mobile + connect", value=f"{optimal_thresholds['all']:d} min",
                      width="stretch")
        with cols[1]:
            st.metric(label="mobile + connect", value=f"{optimal_thresholds['mobile']:d} min",
                      width="stretch")
        with cols[2]:
            st.metric(label="mobile + connect", value=f"{optimal_thresholds['connect']:d} min",
                      width="stretch")

    st.markdown("#### Effets du seuil testé sur les indicateurs")

    col = st.columns(spec=1, width=1200)
    col[0].markdown(
        "Les parts de retards résolus et de locations bloquées sont respectivement exprimées en pourcentage " +
        f"des locations soumises à la friction ({NB_FRICTION} locations) " +
        f"et des locations consécutives ({NB_CONSECUTIVE} locations)."
    )

    resolution_rates = {}
    blocking_rates = {}
    nb_solved_cases = {}
    nb_blocked_cases = {}
    for scope in SCOPE_CHOICES:
        resolution_rates[scope] = compute_resolution_rate(df=results, t=display_threshold, scope=scope)
        blocking_rates[scope] = compute_blocking_rate(df=results, t=display_threshold, scope=scope)
        nb_solved_cases[scope] = compute_friction_free_rentals(df=results, t=display_threshold, scope=scope)
        nb_blocked_cases[scope] = compute_blocked_rentals(df=results, t=display_threshold, scope=scope)

    with st.container(horizontal=True, gap="small", border=True, width=1200):
        row_labels = [
            "Retards résolus (-)",
            "Retards résolus (%)",
            "Locations bloquées (-)",
            "Locations bloquées (%)",
            "Part du revenu total impacté (%)"
        ]
        col_labels = ["Tous véhicules", "Connect uniquement", "Mobile uniquement"]
        header_cols = st.columns(4, vertical_alignment="center", width=1200)
        header_cols[0].metric(label="Seuil testé", value=f"{display_threshold:d} min", width="stretch")
        for col, label in zip(header_cols[1:], col_labels):
            col.markdown(f"**{label}**")
        for i, row_label in enumerate(row_labels):
            row_cols = st.columns(4, vertical_alignment="center", width=1200)
            row_cols[0].markdown(f"**{row_label}**")
            for j, scope in enumerate(SCOPE_CHOICES):
                if i == 0:
                    value = nb_solved_cases[scope]
                elif i == 1:
                    value = resolution_rates[scope]
                elif i == 2:
                    value = nb_blocked_cases[scope]
                elif i == 3:
                    value = blocking_rates[scope]
                else:
                    value = 100 * nb_blocked_cases[scope] / nb_rentals
                value_str = f"{value:.0f}" if i in [0, 2] else f"{value:.1f} %"
                row_cols[1 + j].metric(label="", value=value_str)

with tabs[2]:
    with st.container(border=True, width=1200):
        st.caption("**RECOMMANDATION**")
        st.markdown("#### Seuil de 120 min, check-in Connect uniquement")
        st.markdown("Déploiement en deux phases, avec extension conditionnelle au mobile après 3 à 6 mois.")

    st.write("")
    # KPIs principaux
    kpi_cols = st.columns(4, width=1200)
    kpis = [
        ("Friction résolue", "84%", "sur le segment Connect"),
        ("Friction totale résolue", "27%", "tous canaux confondus"),
        ("Locations bloquées", "1,4%", "~2x moins que global"),
        ("Sur-représentation Connect", "1,57x", "31,7% friction / 20,2% loc."),
    ]
    for col, (label, value, help_text) in zip(kpi_cols, kpis):
        col.metric(label=label, value=value, help=help_text)

    st.write("")
    st.markdown("##### Pourquoi cette stratégie")

    reasons = [
        ("⚡ Faisabilité technique",
         "Connect est nativement digital : blocage automatique trivial. Mobile repose sur une rencontre humaine."),
        ("💰 Coût mesuré",
         "1,4% des locations bloquées contre 3,1% en déploiement global, pour 27% de friction résolue."),
        ("📈 Apprentissage incrémental",
         "Validation des hypothèses sur périmètre restreint avant généralisation."),
    ]
    cols = st.columns(spec=3, width=1200, vertical_alignment="bottom")
    for i, (title, body) in enumerate(reasons):
        with cols[i].container(border=True):
            st.markdown(f"**{title}**")
            st.caption(body)

    with st.container(border=True, width=1200):
        first = True
        for scope in SCOPE_CHOICES:
            if first:
                results_reco = assess_thresholds(rentals, scope=scope)
                first = False
            else:
                results_reco_2 = assess_thresholds(rentals, scope=scope)
                results_reco = pd.concat(objs=[results_reco, results_reco_2], ignore_index=True)
        results_reco.reset_index(drop=True, inplace=True)

        fig = go.Figure()
        i = 0
        symbols = ["circle", "diamond", "square", "cross", "x"]
        thresholds = [60, 120, 180]
        for scope in SCOPE_CHOICES:
            res = results_reco[(results_reco["scope"] == scope) & (results_reco["threshold"] >= 30)]
            scope_2 = "mobile & connect" if scope == "all" else scope
            dash = "solid" if case == "resolution" else "dot"
            fig.add_trace(
                go.Scatter(
                    x=res["blocking_rate"][::10],
                    y=res["resolution_rate"][::10],
                    line=dict(color=GETAROUND_CATEGORICAL[i]),
                    name=scope_2,
                )
            )
            for j, t in enumerate(thresholds):
                fig.add_trace(
                    go.Scatter(
                        x=[compute_blocking_rate(res, t, scope=scope)],
                        y=[compute_resolution_rate(res, t, scope=scope)],
                        mode="markers+text" if scope == "connect" else "markers",
                        text=[f"{t} min"],
                        textposition="top center",
                        marker=dict(
                            color=GETAROUND_CATEGORICAL[i],
                            size=20,
                            symbol=symbols[j % len(symbols)],
                        ),
                        showlegend=False,
                    )
                )
            i += 1

        fig.update_layout(
            height=600,
            legend=dict(xref="paper", yref="paper", x=0.97, y=0.03, xanchor="right", yanchor="bottom"),
            xaxis=dict(title='Taux de blocage (%) [métrique du coût]'),
            yaxis=dict(title='Taux de résolution (%) [proxy du bénéfice]'),
            title=dict(text="Bénéfice vs coût")
        )
        st.plotly_chart(fig, use_container_width=True)

    st.write("")
    st.markdown("##### Contexte de l'analyse")

    context = [
        ("Locations annulées", "15,3%"),
        ("Retard moyen au check-out", "1 h"),
        ("Check-out en retard", "58,3%"),
        ("Locations consécutives (< 12 h)", "8,64%"),
        ("Cas de friction", "1,02%"),
        ("Annulation si friction", "17,0% (+1,7%)"),
        ("Optimum mathématique Connect", "1 h 45 min"),
        ("Tolérance autour du seuil", "±30 min"),
    ]
    with st.container(border=True, width=1200):
        for row_start in range(0, len(context), 2):
            cols = st.columns(2)
            for col, (label, value) in zip(cols, context[row_start:row_start + 2]):
                left, right = col.columns([3, 1])
                left.markdown(
                    body=f"<span style='color: gray;'>{label}</span>",
                    unsafe_allow_html=True,
                )
                right.markdown(f"**{value}**")

    st.write("")
    st.markdown("##### Limites et perspectives")
    with st.container(border=True, width=1200):
        st.markdown(
            "- Causes d'annulation non renseignées : le gain réel pourrait dépasser l'estimation.\n"
            "- Test A/B sur la phase 1 pour mesurer l'impact effectif sur CA propriétaires et satisfaction.\n"
            "- Phase 2 conditionnelle : extension au mobile, ajustement par segment, ou maintien du périmètre Connect."
        )
