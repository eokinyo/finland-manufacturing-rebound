"""Download the official data and build the three charts for the article
"Factories are taking orders again. Jobs have not caught up."

Usage:
    python make_charts.py            # download fresh data, then build CSV and charts
    python make_charts.py --offline  # rebuild from the raw files already in data/raw

Outputs:
    data/raw/*.json              raw API responses, saved verbatim
    data/tidy_series.csv         one row per series and month
    data/article_numbers.csv     every number used in the article, with unit and period
    charts/*.png, charts/*.webp  the three charts
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "raw"
TIDY_CSV = ROOT / "data" / "tidy_series.csv"
NUMBERS_CSV = ROOT / "data" / "article_numbers.csv"
CHARTS = ROOT / "charts"

CHART_START = "2024-08"   # charts 1 and 2
EU_START = "2025-01"      # chart 3

STATFI_BASE = "https://pxdata.stat.fi/PxWeb/api/v1/en/StatFin"
EUROSTAT_BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"

# Internal API identifiers live only here. Published outputs use plain names.
DOWNLOADS = {
    "statistics_finland_new_orders_manufacturing": {
        "kind": "pxweb",
        "url": f"{STATFI_BASE}/teul/14mi.px",
        "query": [
            {"code": "toimiala_17_20220818", "selection": {"filter": "item", "values": ["C", "24-30", "17", "20-21"]}},
            {"code": "contentscode", "selection": {"filter": "item", "values": ["teul-muutosprosentti", "teul-Alkuperainen"]}},
        ],
    },
    "statistics_finland_turnover_industry": {
        "kind": "pxweb",
        "url": f"{STATFI_BASE}/tlv/14ms.px",
        "query": [
            {"code": "nace_8_20180101", "selection": {"filter": "item", "values": ["BTD"]}},
            {"code": "luokkaryhma_2_20180301", "selection": {"filter": "item", "values": ["lv"]}},
            {"code": "contentscode", "selection": {"filter": "item", "values": ["tlv-tpk_muutos", "tlv-kausit_kkmuutos"]}},
        ],
    },
    "statistics_finland_industrial_output_volume": {
        "kind": "pxweb",
        "url": f"{STATFI_BASE}/ttvi/14mh.px",
        "query": [
            {"code": "toimiala_78_20180201", "selection": {"filter": "item", "values": ["BTD"]}},
            {"code": "contentscode", "selection": {"filter": "item", "values": ["ttvi-tpk_muutos", "ttvi-kausit_kkmuutos"]}},
        ],
    },
    "eurostat_industrial_production": {
        "kind": "eurostat",
        "url": f"{EUROSTAT_BASE}/sts_inpr_m",
        "params": [
            ("format", "JSON"), ("lang", "EN"), ("nace_r2", "B-D"), ("s_adj", "CA"),
            ("unit", "PCH_SM"), ("geo", "FI"), ("geo", "EA21"), ("sinceTimePeriod", "2024-01"),
        ],
    },
}

# Plain names for every internal code that reaches the tidy data.
PLAIN = {
    "C": "Manufacturing total", "24-30": "Metal industry",
    "17": "Paper and paper products", "20-21": "Chemical industry",
    "BTD": "Total industry",
    "teul-muutosprosentti": ("year_on_year_pct", "original index"),
    "teul-Alkuperainen": ("index_2021_100", "original index"),
    "tlv-tpk_muutos": ("year_on_year_pct", "working day adjusted"),
    "tlv-kausit_kkmuutos": ("month_on_month_pct", "seasonally adjusted"),
    "ttvi-tpk_muutos": ("year_on_year_pct", "working day adjusted"),
    "ttvi-kausit_kkmuutos": ("month_on_month_pct", "seasonally adjusted"),
    "FI": "Finland", "EA21": "Euro area",
}
SERIES_NAME = {
    "statistics_finland_new_orders_manufacturing": "New orders in manufacturing (value)",
    "statistics_finland_turnover_industry": "Turnover in industry",
    "statistics_finland_industrial_output_volume": "Industrial output volume",
    "eurostat_industrial_production": "Industrial production volume",
}
SOURCE_NAME = {
    "statistics_finland_new_orders_manufacturing": "Statistics Finland",
    "statistics_finland_turnover_industry": "Statistics Finland",
    "statistics_finland_industrial_output_volume": "Statistics Finland",
    "eurostat_industrial_production": "Eurostat",
}


# ---------------------------------------------------------------- download
def download(name: str, spec: dict) -> Path:
    path = RAW / f"{name}.json"
    if spec["kind"] == "pxweb":
        body = {"query": spec["query"], "response": {"format": "json-stat2"}}
        r = requests.post(spec["url"], json=body, timeout=60)
    else:
        r = requests.get(spec["url"], params=spec["params"], timeout=60)
    r.raise_for_status()
    data = r.json()
    if "value" not in data:
        raise RuntimeError(f"{name}: response has no values")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


# ---------------------------------------------------------------- parse
def jsonstat_to_frame(data: dict) -> pd.DataFrame:
    """Flatten a JSON-stat 2.0 dataset (both APIs return this format)."""
    ids, sizes = data["id"], data["size"]
    cats = []
    for dim in ids:
        index = data["dimension"][dim]["category"]["index"]
        if isinstance(index, list):
            order = index
        else:
            order = sorted(index, key=index.get)
        cats.append(order)
    values = data["value"]
    if isinstance(values, list):
        values = {str(i): v for i, v in enumerate(values)}
    rows = []
    for key, val in values.items():
        if val is None:
            continue
        pos, rem = [], int(key)
        for size in reversed(sizes):
            pos.append(rem % size)
            rem //= size
        pos.reverse()
        rows.append({dim: cats[i][p] for i, (dim, p) in enumerate(zip(ids, pos))} | {"value": float(val)})
    return pd.DataFrame(rows)


def tidy_one(name: str, data: dict) -> pd.DataFrame:
    df = jsonstat_to_frame(data)
    out = pd.DataFrame()
    if name == "eurostat_industrial_production":
        out["period"] = df["time"]
        out["geo"] = df["geo"].map(PLAIN)
        out["breakdown"] = "Total industry"
        out["measure"] = "year_on_year_pct"
        out["adjustment"] = "calendar adjusted"
    else:
        time_col = "timeperiod_m"
        ind_col = [c for c in df.columns if c.startswith(("toimiala", "nace"))][0]
        out["period"] = df[time_col].str.replace("M", "-", regex=False)
        out["geo"] = "Finland"
        out["breakdown"] = df[ind_col].map(PLAIN)
        out["measure"] = df["contentscode"].map(lambda c: PLAIN[c][0])
        out["adjustment"] = df["contentscode"].map(lambda c: PLAIN[c][1])
    out["series"] = SERIES_NAME[name]
    out["source"] = SOURCE_NAME[name]
    out["value"] = df["value"].values
    if out.isna().any().any():
        raise ValueError(f"{name}: unmapped code in tidy data")
    return out[["source", "series", "geo", "breakdown", "measure", "adjustment", "period", "value"]]


def build_tidy() -> pd.DataFrame:
    frames = []
    for name in DOWNLOADS:
        data = json.loads((RAW / f"{name}.json").read_text(encoding="utf-8"))
        frames.append(tidy_one(name, data))
    tidy = pd.concat(frames, ignore_index=True)
    tidy = tidy.sort_values(["source", "series", "geo", "breakdown", "measure", "period"]).reset_index(drop=True)
    return tidy


def pick(tidy, series, breakdown=None, measure="year_on_year_pct", geo="Finland", start=None):
    s = tidy[(tidy.series == series) & (tidy.measure == measure) & (tidy.geo == geo)]
    if breakdown:
        s = s[s.breakdown == breakdown]
    if start:
        s = s[s.period >= start]
    return s.set_index("period")["value"].sort_index()


# ---------------------------------------------------------------- charts
def style():
    import matplotlib as mpl
    mpl.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 11, "axes.spines.top": False,
        "axes.spines.right": False, "axes.spines.left": False, "axes.grid": True,
        "axes.grid.axis": "y", "grid.color": "#dddddd", "grid.linewidth": 0.8,
        "axes.edgecolor": "#888888", "xtick.color": "#444444", "ytick.color": "#444444",
        "legend.frameon": False,
    })


COLORS = {"dark": "#1f3b57", "accent": "#d1495b", "teal": "#2a9d8f", "gold": "#e9a03b", "grey": "#8d99ae"}


def month_labels(periods):
    import calendar
    labels = []
    for p in periods:
        y, m = p.split("-")
        labels.append(f"{calendar.month_abbr[int(m)]}\n{y}" if m in ("01",) or p == periods[0] else calendar.month_abbr[int(m)])
    return labels


def finish(fig, ax, title, subtitle, source, stem, periods):
    import matplotlib.pyplot as plt
    from matplotlib.ticker import MaxNLocator
    ax.axhline(0, color="#555555", linewidth=1)
    step = 3 if len(periods) > 14 else 1
    ticks = list(range(0, len(periods), step))
    if ticks[-1] != len(periods) - 1:
        if len(periods) - 1 - ticks[-1] < 2:
            ticks.pop()  # keep the latest month labelled, drop a crowded neighbour
        ticks.append(len(periods) - 1)
    labels = month_labels(periods)
    ax.set_xticks(ticks)
    ax.set_xticklabels([labels[i] for i in ticks])
    ax.set_xlim(-0.5, len(periods) - 0.5)
    ax.yaxis.set_major_locator(MaxNLocator(nbins=7, steps=[1, 2, 5, 10]))
    ax.yaxis.set_major_formatter(lambda v, _: "0%" if abs(v) < 1e-9 else f"{v:+g}%".replace("-", "\u2212"))
    fig.text(0.04, 0.95, title, fontsize=17, fontweight="bold", color="#111111", ha="left", va="top")
    fig.text(0.04, 0.885, subtitle, fontsize=11.5, color="#444444", ha="left", va="top")
    fig.text(0.04, 0.03, source, fontsize=9.5, color="#666666", ha="left", va="bottom")
    fig.subplots_adjust(left=0.11, right=0.76, top=0.80, bottom=0.17)
    CHARTS.mkdir(exist_ok=True)
    png = CHARTS / f"{stem}.png"
    fig.savefig(png, dpi=300, facecolor="white")
    from PIL import Image
    Image.open(png).convert("RGB").save(CHARTS / f"{stem}.webp", "WEBP", quality=92, method=6)
    plt.close(fig)


def end_label(ax, x, y, text, color, placed):
    # nudge labels apart so they do not overlap
    lo, hi = ax.get_ylim()
    gap = 0.06 * (hi - lo)
    for py in placed:
        if abs(py - y) < gap:
            y = py + (gap if y >= py else -gap)
    placed.append(y)
    ax.annotate(text, (x, y), xytext=(8, 0), textcoords="offset points", color=color,
                fontsize=10.5, fontweight="bold", va="center", annotation_clip=False)


def chart_new_orders(tidy):
    import matplotlib.pyplot as plt
    lines = [("Manufacturing total", "Total", COLORS["dark"], 3.0),
             ("Metal industry", "Metal", COLORS["accent"], 1.8),
             ("Paper and paper products", "Paper", COLORS["teal"], 1.8),
             ("Chemical industry", "Chemicals", COLORS["gold"], 1.8)]
    fig, ax = plt.subplots(figsize=(8, 5))
    placed, periods = [], None
    for brk, label, color, lw in lines:
        s = pick(tidy, "New orders in manufacturing (value)", brk, start=CHART_START)
        periods = list(s.index)
        ax.plot(range(len(s)), s.values, color=color, linewidth=lw)
        end_label(ax, len(s) - 1, s.values[-1], f"{label} {fmt(s.values[-1])}", color, placed)
    last = periods[-1]
    finish(fig, ax, "Factory orders are well above a year ago",
           f"New orders in manufacturing, value, change on a year earlier, %, to {pretty(last)}",
           "Source: Statistics Finland; author's calculations.", "chart1_new_orders_manufacturing", periods)


def chart_turnover_vs_output(tidy):
    import matplotlib.pyplot as plt
    t = pick(tidy, "Turnover in industry", "Total industry", start=CHART_START)
    v = pick(tidy, "Industrial output volume", "Total industry", start=CHART_START)
    periods = sorted(set(t.index) & set(v.index))
    t, v = t.loc[periods], v.loc[periods]
    fig, ax = plt.subplots(figsize=(8, 5))
    x = range(len(periods))
    ax.plot(x, t.values, color=COLORS["accent"], linewidth=2.6)
    ax.plot(x, v.values, color=COLORS["dark"], linewidth=2.6)
    placed = []
    end_label(ax, len(periods) - 1, t.values[-1], f"Turnover {fmt(t.values[-1])}", COLORS["accent"], placed)
    end_label(ax, len(periods) - 1, v.values[-1], f"Output {fmt(v.values[-1])}", COLORS["dark"], placed)
    finish(fig, ax, "Sales rose much faster than output volume",
           f"Total industry, working day adjusted, change on a year earlier, %, to {pretty(periods[-1])}",
           "Source: Statistics Finland; author's calculations.", "chart2_turnover_vs_output", periods)


def chart_finland_vs_euro_area(tidy):
    import matplotlib.pyplot as plt
    fi = pick(tidy, "Industrial production volume", geo="Finland", start=EU_START)
    ea = pick(tidy, "Industrial production volume", geo="Euro area", start=EU_START)
    periods = sorted(set(fi.index) & set(ea.index))
    fi, ea = fi.loc[periods], ea.loc[periods]
    fig, ax = plt.subplots(figsize=(8, 5))
    x = range(len(periods))
    ax.plot(x, fi.values, color=COLORS["dark"], linewidth=2.6)
    ax.plot(x, ea.values, color=COLORS["grey"], linewidth=2.6)
    placed = []
    end_label(ax, len(periods) - 1, fi.values[-1], f"Finland {fmt(fi.values[-1])}", COLORS["dark"], placed)
    end_label(ax, len(periods) - 1, ea.values[-1], f"Euro area {fmt(ea.values[-1])}", COLORS["grey"], placed)
    finish(fig, ax, "Finland held up as euro area output slipped",
           f"Industrial production, calendar adjusted, change on a year earlier, %, to {pretty(periods[-1])}",
           "Source: Eurostat; author's calculations.", "chart3_finland_vs_euro_area_production", periods)


def fmt(v):
    """Signed percentage with a true minus sign."""
    return f"{v:+.1f}%".replace("-", "\u2212")


def pretty(period):
    import calendar
    y, m = period.split("-")
    return f"{calendar.month_name[int(m)]} {y}"


# ---------------------------------------------------------------- numbers
def article_numbers(tidy) -> pd.DataFrame:
    rows = []
    def add(label, s, unit):
        rows.append({"number": label, "period": s.index[-1], "value": s.values[-1], "unit": unit})
    for brk in ["Manufacturing total", "Metal industry", "Paper and paper products", "Chemical industry"]:
        add(f"New orders, {brk.lower()}, year on year", pick(tidy, "New orders in manufacturing (value)", brk), "% (original index)")
    add("Turnover in industry, total, year on year", pick(tidy, "Turnover in industry", "Total industry"), "% (working day adjusted)")
    add("Turnover in industry, total, month on month", pick(tidy, "Turnover in industry", "Total industry", "month_on_month_pct"), "% (seasonally adjusted)")
    add("Industrial output volume, total, year on year", pick(tidy, "Industrial output volume", "Total industry"), "% (working day adjusted)")
    add("Industrial output volume, total, month on month", pick(tidy, "Industrial output volume", "Total industry", "month_on_month_pct"), "% (seasonally adjusted)")
    add("Industrial production, Finland, year on year (Eurostat)", pick(tidy, "Industrial production volume", geo="Finland"), "% (calendar adjusted)")
    add("Industrial production, euro area, year on year (Eurostat)", pick(tidy, "Industrial production volume", geo="Euro area"), "% (calendar adjusted)")
    return pd.DataFrame(rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--offline", action="store_true", help="use raw files already in data/raw")
    args = ap.parse_args(argv)
    RAW.mkdir(parents=True, exist_ok=True)
    if not args.offline:
        for name, spec in DOWNLOADS.items():
            try:
                print("downloaded", download(name, spec).relative_to(ROOT))
            except Exception as exc:  # never fake a series: stop loudly
                sys.exit(f"Could not fetch {name}: {exc}")
    tidy = build_tidy()
    tidy.to_csv(TIDY_CSV, index=False)
    numbers = article_numbers(tidy)
    numbers.to_csv(NUMBERS_CSV, index=False)
    style()
    chart_new_orders(tidy)
    chart_turnover_vs_output(tidy)
    chart_finland_vs_euro_area(tidy)
    print("\nNumbers for the article:")
    for r in numbers.itertuples():
        print(f"  {r.number}: {r.value:+.1f} {r.unit}, {pretty(r.period)}")
    print("\nCharts written to", CHARTS.relative_to(ROOT))


if __name__ == "__main__":
    main()
