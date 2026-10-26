from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / "sql"

# Local working data. Git ignores everything in here.
DATA = ROOT / "data"
RAW = DATA / "raw"
DATABASE = DATA / "retail.duckdb"
MODELS = DATA / "models"

# Small JSON files the dashboard reads. These are committed so GitHub Pages
# can serve the dashboard without running the pipeline.
WEB_DATA = ROOT / "web" / "data"
REPORT = ROOT / "docs" / "report.md"
