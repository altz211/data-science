"""Get the Online Retail II transactions into a tidy DataFrame.

The UCI download is a 45 MB Excel workbook that takes a minute or two to
parse, so the first read is cached as Parquet and reused afterwards.
"""
from __future__ import annotations

import hashlib
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile

import pandas as pd

from retail.paths import RAW

UCI_URL = "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"
CITATION = "Chen, D. (2012). Online Retail II. UCI Machine Learning Repository. https://doi.org/10.24432/C5CG6D"
COLUMNS = ["invoice", "product_id", "description", "quantity",
           "invoice_date", "unit_price", "customer_id", "country"]

CACHE = RAW / "transactions.parquet"
MANIFEST = RAW / "source.json"


def load_transactions(source: str | Path | None = None, refresh: bool = False) -> pd.DataFrame:
    """Return every transaction line, downloading the data the first time.

    `source` may be the UCI zip, the Excel workbook, or a CSV/Parquet copy with
    the same eight columns in the same order.
    """
    if CACHE.exists() and source is None and not refresh:
        return pd.read_parquet(CACHE)

    RAW.mkdir(parents=True, exist_ok=True)
    path = Path(source) if source else download()
    rows = tidy(read_any(path))
    rows.to_parquet(CACHE, index=False)
    MANIFEST.write_text(json.dumps({
        "source": path.name if source else UCI_URL,
        "sha256": sha256(path),
        "rows": len(rows),
        "loaded_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "license": "CC BY 4.0",
        "citation": CITATION,
    }, indent=2) + "\n")
    return rows


def download() -> Path:
    archive = RAW / "online_retail_ii.zip"
    if not archive.exists():
        partial = archive.with_suffix(".part")
        with urllib.request.urlopen(UCI_URL, timeout=120) as response, partial.open("wb") as out:
            while chunk := response.read(1 << 20):
                out.write(chunk)
        partial.replace(archive)
    return archive


def read_any(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".zip":
        with ZipFile(path) as archive:
            workbook = next(name for name in archive.namelist() if name.endswith(".xlsx"))
            with archive.open(workbook) as file:
                return read_workbook(file)
    if suffix == ".xlsx":
        return read_workbook(path)
    if suffix == ".parquet":
        return pd.read_parquet(path)
    if suffix == ".csv":
        return pd.read_csv(path, dtype={0: str, 1: str}, encoding_errors="replace")
    raise ValueError(f"Don't know how to read {path.name}")


def read_workbook(file) -> pd.DataFrame:
    # The workbook splits the two years across two sheets.
    sheets = pd.read_excel(file, sheet_name=None, dtype={"Invoice": str, "StockCode": str})
    return pd.concat(sheets.values(), ignore_index=True)


def tidy(rows: pd.DataFrame) -> pd.DataFrame:
    if rows.shape[1] != len(COLUMNS):
        raise ValueError(f"Expected {len(COLUMNS)} columns, got {rows.shape[1]}")
    rows = rows.set_axis(COLUMNS, axis=1)
    rows["invoice"] = rows.invoice.astype(str).str.strip()
    rows["product_id"] = rows.product_id.astype(str).str.strip().str.upper()
    rows["description"] = rows.description.fillna("").astype(str).str.strip()
    rows["quantity"] = pd.to_numeric(rows.quantity, errors="coerce")
    rows["unit_price"] = pd.to_numeric(rows.unit_price, errors="coerce")
    rows["invoice_date"] = pd.to_datetime(rows.invoice_date, errors="coerce")
    # Customer IDs arrive as floats (12345.0) because of the gaps.
    rows["customer_id"] = pd.to_numeric(rows.customer_id, errors="coerce").astype("Int64").astype("string")
    rows["country"] = rows.country.astype(str).str.strip()
    return rows


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while chunk := file.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()
