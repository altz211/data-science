"""Run the whole pipeline.

    python -m retail                       # download from UCI on first run
    python -m retail --source data.xlsx    # or use a local copy
    python -m retail --skip-models         # analytics only, about 15 seconds
"""
from __future__ import annotations

import argparse
import json
import platform
import time
from contextlib import contextmanager
from datetime import datetime, timezone

import sklearn

from retail import analytics, forecast, recommend, report, warehouse
from retail.data import MANIFEST, load_transactions
from retail.paths import WEB_DATA

timings = {}


@contextmanager
def step(label: str):
    print(f"→ {label}…", flush=True)
    started = time.perf_counter()
    yield
    timings[label] = round(time.perf_counter() - started, 1)
    print(f"  done in {timings[label]}s", flush=True)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", help="local zip, xlsx, csv or parquet copy of Online Retail II")
    parser.add_argument("--refresh", action="store_true", help="ignore the cached Parquet file")
    parser.add_argument("--skip-models", action="store_true", help="reuse the last forecast and recommendation results")
    args = parser.parse_args(argv)

    with step("Loading transactions"):
        rows = load_transactions(args.source, args.refresh)
    with step("Building the DuckDB warehouse"):
        db = warehouse.build(rows)
        audit = warehouse.audit(db)
    with step("Exporting dashboard analytics"):
        pages = analytics.export(db)

    if args.skip_models:
        forecasts = json.loads((WEB_DATA / "forecast.json").read_text())
        recs = json.loads((WEB_DATA / "recommendations.json").read_text())
    else:
        with step("Backtesting and fitting forecasts"):
            result = forecast.run(db)
            ids = [p["id"] for p in result["products"]]
            names = analytics.product_names(db, ids)
            for product in result["products"]:
                product["name"] = names[product["id"]]
            forecasts = {**result, "metrics": analytics.table(result["metrics"], 4),
                         "by_horizon": analytics.table(result["by_horizon"], 4)}
            analytics.write_json("forecast", forecasts)
        with step("Evaluating and fitting recommendations"):
            result = recommend.run(db)
            ids = {p["id"] for p in result["similar"]} | set(result["trending"])
            ids |= {other for p in result["similar"] for other, _ in p["similar"]}
            recs = {**result, "metrics": analytics.table(result["metrics"], 4),
                    "names": analytics.product_names(db, ids)}
            analytics.write_json("recommendations", recs)

    with step("Writing the report"):
        sections = report.findings(pages["overview"], pages["customers"], pages["products"], forecasts, recs)
        analytics.write_json("report", {"sections": sections})
        path = report.write(sections, audit)

    source = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    analytics.write_json("meta", {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "audit": audit,
        "source": source,
        "python": platform.python_version(),
        "scikit_learn": sklearn.__version__,
        "timings_seconds": timings,
    })
    db.close()
    print(f"\nDashboard data in {WEB_DATA}\nReport in {path}")


if __name__ == "__main__":
    main()
