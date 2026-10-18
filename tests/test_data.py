"""Sanity tests: the tidy CSV and article numbers must match the raw downloads."""
import json
import re
from pathlib import Path

import pandas as pd
import pytest
from PIL import Image

import make_charts as mc

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def tidy():
    return pd.read_csv(mc.TIDY_CSV, dtype={"period": str})


def raw(name):
    return json.loads((mc.RAW / f"{name}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", list(mc.DOWNLOADS))
def test_row_counts_match_raw(tidy, name):
    data = raw(name)
    values = data["value"]
    n_raw = sum(v is not None for v in (values.values() if isinstance(values, dict) else values))
    assert (tidy.series == mc.SERIES_NAME[name]).sum() == n_raw


def test_tidy_rebuild_is_identical(tidy):
    rebuilt = mc.build_tidy()
    pd.testing.assert_frame_equal(rebuilt.reset_index(drop=True), tidy, check_dtype=False)


def test_latest_period_is_august_2026(tidy):
    for name in mc.DOWNLOADS:
        assert tidy[tidy.series == mc.SERIES_NAME[name]].period.max() == "2026-08"


def raw_latest(name, **select):
    df = mc.jsonstat_to_frame(raw(name))
    for k, v in select.items():
        df = df[df[k] == v]
    tcol = "time" if "time" in df else "timeperiod_m"
    return df.sort_values(tcol).iloc[-1]["value"]


def test_latest_values_match_raw(tidy):
    assert mc.pick(tidy, "New orders in manufacturing (value)", "Manufacturing total").iloc[-1] == raw_latest(
        "statistics_finland_new_orders_manufacturing", toimiala_17_20220818="C", contentscode="teul-muutosprosentti")
    assert mc.pick(tidy, "Turnover in industry", "Total industry").iloc[-1] == raw_latest(
        "statistics_finland_turnover_industry", contentscode="tlv-tpk_muutos")
    assert mc.pick(tidy, "Industrial output volume", "Total industry").iloc[-1] == raw_latest(
        "statistics_finland_industrial_output_volume", contentscode="ttvi-tpk_muutos")
    assert mc.pick(tidy, "Industrial production volume", geo="Euro area").iloc[-1] == raw_latest(
        "eurostat_industrial_production", geo="EA21")


def test_headline_numbers_match_official_releases(tidy):
    # Figures quoted in the official releases of 8, 9 and 15 October 2026.
    assert mc.pick(tidy, "New orders in manufacturing (value)", "Manufacturing total")["2026-08"] == 18.1
    assert mc.pick(tidy, "Turnover in industry", "Total industry")["2026-08"] == 11.8
    assert mc.pick(tidy, "Industrial output volume", "Total industry")["2026-08"] == 0.8
    assert mc.pick(tidy, "Industrial production volume", geo="Finland")["2026-08"] == 0.9
    assert mc.pick(tidy, "Industrial production volume", geo="Euro area")["2026-08"] == -1.1


def test_chart_windows_complete(tidy):
    for brk in ["Manufacturing total", "Metal industry", "Paper and paper products", "Chemical industry"]:
        assert len(mc.pick(tidy, "New orders in manufacturing (value)", brk, start=mc.CHART_START)) == 25
    assert len(mc.pick(tidy, "Industrial production volume", geo="Finland", start=mc.EU_START)) == 20


def test_no_codes_or_credits_in_published_text():
    code_pattern = re.compile(r"\b(14m[a-z0-9]|14n8|14s8|sts_inpr|teul|ttvi|tlv|EA2[01]|PCH_SM)\b", re.I)
    published = [ROOT / "README.md", mc.TIDY_CSV, mc.NUMBERS_CSV]
    for path in published:
        text = path.read_text(encoding="utf-8")
        assert not code_pattern.search(text), path.name
        assert "chart:" not in text.lower() and "chart by" not in text.lower(), path.name
    for path in list((ROOT / "charts").iterdir()) + list((ROOT / "data").rglob("*")):
        assert not code_pattern.search(path.name), path.name


def test_chart_files_exist_and_are_high_resolution():
    for stem in ["chart1_new_orders_manufacturing", "chart2_turnover_vs_output", "chart3_finland_vs_euro_area_production"]:
        for ext in ("png", "webp"):
            img = Image.open(ROOT / "charts" / f"{stem}.{ext}")
            assert img.size[0] >= 2000
