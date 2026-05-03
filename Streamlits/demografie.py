"""
demografie.py  –  Demografisch dashboard + familiestructuur + config-editor + register-export.
Start met:  streamlit run Streamlits/demografie.py
"""

import sys
import json
import socket
import subprocess
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "Scripts"))

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st


# --------------------------------------------------------------------------- #
# Paden
# --------------------------------------------------------------------------- #
ROOT        = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"
SAVE_DIR    = ROOT / "Generated Data"
SCRIPTS_DIR = ROOT / "Scripts"
SAVE_DIR.mkdir(exist_ok=True)

# --------------------------------------------------------------------------- #
# Pagina-config
# --------------------------------------------------------------------------- #
st.set_page_config(
    page_title="Fictief Belgisch Register",
    page_icon="🇧🇪",
    layout="wide",
)

COLORS = {
    "M":      "#4878CF",
    "F":      "#E24A33",
    "accent": "#2ecc71",
    "muted":  "#95a5a6",
}
NAT_PALETTE = px.colors.qualitative.Safe


# --------------------------------------------------------------------------- #
# Config helpers
# --------------------------------------------------------------------------- #
def lees_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)

def schrijf_config(cfg: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


# --------------------------------------------------------------------------- #
# Data helpers
# --------------------------------------------------------------------------- #
def _leeftijd_toevoegen(rr: pd.DataFrame, bis: pd.DataFrame) -> tuple:
    cfg = lees_config()
    ref = pd.Timestamp(cfg["meta"]["creation_date"])
    for df in (rr, bis):
        df["geboortedatum"] = pd.to_datetime(df["geboortedatum"])
        df["leeftijd"] = ((ref - df["geboortedatum"]).dt.days // 365).clip(0, 110)
    return rr, bis


def scan_registers(save_dir: Path) -> list[dict]:
    """Zoekt complete register-paren (RR + BIS) in de opslagmap."""
    paren = []
    for rr_pad in sorted(save_dir.glob("*_rijksregister.json")):
        prefix  = rr_pad.name.replace("_rijksregister.json", "")
        bis_pad = save_dir / f"{prefix}_bisregister.json"
        if bis_pad.exists():
            paren.append({
                "prefix":     prefix,
                "rr_pad":     rr_pad,
                "bis_pad":    bis_pad,
                "fam_pad":    save_dir / f"{prefix}_families.json",
                "opgeslagen": datetime.fromtimestamp(rr_pad.stat().st_mtime),
            })
    return sorted(paren, key=lambda p: p["opgeslagen"], reverse=True)


@st.cache_data(show_spinner="Registers inlezen van schijf…")
def load_van_schijf(rr_pad: str, bis_pad: str, _rr_mtime: float, _bis_mtime: float):
    rr  = pd.read_json(rr_pad,  convert_dates=False)
    bis = pd.read_json(bis_pad, convert_dates=False)
    return _leeftijd_toevoegen(rr, bis)



@st.cache_data(show_spinner="Families inlezen van schijf…")
def load_families(fam_pad: str, _mtime: float) -> pd.DataFrame:
    df = pd.read_json(fam_pad, convert_dates=False)
    _verrijk_families(df)
    return df


def _verrijk_families(df: pd.DataFrame) -> None:
    """Voeg berekende kolommen toe (in-place)."""
    cfg = lees_config()
    ref = pd.Timestamp(cfg["meta"]["creation_date"])
    df["geboortedatum"] = pd.to_datetime(df["geboortedatum"], errors="coerce")
    df["leeftijd"]      = ((ref - df["geboortedatum"]).dt.days // 365).clip(0, 120)
    df["n_kinderen"]    = df["kinderen_rr"].apply(
        lambda x: len(x) if isinstance(x, list) else 0
    )


def leeftijdsbanden(df: pd.DataFrame) -> pd.DataFrame:
    bins   = list(range(0, 116, 5))
    labels = [f"{i}–{i+4}" for i in range(0, 111, 5)]
    out = df.copy()
    out["band"] = pd.cut(out["leeftijd"], bins=bins, labels=labels, right=False)
    return out


# --------------------------------------------------------------------------- #
# Diensten helpers
# --------------------------------------------------------------------------- #
def _port_actief(poort: int) -> bool:
    try:
        with socket.create_connection(("localhost", poort), timeout=0.5):
            return True
    except (ConnectionRefusedError, OSError):
        return False


# --------------------------------------------------------------------------- #
# Persoonskaart helpers
# --------------------------------------------------------------------------- #
def _bouw_fam_idx(df: pd.DataFrame) -> dict:
    """Bouw opzoektabel: rijksregisternummer → rij als dict (met string-datums)."""
    idx = {}
    for _, row in df.iterrows():
        rr = row.get("rijksregisternummer")
        if rr is None or (isinstance(rr, float) and pd.isna(rr)):
            continue
        d = {}
        for k, v in row.items():
            if isinstance(v, (list, dict)):
                d[k] = v
            elif hasattr(v, "isoformat"):
                d[k] = v.isoformat()[:10] if not pd.isna(v) else None
            else:
                try:
                    d[k] = None if pd.isna(v) else v
                except (TypeError, ValueError):
                    d[k] = v
        idx[str(rr)] = d
    return idx


def _zoek_persoon(nr: str, fam: pd.DataFrame, rr_df: pd.DataFrame, bis_df: pd.DataFrame):
    """Zoek een persoon op nummer. Geeft (row_dict, bronnaam) terug."""
    nr = nr.strip()
    for df, id_col, bron in [
        (fam,    "rijksregisternummer", "Families"),
        (rr_df,  "rijksregisternummer", "Rijksregister"),
        (bis_df, "bisnummer",           "Bisregister"),
    ]:
        if id_col not in df.columns:
            continue
        mask = df[id_col].astype(str) == nr
        if mask.any():
            row = df[mask].iloc[0]
            d = {}
            for k, v in row.items():
                if isinstance(v, (list, dict)):
                    d[k] = v
                elif hasattr(v, "isoformat"):
                    d[k] = v.isoformat()[:10] if not pd.isna(v) else None
                else:
                    try:
                        d[k] = None if pd.isna(v) else v
                    except (TypeError, ValueError):
                        d[k] = v
            return d, bron
    return None, None


def _familie_tabel(persoon: dict, idx: dict) -> pd.DataFrame:
    """Bouw een tabel van alle verwanten van een persoon."""
    rows = []
    focus_rr = str(persoon.get("rijksregisternummer", ""))

    def add(rr_raw, relatie):
        if not rr_raw:
            return
        rr = str(rr_raw)
        if rr not in idx:
            return
        r = idx[rr]
        geb = str(r.get("geboortedatum", "") or "")[:10]
        ovl = str(r.get("overlijdensdatum", "") or "")[:10]
        rows.append({
            "Relatie":      relatie,
            "Naam":         f"{r.get('voornaam', '')} {r.get('familienaam', '')}",
            "Geslacht":     r.get("geslacht", ""),
            "Geboren":      geb,
            "Overleden":    ovl,
            "Nummer":       rr,
        })

    # Grootouders vaderszijde
    vader_rr = persoon.get("vader_rr")
    if vader_rr and str(vader_rr) in idx:
        vader = idx[str(vader_rr)]
        add(vader.get("vader_rr"), "Grootvader (vaderszijde)")
        add(vader.get("moeder_rr"), "Grootmoeder (vaderszijde)")

    # Grootouders moederszijde
    moeder_rr = persoon.get("moeder_rr")
    if moeder_rr and str(moeder_rr) in idx:
        moeder = idx[str(moeder_rr)]
        add(moeder.get("vader_rr"), "Grootvader (moederszijde)")
        add(moeder.get("moeder_rr"), "Grootmoeder (moederszijde)")

    # Ouders
    add(vader_rr, "Vader")
    add(moeder_rr, "Moeder")

    # Broers/zussen (via vader, ontdubbeld)
    gezien = {focus_rr}
    for par_key in ["vader_rr", "moeder_rr"]:
        par_rr = persoon.get(par_key)
        if not par_rr or str(par_rr) not in idx:
            continue
        siblings = idx[str(par_rr)].get("kinderen_rr") or []
        if not isinstance(siblings, list):
            continue
        for sib_rr in siblings:
            sib_rr_s = str(sib_rr)
            if sib_rr_s in gezien:
                continue
            gezien.add(sib_rr_s)
            add(sib_rr_s, "Broer/Zus")

    # Partner
    add(persoon.get("partner_rr"), "Partner")

    # Kinderen
    kinderen = persoon.get("kinderen_rr") or []
    if not isinstance(kinderen, list):
        kinderen = []
    for kind_rr in kinderen:
        add(kind_rr, "Kind")

    # Kleinkinderen
    for kind_rr in kinderen:
        ks = str(kind_rr)
        if ks not in idx:
            continue
        klein = idx[ks].get("kinderen_rr") or []
        if not isinstance(klein, list):
            continue
        for kk in klein:
            add(kk, "Kleinkind")

    return pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=["Relatie", "Naam", "Geslacht", "Geboren", "Overleden", "Nummer"]
    )


def _teken_stamboom(focus_rr: str, idx: dict) -> go.Figure | None:
    """
    Bouw een stamboom-figuur voor de focuspersoon.

    Layout (y-as, hoog = oud):
      +2*YGAP  grootouders
      +YGAP    ouders
        0      focuspersoon + partner
      -YGAP    kinderen (max 8)
    """
    XGAP  = 2.5   # afstand tussen knooppuntcentra horizontaal
    YGAP  = 2.2   # afstand tussen generatieniveaus
    BW    = 1.5   # boxbreedte  (data-eenheden)
    BH    = 0.62  # boxhoogte

    GKLEUR = {"M": "#4878CF", "F": "#E24A33", "X": "#95a5a6"}

    focus_rr = str(focus_rr)
    if focus_rr not in idx:
        return None

    foc = idx[focus_rr]
    nodes  = {}   # rr -> {x, y, naam, geb, geslacht, is_focus}
    shapes = []   # lijst van Plotly shape-dicts

    def _naam(r):
        return f"{r.get('voornaam', '?')} {r.get('familienaam', '?')}"

    def _geb(r):
        g = r.get("geboortedatum") or ""
        return str(g)[:10]

    def add_node(rr, x, y, is_focus=False):
        rr = str(rr)
        if rr not in idx:
            return False
        r = idx[rr]
        nodes[rr] = {
            "x": x, "y": y,
            "naam": _naam(r), "geb": _geb(r),
            "geslacht": r.get("geslacht", "X"),
            "is_focus": is_focus,
        }
        return True

    def hline(x0, y0, x1, y1, kleur="#aaaaaa"):
        shapes.append(dict(
            type="line", x0=x0, y0=y0, x1=x1, y1=y1,
            line=dict(color=kleur, width=1.5),
        ))

    # ── niveau 0: focuspersoon + partner ────────────────────────────────────
    add_node(focus_rr, 0.0, 0.0, is_focus=True)

    partner_rr  = str(foc.get("partner_rr") or "")
    has_partner = bool(partner_rr and partner_rr in idx)
    if has_partner:
        add_node(partner_rr, XGAP, 0.0)
        # koppelbeugel
        hline(BW / 2, 0.0, XGAP - BW / 2, 0.0)

    cx = XGAP / 2 if has_partner else 0.0   # middelpunt koppel

    # ── niveau +1: ouders ────────────────────────────────────────────────────
    vader_rr  = str(foc.get("vader_rr")  or "")
    moeder_rr = str(foc.get("moeder_rr") or "")
    has_vader  = bool(vader_rr  and vader_rr  in idx)
    has_moeder = bool(moeder_rr and moeder_rr in idx)

    # ouders staan 2*XGAP uiteen, gecentreerd boven cx
    vx = cx - XGAP
    mx = cx + XGAP

    if has_vader and has_moeder:
        add_node(vader_rr,  vx, YGAP)
        add_node(moeder_rr, mx, YGAP)
        hline(vx + BW / 2, YGAP, mx - BW / 2, YGAP)       # koppelbeugel ouders
        hline(cx, YGAP - BH / 2, cx, BH / 2)               # verticaal naar focus
    elif has_vader:
        add_node(vader_rr, cx, YGAP)
        hline(cx, YGAP - BH / 2, cx, BH / 2)
    elif has_moeder:
        add_node(moeder_rr, cx, YGAP)
        hline(cx, YGAP - BH / 2, cx, BH / 2)

    # ── niveau +2: grootouders ───────────────────────────────────────────────
    for par_rr, par_x, par_aanwezig in [
        (vader_rr,  vx, has_vader),
        (moeder_rr, mx, has_moeder),
    ]:
        if not par_aanwezig or par_rr not in idx:
            continue
        par    = idx[par_rr]
        gv_rr  = str(par.get("vader_rr")  or "")
        gm_rr  = str(par.get("moeder_rr") or "")
        has_gv = bool(gv_rr and gv_rr in idx)
        has_gm = bool(gm_rr and gm_rr in idx)
        gvx    = par_x - XGAP / 2
        gmx    = par_x + XGAP / 2

        if has_gv and has_gm:
            add_node(gv_rr, gvx, 2 * YGAP)
            add_node(gm_rr, gmx, 2 * YGAP)
            hline(gvx + BW / 2, 2 * YGAP, gmx - BW / 2, 2 * YGAP)
            hline(par_x, 2 * YGAP - BH / 2, par_x, YGAP + BH / 2)
        elif has_gv:
            add_node(gv_rr, par_x, 2 * YGAP)
            hline(par_x, 2 * YGAP - BH / 2, par_x, YGAP + BH / 2)
        elif has_gm:
            add_node(gm_rr, par_x, 2 * YGAP)
            hline(par_x, 2 * YGAP - BH / 2, par_x, YGAP + BH / 2)

    # ── niveau -1: kinderen (max 8) ──────────────────────────────────────────
    kinderen = foc.get("kinderen_rr") or []
    if not isinstance(kinderen, list):
        kinderen = []
    valid_kind = [str(k) for k in kinderen if str(k) in idx][:8]
    n_k = len(valid_kind)

    if n_k > 0:
        kind_xs = [cx + (i - (n_k - 1) / 2) * XGAP for i in range(n_k)]
        bar_y   = -YGAP / 2

        hline(cx, -BH / 2, cx, bar_y)                          # neer naar balk
        hline(kind_xs[0], bar_y, kind_xs[-1], bar_y)           # horizontale balk
        for i, kind_rr in enumerate(valid_kind):
            add_node(kind_rr, kind_xs[i], -YGAP)
            hline(kind_xs[i], bar_y, kind_xs[i], -YGAP + BH / 2)

        if len(kinderen) > 8:
            # "+ N meer" tekst naast de balk
            extra = len(kinderen) - 8
            shapes.append(dict(
                type="line", x0=kind_xs[-1] + XGAP / 2, y0=bar_y,
                x1=kind_xs[-1] + XGAP / 2, y1=bar_y,
                line=dict(color="rgba(0,0,0,0)", width=0),
            ))

    if not nodes:
        return None

    # ── Plotly figure ────────────────────────────────────────────────────────
    fig = go.Figure()

    # Verbindingslijnen via shapes
    for s in shapes:
        fig.add_shape(**s)

    # Knooppunten: box (shape) + naam (annotation)
    for rr, node in nodes.items():
        x, y = node["x"], node["y"]
        kleur = "#f39c12" if node["is_focus"] else GKLEUR.get(node["geslacht"], "#95a5a6")
        txtkleur = "#000" if node["is_focus"] else "#fff"

        fig.add_shape(
            type="rect",
            x0=x - BW / 2, y0=y - BH / 2,
            x1=x + BW / 2, y1=y + BH / 2,
            fillcolor=kleur,
            line=dict(color="white", width=1.5),
            layer="above",
        )
        fig.add_annotation(
            x=x, y=y + 0.1,
            text=f"<b>{node['naam'][:22]}</b>",
            showarrow=False,
            font=dict(size=9, color=txtkleur),
            xanchor="center", yanchor="middle",
            bgcolor="rgba(0,0,0,0)",
        )
        fig.add_annotation(
            x=x, y=y - 0.18,
            text=f"<span style='font-size:8px'>{node['geb']}</span>",
            showarrow=False,
            font=dict(size=8, color=txtkleur),
            xanchor="center", yanchor="middle",
            bgcolor="rgba(0,0,0,0)",
        )

    # Mededeling bij afgeknotte kinderenlijst
    if n_k > 0 and len(kinderen) > 8:
        extra = len(kinderen) - 8
        fig.add_annotation(
            x=kind_xs[-1] + XGAP * 0.6, y=-YGAP,
            text=f"<i>+ {extra} meer</i>",
            showarrow=False, font=dict(size=9, color="#666"),
            xanchor="left", yanchor="middle",
        )

    all_x = [n["x"] for n in nodes.values()]
    all_y = [n["y"] for n in nodes.values()]
    x_pad = BW * 2.0
    y_pad = BH * 2.5

    focus_naam = nodes.get(focus_rr, {}).get("naam", "")
    fig.update_layout(
        title=dict(text=f"Stamboom — {focus_naam}", font=dict(size=14)),
        height=max(420, int((max(all_y) - min(all_y) + 2.5) * 120)),
        margin=dict(l=20, r=20, t=50, b=20),
        plot_bgcolor="white",
        xaxis=dict(
            showgrid=False, zeroline=False, showticklabels=False,
            range=[min(all_x) - x_pad, max(all_x) + x_pad],
        ),
        yaxis=dict(
            showgrid=False, zeroline=False, showticklabels=False,
            range=[min(all_y) - y_pad, max(all_y) + y_pad],
        ),
    )
    return fig


# --------------------------------------------------------------------------- #
# Opstartdetectie
# --------------------------------------------------------------------------- #
beschikbare_registers = scan_registers(SAVE_DIR)


# --------------------------------------------------------------------------- #
# Sidebar
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.title("⚙️ Instellingen")

    if beschikbare_registers:
        opties  = [p["prefix"] for p in beschikbare_registers]
        labels  = [
            f"{p['prefix']}  ({p['opgeslagen'].strftime('%Y-%m-%d %H:%M')})"
            for p in beschikbare_registers
        ]
        keuze_idx = st.selectbox(
            "Register laden",
            range(len(opties)),
            format_func=lambda i: labels[i],
        )
        prefix = opties[keuze_idx]
    else:
        prefix = "metaworld"

    st.divider()
    toon_bis = st.toggle("Toon bisregister-sectie", value=True)


# --------------------------------------------------------------------------- #
# Data laden
# --------------------------------------------------------------------------- #
RR_PATH  = SAVE_DIR / f"{prefix}_rijksregister.json"
BIS_PATH = SAVE_DIR / f"{prefix}_bisregister.json"
FAM_PATH = SAVE_DIR / f"{prefix}_families.json"

if not (RR_PATH.exists() and BIS_PATH.exists()):
    st.error(
        f"Geen registerbestanden gevonden voor prefix **{prefix}**. "
        "Genereer eerst registers via de Scripts en sla ze op."
    )
    st.stop()

rr, bis = load_van_schijf(
    str(RR_PATH), str(BIS_PATH),
    RR_PATH.stat().st_mtime, BIS_PATH.stat().st_mtime,
)
data_ts = datetime.fromtimestamp(RR_PATH.stat().st_mtime).strftime("%Y-%m-%d %H:%M")

if not FAM_PATH.exists():
    st.warning(
        f"Geen familiesbestand gevonden voor prefix **{prefix}**. "
        "Familietab en stamboom zijn niet beschikbaar."
    )
    fam = pd.DataFrame()
    fam_bron = "ontbreekt"
else:
    fam = load_families(str(FAM_PATH), FAM_PATH.stat().st_mtime)
    fam_bron = "schijf"

rr_levend = rr[rr["overlijdensdatum"].isna()]


# --------------------------------------------------------------------------- #
# Sidebar – status
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.divider()
    st.success("📂 Geladen van schijf")
    st.caption(f"Opgeslagen: **{data_ts}**")
    st.caption(f"RR: **{len(rr):,}** · BIS: **{len(bis):,}** rijen")
    cfg_sidebar = lees_config()
    st.caption(f"Seed: **{cfg_sidebar['meta']['seed']}**")
    st.caption(f"Referentiedatum: **{cfg_sidebar['meta']['creation_date']}**")
    if fam_bron == "schijf":
        st.caption(f"Families: **{len(fam):,}** personen (💾)")


# --------------------------------------------------------------------------- #
# Paginatitel
# --------------------------------------------------------------------------- #
st.title("Fictief Belgisch Register — Demografisch overzicht")
st.caption(
    f"Rijksregister: **{len(rr):,}** · Bisregister: **{len(bis):,}** · "
    f"Databron: 📂 opgeslagen {data_ts} · Alle data is volledig fictief."
)

# --------------------------------------------------------------------------- #
# Tabs
# --------------------------------------------------------------------------- #
tab_dash, tab_fam, tab_kaart, tab_diensten, tab_cfg = st.tabs([
    "📊 Dashboard",
    "👨‍👩‍👧‍👦 Families",
    "🔍 Persoonskaart",
    "🌐 Diensten",
    "⚙️ Config aanpassen",
])


# =========================================================================== #
# TAB 1 – DASHBOARD
# =========================================================================== #
with tab_dash:

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Rijksregister",         f"{len(rr):,}")
    k2.metric("Bisregister",           f"{len(bis):,}")
    k3.metric("Gemid. leeftijd",       f"{rr_levend['leeftijd'].mean():.1f} jr")
    k4.metric("Vrouwelijk",            f"{(rr['geslacht']=='F').mean():.1%}")
    k5.metric("Buitenlandse geboorte", f"{(rr['geboorteland']!='België').mean():.1%}")

    st.divider()

    col_pyr, col_nat = st.columns([3, 2])

    with col_pyr:
        st.subheader("Bevolkingspiramide (levenden)")
        rr_lv  = leeftijdsbanden(rr_levend)
        bands  = [f"{i}–{i+4}" for i in range(0, 111, 5)]
        m_cnt  = rr_lv[rr_lv["geslacht"] == "M"]["band"].value_counts().reindex(bands, fill_value=0)
        f_cnt  = rr_lv[rr_lv["geslacht"] == "F"]["band"].value_counts().reindex(bands, fill_value=0)
        max_val = max(m_cnt.max(), f_cnt.max())

        fig_pyr = go.Figure()
        fig_pyr.add_trace(go.Bar(
            y=bands, x=-m_cnt.values, orientation="h", name="Man",
            marker_color=COLORS["M"],
            hovertemplate="%{customdata}<extra>Man</extra>",
            customdata=m_cnt.values,
        ))
        fig_pyr.add_trace(go.Bar(
            y=bands, x=f_cnt.values, orientation="h", name="Vrouw",
            marker_color=COLORS["F"],
            hovertemplate="%{x}<extra>Vrouw</extra>",
        ))
        fig_pyr.update_layout(
            barmode="relative", height=480,
            margin=dict(l=10, r=10, t=10, b=30),
            legend=dict(orientation="h", y=-0.05),
            xaxis=dict(
                tickvals=[-max_val, -max_val//2, 0, max_val//2, max_val],
                ticktext=[str(max_val), str(max_val//2), "0",
                          str(max_val//2), str(max_val)],
            ),
        )
        st.plotly_chart(fig_pyr, use_container_width=True)

    with col_nat:
        st.subheader("Nationaliteitsgroep")
        nat_cnt = rr["nationaliteit"].value_counts().reset_index()
        nat_cnt.columns = ["nationaliteit", "aantal"]
        fig_nat = px.pie(
            nat_cnt, values="aantal", names="nationaliteit",
            color_discrete_sequence=NAT_PALETTE, hole=0.35,
        )
        fig_nat.update_traces(textposition="inside", textinfo="percent+label")
        fig_nat.update_layout(
            height=480, margin=dict(l=10, r=10, t=10, b=10), showlegend=False,
        )
        st.plotly_chart(fig_nat, use_container_width=True)

    col_age, col_land = st.columns(2)

    with col_age:
        st.subheader("Leeftijdsverdeling naar geslacht")
        fig_age = go.Figure()
        for gsl, kleur, naam in [("M", COLORS["M"], "Man"), ("F", COLORS["F"], "Vrouw")]:
            cnt = (
                rr[rr["geslacht"] == gsl]["leeftijd"]
                .value_counts().sort_index().reset_index()
            )
            cnt.columns = ["leeftijd", "aantal"]
            fig_age.add_trace(go.Scatter(
                x=cnt["leeftijd"], y=cnt["aantal"],
                mode="lines", name=naam,
                line=dict(color=kleur, width=2),
            ))
        fig_age.update_layout(
            height=360,
            margin=dict(l=10, r=10, t=10, b=30),
            xaxis_title="Leeftijd", yaxis_title="Aantal",
            legend=dict(orientation="h", y=-0.12),
        )
        st.plotly_chart(fig_age, use_container_width=True)

    with col_land:
        st.subheader("Top-10 geboorteland")
        top_l = rr["geboorteland"].value_counts().head(10).reset_index()
        top_l.columns = ["land", "aantal"]
        fig_land = px.bar(
            top_l.sort_values("aantal"), x="aantal", y="land", orientation="h",
            color="aantal", color_continuous_scale="Teal", text="aantal",
        )
        fig_land.update_traces(textposition="outside")
        fig_land.update_layout(
            height=360, margin=dict(l=10, r=10, t=10, b=30),
            coloraxis_showscale=False, xaxis_title="Aantal", yaxis_title="",
        )
        st.plotly_chart(fig_land, use_container_width=True)

    st.subheader("Overlijdens")
    col_ov1, col_ov2, col_ov3 = st.columns(3)

    ov_df = rr[rr["overlijdensdatum"].notna()].copy()
    ov_df["overlijdensdatum"] = pd.to_datetime(ov_df["overlijdensdatum"])

    with col_ov1:
        fig_ov = go.Figure(go.Pie(
            labels=["Levend", "Overleden"],
            values=[rr["overlijdensdatum"].isna().sum(), len(ov_df)],
            marker_colors=[COLORS["accent"], COLORS["muted"]],
            hole=0.4, textinfo="percent+label",
        ))
        fig_ov.update_layout(
            height=280, margin=dict(l=10, r=10, t=30, b=10), title="Status",
        )
        st.plotly_chart(fig_ov, use_container_width=True)

    with col_ov2:
        per_jaar = (
            ov_df["overlijdensdatum"].dt.year
            .value_counts().sort_index().reset_index()
        )
        per_jaar.columns = ["jaar", "aantal"]
        fig_jaar = px.line(per_jaar, x="jaar", y="aantal", markers=True)
        fig_jaar.update_layout(
            height=280, margin=dict(l=10, r=10, t=30, b=10),
            title="Overlijdens per jaar",
            xaxis_title="", yaxis_title="Aantal",
        )
        st.plotly_chart(fig_jaar, use_container_width=True)

    with col_ov3:
        ov_lft = (ov_df["overlijdensdatum"] - ov_df["geboortedatum"]).dt.days // 365
        cnt_ov = ov_lft.dropna().astype(int).value_counts().sort_index().reset_index()
        cnt_ov.columns = ["leeftijd", "aantal"]
        fig_ovl = go.Figure(go.Scatter(
            x=cnt_ov["leeftijd"], y=cnt_ov["aantal"],
            mode="lines", fill="tozeroy",
            line=dict(color=COLORS["muted"], width=2),
        ))
        fig_ovl.update_layout(
            height=280, margin=dict(l=10, r=10, t=30, b=10),
            title="Leeftijd bij overlijden",
            xaxis_title="Leeftijd", yaxis_title="Aantal", showlegend=False,
        )
        st.plotly_chart(fig_ovl, use_container_width=True)

    if toon_bis:
        st.divider()
        st.header("Bisregister")

        b1, b2, b3, b4 = st.columns(4)
        n_bis_x = (bis["geslacht"] == "X").sum()
        b1.metric("Totaal BIS",            f"{len(bis):,}")
        b2.metric("Geslacht onbekend (X)", f"{n_bis_x/len(bis):.1%}")
        b3.metric("Gemid. leeftijd",       f"{bis['leeftijd'].mean():.1f} jr")
        b4.metric("In België geboren",     f"{(bis['geboorteland']=='België').mean():.1%}")

        col_b1, col_b2, col_b3 = st.columns(3)

        with col_b1:
            nat_bis = bis["nationaliteit"].value_counts().reset_index()
            nat_bis.columns = ["nationaliteit", "aantal"]
            fig_bn = px.bar(
                nat_bis, x="aantal", y="nationaliteit", orientation="h",
                color_discrete_sequence=["coral"], text="aantal", title="Nationaliteitsgroep",
            )
            fig_bn.update_traces(textposition="outside")
            fig_bn.update_layout(
                height=320, margin=dict(l=10, r=10, t=40, b=10),
                yaxis_title="", xaxis_title="Aantal",
            )
            st.plotly_chart(fig_bn, use_container_width=True)

        with col_b2:
            gsl_bis = bis["geslacht"].value_counts().reset_index()
            gsl_bis.columns = ["geslacht", "aantal"]
            fig_bg = px.pie(
                gsl_bis, values="aantal", names="geslacht",
                color="geslacht",
                color_discrete_map={"M": COLORS["M"], "F": COLORS["F"], "X": COLORS["muted"]},
                hole=0.35, title="Geslacht (X = onbekend)",
            )
            fig_bg.update_traces(textinfo="percent+label")
            fig_bg.update_layout(
                height=320, margin=dict(l=10, r=10, t=40, b=10), showlegend=False,
            )
            st.plotly_chart(fig_bg, use_container_width=True)

        with col_b3:
            top_bl = bis["geboorteland"].value_counts().head(8).reset_index()
            top_bl.columns = ["land", "aantal"]
            fig_bl = px.bar(
                top_bl.sort_values("aantal"), x="aantal", y="land", orientation="h",
                color="aantal", color_continuous_scale="Oranges",
                text="aantal", title="Geboorteland (top 8)",
            )
            fig_bl.update_traces(textposition="outside")
            fig_bl.update_layout(
                height=320, margin=dict(l=10, r=10, t=40, b=10),
                coloraxis_showscale=False, yaxis_title="", xaxis_title="Aantal",
            )
            st.plotly_chart(fig_bl, use_container_width=True)


# =========================================================================== #
# TAB 2 – FAMILIES
# =========================================================================== #
with tab_fam:
    st.header("Familiestructuur")
    bron_lbl = "📂 geladen van schijf" if fam_bron == "schijf" else "⚡ gegenereerd (nog niet opgeslagen)"
    st.caption(f"{len(fam):,} personen · {bron_lbl}")

    # ── KPI's ──────────────────────────────────────────────────────────────
    n_koppels      = int(fam["partner_rr"].notna().sum() // 2)
    n_met_kinderen = int((fam["n_kinderen"] > 0).sum())
    gem_kinderen   = fam.loc[fam["partner_rr"].notna(), "n_kinderen"].mean()
    n_overl_fam    = int(fam["overlijdensdatum"].notna().sum())

    f1, f2, f3, f4, f5 = st.columns(5)
    f1.metric("Totaal personen",    f"{len(fam):,}")
    f2.metric("Koppels",            f"{n_koppels:,}")
    f3.metric("Met kinderen",       f"{n_met_kinderen:,}")
    f4.metric("Gem. kinderen/koppel", f"{gem_kinderen:.1f}")
    f5.metric("Overledenen",        f"{n_overl_fam:,}")

    # ── Generatieverdeling ─────────────────────────────────────────────────
    st.divider()
    col_gen, col_staat = st.columns(2)

    with col_gen:
        st.subheader("Personen per generatie")
        gen_labels = {0: "Gen 0 – stamouders", 1: "Gen 1", 2: "Gen 2", 3: "Gen 3"}
        gen_cnt = (
            fam["generatie"].value_counts().sort_index().reset_index()
        )
        gen_cnt.columns = ["generatie", "aantal"]
        gen_cnt["label"] = gen_cnt["generatie"].map(gen_labels).fillna("Overig")
        fig_gen = px.bar(
            gen_cnt, x="label", y="aantal",
            color="aantal", color_continuous_scale="Blues", text="aantal",
        )
        fig_gen.update_traces(textposition="outside")
        fig_gen.update_layout(
            height=300, margin=dict(l=10, r=10, t=10, b=30),
            coloraxis_showscale=False, xaxis_title="", yaxis_title="Aantal",
        )
        st.plotly_chart(fig_gen, use_container_width=True)

    with col_staat:
        st.subheader("Burgerlijke staat")
        staat_cnt = fam["burgerlijke_staat"].value_counts().reset_index()
        staat_cnt.columns = ["staat", "aantal"]
        fig_staat = px.pie(
            staat_cnt, values="aantal", names="staat",
            color_discrete_sequence=NAT_PALETTE, hole=0.35,
        )
        fig_staat.update_traces(textposition="inside", textinfo="percent+label")
        fig_staat.update_layout(
            height=300, margin=dict(l=10, r=10, t=10, b=10), showlegend=False,
        )
        st.plotly_chart(fig_staat, use_container_width=True)

    # ── Overzichtstabellen ─────────────────────────────────────────────────
    st.divider()
    st.subheader("Overzichtstabellen")
    st.caption(
        "De familiedataset is een apart gegenereerde dataset. "
        "De nummers in de kolom **nummer** zijn interne identificatoren van de familiedataset "
        "en staan niet noodzakelijk in het rijksregister. "
        "Via de **Persoonskaart**-tab zijn ze wel opzoekbaar."
    )

    _DISP_COLS = ["rijksregisternummer", "voornaam", "familienaam", "geslacht",
                  "leeftijd", "burgerlijke_staat", "generatie", "adres_gemeente"]

    def _tabel(df: pd.DataFrame, cols: list[str], max_rows: int = 500) -> pd.DataFrame:
        aanwezig = [c for c in cols if c in df.columns]
        result = df[aanwezig].head(max_rows).reset_index(drop=True)
        return result.rename(columns={"rijksregisternummer": "nummer"})

    tbl1, tbl2, tbl3, tbl4 = st.tabs([
        "🌳 Zonder ouders",
        "🚫 Kinderloos",
        "💔 Alleenstaanden",
        "👶 Meeste kinderen",
    ])

    with tbl1:
        st.markdown("**Personen zonder ouders in het systeem** (stamouders of wezen)")
        geen_ouders = fam[fam["vader_rr"].isna() & fam["moeder_rr"].isna()]
        st.metric("Aantal", f"{len(geen_ouders):,}")
        gen_verd = geen_ouders["generatie"].value_counts().sort_index().to_dict()
        st.caption(
            "  ·  ".join(f"Generatie {g}: {v}" for g, v in gen_verd.items())
        )
        st.dataframe(
            _tabel(geen_ouders, _DISP_COLS + ["partner_rr", "n_kinderen"]),
            use_container_width=True, hide_index=True,
        )

    with tbl2:
        st.markdown("**Volwassenen (≥ 18 jaar) zonder kinderen**")
        kinderloos = fam[(fam["n_kinderen"] == 0) & (fam["leeftijd"] >= 18)]
        st.metric("Aantal", f"{len(kinderloos):,}")
        col_a, col_b = st.columns(2)
        with col_a:
            staat_kl = kinderloos["burgerlijke_staat"].value_counts().reset_index()
            staat_kl.columns = ["staat", "aantal"]
            fig_kl = px.bar(staat_kl, x="staat", y="aantal",
                            color_discrete_sequence=["#4878CF"], text="aantal")
            fig_kl.update_traces(textposition="outside")
            fig_kl.update_layout(height=250, margin=dict(l=5, r=5, t=5, b=30),
                                  xaxis_title="", yaxis_title="")
            st.plotly_chart(fig_kl, use_container_width=True)
        with col_b:
            gen_kl = kinderloos["generatie"].value_counts().sort_index().reset_index()
            gen_kl.columns = ["generatie", "aantal"]
            fig_gkl = px.bar(gen_kl, x="generatie", y="aantal",
                             color_discrete_sequence=["#E24A33"], text="aantal")
            fig_gkl.update_traces(textposition="outside")
            fig_gkl.update_layout(height=250, margin=dict(l=5, r=5, t=5, b=30),
                                   xaxis_title="Generatie", yaxis_title="")
            st.plotly_chart(fig_gkl, use_container_width=True)
        st.dataframe(
            _tabel(kinderloos, _DISP_COLS),
            use_container_width=True, hide_index=True,
        )

    with tbl3:
        st.markdown("**Alleenstaanden ≥ 18 jaar (geen partner)**")
        alleenst = fam[(fam["partner_rr"].isna()) & (fam["leeftijd"] >= 18)]
        st.metric("Aantal", f"{len(alleenst):,}")
        staat_as = alleenst["burgerlijke_staat"].value_counts().reset_index()
        staat_as.columns = ["staat", "aantal"]
        fig_as = px.bar(
            staat_as, x="staat", y="aantal",
            color_discrete_sequence=["#2ecc71"], text="aantal",
        )
        fig_as.update_traces(textposition="outside")
        fig_as.update_layout(
            height=250, margin=dict(l=5, r=5, t=5, b=30),
            xaxis_title="Burgerlijke staat", yaxis_title="Aantal",
        )
        st.plotly_chart(fig_as, use_container_width=True)
        st.dataframe(
            _tabel(alleenst, _DISP_COLS),
            use_container_width=True, hide_index=True,
        )

    with tbl4:
        st.markdown("**Koppels gesorteerd op aantal kinderen (top 50)**")
        koppels_df = (
            fam[fam["partner_rr"].notna() & (fam["geslacht"] == "M")]
            .sort_values("n_kinderen", ascending=False)
            .head(50)
        )
        st.dataframe(
            _tabel(koppels_df, ["rijksregisternummer", "voornaam", "familienaam",
                                 "leeftijd", "generatie", "n_kinderen", "adres_gemeente"]),
            use_container_width=True, hide_index=True,
        )

    # ── Distributie kinderen per koppel ────────────────────────────────────
    with st.expander("Verdeling aantal kinderen per koppel"):
        koppel_kinden = fam[fam["partner_rr"].notna()]["n_kinderen"].value_counts().sort_index()
        fig_kk = px.bar(
            x=koppel_kinden.index.astype(str),
            y=koppel_kinden.values,
            labels={"x": "Aantal kinderen", "y": "Aantal koppels"},
            color_discrete_sequence=["#4878CF"],
            text=koppel_kinden.values,
        )
        fig_kk.update_traces(textposition="outside")
        fig_kk.update_layout(
            height=300, margin=dict(l=10, r=10, t=10, b=30),
        )
        st.plotly_chart(fig_kk, use_container_width=True)


# =========================================================================== #
# TAB 3 – PERSOONSKAART
# =========================================================================== #
with tab_kaart:
    st.header("Persoonskaart")

    zoek_modus = st.radio(
        "Zoeken op",
        ["Op nummer", "Op kenmerken"],
        horizontal=True,
        label_visibility="collapsed",
    )

    zoek_nr = ""

    if zoek_modus == "Op kenmerken":
        # Sessie-staat initialiseren
        if "zoek_res" not in st.session_state:
            st.session_state.zoek_res = None

        # ── Gecombineerde zoekdataframe bouwen ───────────────────────────────
        stukken = []
        for _df, _nr_col, _reg_label in [
            (fam,  "rijksregisternummer", "Families"),
            (rr,   "rijksregisternummer", "Rijksregister"),
            (bis,  "bisnummer",           "Bisregister"),
        ]:
            if _df.empty:
                continue
            _d = _df.copy()
            _d["_register"] = _reg_label
            _d["_nummer"]   = _d[_nr_col].astype(str)
            stukken.append(_d)
        zoek_df = pd.concat(stukken, ignore_index=True) if stukken else pd.DataFrame()

        # ── Filterformulier ──────────────────────────────────────────────────
        with st.form("zoek_form"):
            c1, c2, c3 = st.columns(3)

            voornaam_f    = c1.text_input("Voornaam (bevat)")
            familienaam_f = c2.text_input("Familienaam (bevat)")
            geslacht_f    = c3.selectbox("Geslacht", ["(alle)", "M", "F", "X"])

            c4, c5, c6 = st.columns(3)
            register_f    = c4.selectbox("Register", ["(alle)", "Families", "Rijksregister", "Bisregister"])
            leeftijd_min  = c5.number_input("Leeftijd van", min_value=0, max_value=150, value=0, step=1)
            leeftijd_max  = c6.number_input("Leeftijd tot", min_value=0, max_value=150, value=150, step=1)

            c7, c8, c9 = st.columns(3)
            nat_opties   = ["(alle)"] + sorted(zoek_df["nationaliteit"].dropna().unique().tolist()) if not zoek_df.empty and "nationaliteit" in zoek_df.columns else ["(alle)"]
            nationaliteit_f = c7.selectbox("Nationaliteit", nat_opties)
            gem_opties   = ["(alle)"] + sorted(zoek_df["adres_gemeente"].dropna().unique().tolist()) if not zoek_df.empty and "adres_gemeente" in zoek_df.columns else ["(alle)"]
            gemeente_f   = c8.selectbox("Gemeente", gem_opties)
            staat_opties = ["(alle)"] + sorted(zoek_df["burgerlijke_staat"].dropna().unique().tolist()) if not zoek_df.empty and "burgerlijke_staat" in zoek_df.columns else ["(alle)"]
            staat_f      = c9.selectbox("Burgerlijke staat", staat_opties)

            c10, c11, c12 = st.columns(3)
            heeft_kinderen_f = c10.selectbox("Heeft kinderen", ["(alle)", "Ja", "Nee"])
            ouders_f         = c11.selectbox("Ouders in systeem", ["(alle)", "Ja", "Nee"])
            heeft_partner_f  = c12.selectbox("Heeft partner", ["(alle)", "Ja", "Nee"])

            zoek_btn = st.form_submit_button("Zoeken", type="primary")

        # ── Filteren + opslaan in sessie-staat ───────────────────────────────
        if zoek_btn and not zoek_df.empty:
            res = zoek_df.copy()

            if voornaam_f.strip():
                res = res[res["voornaam"].astype(str).str.contains(voornaam_f.strip(), case=False, na=False)]
            if familienaam_f.strip():
                res = res[res["familienaam"].astype(str).str.contains(familienaam_f.strip(), case=False, na=False)]
            if geslacht_f != "(alle)":
                res = res[res["geslacht"] == geslacht_f]
            if register_f != "(alle)":
                res = res[res["_register"] == register_f]
            if "leeftijd" in res.columns:
                res = res[res["leeftijd"].between(leeftijd_min, leeftijd_max, inclusive="both")]
            if nationaliteit_f != "(alle)" and "nationaliteit" in res.columns:
                res = res[res["nationaliteit"] == nationaliteit_f]
            if gemeente_f != "(alle)" and "adres_gemeente" in res.columns:
                res = res[res["adres_gemeente"] == gemeente_f]
            if staat_f != "(alle)" and "burgerlijke_staat" in res.columns:
                res = res[res["burgerlijke_staat"] == staat_f]
            if heeft_kinderen_f != "(alle)" and "n_kinderen" in res.columns:
                if heeft_kinderen_f == "Ja":
                    res = res[res["n_kinderen"].fillna(0) > 0]
                else:
                    res = res[res["n_kinderen"].fillna(0) == 0]
            if ouders_f != "(alle)":
                heeft_vader  = res["vader_rr"].notna()  if "vader_rr"  in res.columns else pd.Series(False, index=res.index)
                heeft_moeder = res["moeder_rr"].notna() if "moeder_rr" in res.columns else pd.Series(False, index=res.index)
                heeft_ouders = heeft_vader | heeft_moeder
                res = res[heeft_ouders] if ouders_f == "Ja" else res[~heeft_ouders]
            if heeft_partner_f != "(alle)" and "partner_rr" in res.columns:
                if heeft_partner_f == "Ja":
                    res = res[res["partner_rr"].notna()]
                else:
                    res = res[res["partner_rr"].isna()]

            st.session_state.zoek_res = res.reset_index(drop=True) if not res.empty else None
            if res.empty:
                st.info("Geen resultaten voor de huidige filters.")

        # ── Resultaten tonen (persistent over reruns) ────────────────────────
        if st.session_state.zoek_res is not None:
            res = st.session_state.zoek_res
            st.caption(f"{len(res):,} resultaten")

            toon_cols = [c for c in ["_nummer", "voornaam", "familienaam", "geslacht",
                                      "leeftijd", "nationaliteit", "burgerlijke_staat",
                                      "adres_gemeente", "n_kinderen", "_register"] if c in res.columns]
            toon_df = res[toon_cols].head(500).rename(columns={"_nummer": "nummer", "_register": "register"})
            st.dataframe(toon_df, use_container_width=True, hide_index=True)

            nummers = res["_nummer"].head(500).tolist()
            keuze_opties = ["— kies een persoon —"] + nummers
            gekozen = st.selectbox("Selecteer persoon voor persoonskaart", keuze_opties)
            if gekozen != "— kies een persoon —":
                zoek_nr = gekozen

    else:
        st.caption("Geef een rijksregisternummer of bisnummer in om de volledige fiche en stamboom te zien.")
        zoek_nr = st.text_input(
            "Nummer",
            placeholder="bijv.  85.04.03-997.05",
            label_visibility="collapsed",
        )

    if zoek_nr.strip():
        persoon, bron = _zoek_persoon(zoek_nr.strip(), fam, rr, bis)

        if persoon is None:
            st.error(f"Nummer **{zoek_nr.strip()}** niet gevonden in registers of families.")
        else:
            st.success(f"Gevonden in: **{bron}**")

            # ── Persoonsgegevens ─────────────────────────────────────────────
            st.subheader("Persoonsgegevens")

            # badge-helper
            def badge(txt, kleur):
                return f"<span style='background:{kleur};color:white;padding:2px 8px;border-radius:4px;font-size:0.85em'>{txt}</span>"

            gsl       = persoon.get("geslacht", "")
            gsl_label = {"M": "Man", "F": "Vrouw", "X": "Onbekend"}.get(gsl, gsl)
            gsl_kleur = {"M": "#4878CF", "F": "#E24A33"}.get(gsl, "#95a5a6")

            ovl = persoon.get("overlijdensdatum")
            leven_badge = (
                badge("Nog in leven", "#27ae60")
                if not ovl
                else badge(f"Overleden {ovl}", "#c0392b")
            )

            col_l, col_r = st.columns([2, 1])
            with col_l:
                naam_vol = f"{persoon.get('voornaam', '')} {persoon.get('familienaam', '')}"
                st.markdown(f"## {naam_vol}")
                st.markdown(
                    f"{badge(gsl_label, gsl_kleur)}  &nbsp; {leven_badge}",
                    unsafe_allow_html=True,
                )

            with col_r:
                id_veld = "rijksregisternummer" if "rijksregisternummer" in persoon else "bisnummer"
                st.code(persoon.get(id_veld, ""), language=None)

            LABELS = {
                "geboortedatum":   "Geboortedatum",
                "geboorteplaats":  "Geboorteplaats",
                "geboorteland":    "Geboorteland",
                "nationaliteit":   "Nationaliteit",
                "burgerlijke_staat": "Burgerlijke staat",
                "generatie":       "Generatie",
            }

            tabel_rijen = []
            for veld, label in LABELS.items():
                val = persoon.get(veld)
                if val is not None:
                    tabel_rijen.append({"Veld": label, "Waarde": str(val)})

            if tabel_rijen:
                st.table(pd.DataFrame(tabel_rijen).set_index("Veld"))

            # Adres
            if persoon.get("adres_straat"):
                st.markdown("**Woonadres**")
                bus_deel = f" bus {persoon['adres_bus']}" if persoon.get("adres_bus") else ""
                adres_rijen = [
                    {"": "Straat",           "Waarde": f"{persoon['adres_straat']} {persoon.get('adres_nr', '')}{bus_deel}"},
                    {"": "Gemeente",         "Waarde": f"{persoon.get('adres_postcode', '')} {persoon.get('adres_gemeente', '')}"},
                    {"": "Provincie/Gewest", "Waarde": f"{persoon.get('adres_provincie', '')} · {persoon.get('adres_gewest', '')}"},
                ]
                st.table(pd.DataFrame(adres_rijen).set_index(""))

            # ── Stamboom ─────────────────────────────────────────────────────
            st.divider()
            st.subheader("Stamboom")

            if bron == "Families":
                fam_idx = _bouw_fam_idx(fam)
                focus_rr_kaart = str(persoon.get("rijksregisternummer", ""))

                sub_tabel, sub_tekening = st.tabs(["📋 Tabel", "🌳 Tekening"])

                with sub_tabel:
                    fam_tbl = _familie_tabel(persoon, fam_idx)
                    if fam_tbl.empty:
                        st.info("Geen verwanten gevonden in het systeem.")
                    else:
                        st.dataframe(fam_tbl, use_container_width=True, hide_index=True)

                with sub_tekening:
                    fig_boom = _teken_stamboom(focus_rr_kaart, fam_idx)
                    if fig_boom:
                        st.plotly_chart(fig_boom, use_container_width=True)
                    else:
                        st.info("Stamboom kon niet worden opgebouwd.")

                # Snel overzicht relaties
                with st.expander("Relatieoverzicht"):
                    rel_cols = st.columns(4)
                    rel_cols[0].metric("Vader",    "✓" if persoon.get("vader_rr")   else "—")
                    rel_cols[1].metric("Moeder",   "✓" if persoon.get("moeder_rr")  else "—")
                    rel_cols[2].metric("Partner",  "✓" if persoon.get("partner_rr") else "—")
                    kinderen_count = len(persoon.get("kinderen_rr") or [])
                    rel_cols[3].metric("Kinderen", str(kinderen_count))
            else:
                st.info(
                    f"Persoon gevonden in **{bron}**, maar stamboomgegevens zijn alleen beschikbaar "
                    "voor personen in de familiedataset. Laad of genereer families om de stamboom te zien."
                )
    elif zoek_modus == "Op nummer":
        st.info("Voer een nummer in om te zoeken.")


# =========================================================================== #
# TAB 4 – DIENSTEN
# =========================================================================== #
with tab_diensten:
    st.header("Webdiensten")
    st.caption(
        "Start de Flask-diensten en open ze in de browser. "
        "Zorg dat de registers zijn opgeslagen voordat je de diensten gebruikt."
    )

    DIENSTEN = [
        {
            "naam":    "Authenticatiedienst (FAS/CSAM)",
            "script":  "auth_service.py",
            "poort":   5001,
            "url":     "http://localhost:5001",
            "omschr":  "Simuleert de federale authenticatiedienst. Vereist opgeslagen registers.",
        },
        {
            "naam":    "Datadienst (Rijksregister)",
            "script":  "data_service.py",
            "poort":   5002,
            "url":     "http://localhost:5002",
            "omschr":  "Toont persoonsfiches na inloggen via de authenticatiedienst.",
        },
    ]

    for svc in DIENSTEN:
        actief = _port_actief(svc["poort"])

        with st.container(border=True):
            h_col, s_col, b_col = st.columns([4, 2, 2])

            with h_col:
                st.markdown(f"**{svc['naam']}**")
                st.caption(f"`Scripts/{svc['script']}`  ·  poort **{svc['poort']}**")
                st.caption(svc["omschr"])

            with s_col:
                if actief:
                    st.success("✅ Actief")
                else:
                    st.error("⛔ Niet actief")

            with b_col:
                if actief:
                    st.link_button(
                        f"🌐 Open pagina",
                        url=svc["url"],
                        use_container_width=True,
                        type="primary",
                    )
                else:
                    if st.button(
                        "▶️ Starten",
                        key=f"start_{svc['poort']}",
                        use_container_width=True,
                    ):
                        script_pad = SCRIPTS_DIR / svc["script"]
                        if sys.platform == "win32":
                            subprocess.Popen(
                                ["python", str(script_pad)],
                                creationflags=subprocess.CREATE_NEW_CONSOLE,
                            )
                        else:
                            subprocess.Popen(
                                ["python", str(script_pad)],
                                start_new_session=True,
                            )
                        st.info("Service gestart in nieuw venster. Vernieuw de status.")

    st.divider()
    if st.button("🔄 Status vernieuwen", use_container_width=False):
        st.rerun()

    # Registers-status
    with st.expander("Beschikbare registerbestanden"):
        bestanden = sorted(SAVE_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if bestanden:
            st.dataframe(
                pd.DataFrame([{
                    "Bestand":    p.name,
                    "Grootte":    f"{p.stat().st_size / 1024:.0f} KB",
                    "Opgeslagen": datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
                } for p in bestanden]),
                use_container_width=True, hide_index=True,
            )
        else:
            st.warning("Geen registerbestanden gevonden. Genereer eerst registers via het notebook en sla ze op in de map 'Generated Data'.")


# =========================================================================== #
# TAB 5 – CONFIG AANPASSEN
# =========================================================================== #
with tab_cfg:
    st.header("Config aanpassen")
    st.caption(f"Bestand: `{CONFIG_PATH}`")

    cfg = lees_config()

    st.subheader("Algemeen")
    c1, c2 = st.columns(2)
    new_seed = c1.number_input(
        "Seed", value=int(cfg["meta"]["seed"]), step=1, min_value=0,
        help="Verandering van seed genereert een andere fictieve bevolking.",
    )
    new_date = c2.date_input(
        "Referentiedatum",
        value=pd.Timestamp(cfg["meta"]["creation_date"]).date(),
    )

    st.subheader("Generatieparameters")
    st.caption("Aantal records dat aangemaakt wordt bij uitvoering van de generatiescripts/notebook.")
    gc1, gc2, gc3, gc4 = st.columns(4)
    gen_counts = cfg["generation"]["counts"]
    new_n_rr      = gc1.number_input("Rijksregister – aanmaken",
                                      value=int(gen_counts["rijksregister"]),
                                      step=1_000, min_value=100)
    new_n_bis     = gc2.number_input("Bisregister – aanmaken",
                                      value=int(gen_counts["bisregister"]),
                                      step=100, min_value=10)
    new_n_stam    = gc3.number_input("Stamfamilies (gen 0)",
                                      value=int(gen_counts["stamfamilies"]),
                                      step=10, min_value=10)
    new_n_singles = gc4.number_input("Stamsingles (gen 0)",
                                      value=int(gen_counts["stamsingles"]),
                                      step=5, min_value=5)

    st.subheader("Bevolking")
    c1, c2, c3, c4 = st.columns(4)
    new_rr_total  = c1.number_input("Rijksregister – totaal",
                                     value=int(cfg["population"]["rijksregister"]["total"]),
                                     step=100_000)
    new_bis_total = c2.number_input("Bisregister – totaal",
                                     value=int(cfg["population"]["bisregister"]["total"]),
                                     step=10_000)
    new_man_pct   = c3.slider("Aandeel man (%)", 40.0, 60.0,
                               round(cfg["demographics"]["gender_ratio"]["male"] * 100, 1),
                               step=0.1, format="%.1f")
    new_deceased  = c4.slider("Overlijdens-fractie (%)", 0.0, 5.0,
                               round(cfg["generation"]["deceased_fraction"] * 100, 2),
                               step=0.01, format="%.2f")

    st.subheader("Nationaliteitsgroepen rijksregister")
    st.caption("Gewichten worden automatisch genormaliseerd bij opslaan.")
    nat_cfg  = cfg["demographics"]["nationality_groups"]
    nat_keys = [k for k in nat_cfg if k != "comment"]
    nat_df   = pd.DataFrame({
        "Nationaliteitsgroep": nat_keys,
        "Gewicht (%)": [round(nat_cfg[k] * 100, 2) for k in nat_keys],
    })
    edited_nat = st.data_editor(
        nat_df, use_container_width=True, hide_index=True,
        column_config={
            "Nationaliteitsgroep": st.column_config.TextColumn(disabled=True),
            "Gewicht (%)": st.column_config.NumberColumn(
                min_value=0.0, max_value=100.0, step=0.1, format="%.2f",
            ),
        },
    )
    totaal_pct = edited_nat["Gewicht (%)"].sum()
    if abs(totaal_pct - 100) > 0.1:
        st.warning(f"Gewichten tellen op tot **{totaal_pct:.2f}%** — worden genormaliseerd.")
    else:
        st.success(f"Gewichten tellen op tot **{totaal_pct:.2f}%** ✓")

    with st.expander("Leeftijdsverdeling (banden) — enkel via config.json"):
        st.dataframe(
            pd.DataFrame(cfg["demographics"]["age_distribution"]["bands"]),
            use_container_width=True, hide_index=True,
        )
    with st.expander("Sterftetafel — enkel via config.json"):
        st.dataframe(
            pd.DataFrame(cfg["demographics"]["mortality"]["life_table"]),
            use_container_width=True, hide_index=True,
        )

    st.divider()
    if st.button("💾 Sla config op", type="primary"):
        cfg["meta"]["seed"]                              = int(new_seed)
        cfg["meta"]["creation_date"]                     = str(new_date)
        cfg["population"]["rijksregister"]["total"]      = int(new_rr_total)
        cfg["population"]["bisregister"]["total"]        = int(new_bis_total)
        cfg["demographics"]["gender_ratio"]["male"]      = round(new_man_pct / 100, 4)
        cfg["demographics"]["gender_ratio"]["female"]    = round(1 - new_man_pct / 100, 4)
        cfg["generation"]["deceased_fraction"]           = round(new_deceased / 100, 4)
        cfg["generation"]["counts"]["rijksregister"]     = int(new_n_rr)
        cfg["generation"]["counts"]["bisregister"]       = int(new_n_bis)
        cfg["generation"]["counts"]["stamfamilies"]      = int(new_n_stam)
        cfg["generation"]["counts"]["stamsingles"]       = int(new_n_singles)
        norm = edited_nat["Gewicht (%)"].sum()
        for _, row in edited_nat.iterrows():
            cfg["demographics"]["nationality_groups"][row["Nationaliteitsgroep"]] = round(
                row["Gewicht (%)"] / norm, 6
            )
        schrijf_config(cfg)
        st.cache_data.clear()
        st.success("Config opgeslagen. Voer het notebook uit om registers met de nieuwe parameters aan te maken.")
        st.rerun()

