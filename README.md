# Finland's manufacturing rebound: data and charts

Code and data behind the charts for the article **"Factories are taking orders again. Jobs have not caught up."** (October 2026).

**Status: draft, article not yet published.**

The repository downloads official monthly statistics from Statistics Finland and Eurostat, saves the raw responses, builds one tidy CSV, prints every number used in the article with its unit and period, and draws three charts.

## The charts

| File | What it shows | Latest point |
|---|---|---|
| `charts/chart1_new_orders_manufacturing.png` / `.webp` | New orders in manufacturing (value), change on a year earlier: total, metal industry, paper and paper products, chemical industry. August 2024 to August 2026. | August 2026: total +18.1%, metal +24.3%, paper +8.0%, chemicals −7.2% |
| `charts/chart2_turnover_vs_output.png` / `.webp` | Turnover in industry and volume of industrial output, total industry, working day adjusted, change on a year earlier. August 2024 to August 2026. | August 2026: turnover +11.8%, output +0.8% |
| `charts/chart3_finland_vs_euro_area_production.png` / `.webp` | Industrial production, calendar adjusted, change on a year earlier: Finland and the euro area. January 2025 to August 2026. | August 2026: Finland +0.9%, euro area −1.1% |

PNG files are 2400 × 1500 pixels; WebP files are the same images, smaller.

## How to reproduce

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python make_charts.py        # downloads fresh data and rebuilds everything
.venv/bin/python -m pytest -q          # sanity tests
```

`make_charts.py --offline` rebuilds the CSV files and charts from the raw files already saved in `data/raw/`, without downloading. If a download fails, the script stops with an error; it never fills a gap with made-up numbers.

## Files

- `data/raw/`: the API responses exactly as downloaded (JSON-stat format), one file per source table.
- `data/tidy_series.csv`: all downloaded series in long format (`source, series, geo, breakdown, measure, adjustment, period, value`).
- `data/article_numbers.csv`: the latest value of each series used in the article, with unit and period.
- `make_charts.py`: download, tidy, charts.
- `tests/test_data.py`: checks that row counts and latest values in the tidy CSV match the raw files, that the headline figures equal those in the official releases, and that the charts exist at full resolution.

## Sources

All data are public and free to reuse with attribution.

- **Statistics Finland, New orders in manufacturing**, monthly value index (2021 = 100) and change on a year earlier of the original index. Release for August 2026, published 8 October 2026: <https://stat.fi/en/publication/cmg4siu45i8bj07w0vgkw8dt6>
- **Statistics Finland, Index of turnover in industry**, monthly, working day adjusted change on a year earlier and seasonally adjusted change on the previous month. Release for August 2026, published 9 October 2026: <https://stat.fi/en/publication/cmg0goy296z9707t7clauwkxm>
- **Statistics Finland, Volume index of industrial output**, monthly, working day adjusted change on a year earlier and seasonally adjusted change on the previous month. Latest release page: <https://stat.fi/en/publication/cmfwfnxcdgti607w1hg8019uy>; August 2026 data from the Statistics Finland database, updated 8 October 2026.
- **Eurostat, Production in industry, monthly data**, calendar adjusted change on a year earlier, total industry (mining, manufacturing and energy), Finland and the euro area. Euro indicators release for August 2026, published 15 October 2026: <https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/4-15102026-ap>

Data are downloaded through the Statistics Finland database interface (<https://pxdata.stat.fi/>) and the Eurostat dissemination interface (<https://ec.europa.eu/eurostat/web/user-guides/data-browser/api-data-access>). Data were last downloaded on 18 October 2026.

Chart footers read "Source: Statistics Finland; author's calculations." or "Source: Eurostat; author's calculations."

## Method notes

- Changes on a year earlier are taken as published; no seasonal adjustment of our own.
- "Manufacturing total" for new orders covers the industries in the new orders statistics: paper and paper products, chemical industry and metal industry.
- "Total industry" in chart 2 is mining, manufacturing and energy supply for both turnover and output, so the two lines cover the same industries.
- The euro area is the current 21 country euro area.
- The latest month is preliminary in all sources and may be revised.
