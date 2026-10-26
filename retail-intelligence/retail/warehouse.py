"""Load transactions into DuckDB and create the reporting views."""
from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from retail.paths import DATABASE, SQL


def build(rows: pd.DataFrame, database: str | Path = DATABASE) -> duckdb.DuckDBPyConnection:
    """Store the raw rows unchanged and layer the SQL views on top."""
    if str(database) != ":memory:":
        Path(database).parent.mkdir(parents=True, exist_ok=True)
    db = duckdb.connect(str(database))
    db.register("incoming", rows)
    db.execute("CREATE OR REPLACE TABLE raw_transactions AS SELECT * FROM incoming")
    db.unregister("incoming")
    for name in ("clean.sql", "marts.sql"):
        db.execute((SQL / name).read_text())
    return db


def connect(database: str | Path = DATABASE) -> duckdb.DuckDBPyConnection:
    if not Path(database).exists():
        raise FileNotFoundError(f"{database} not found. Run `python -m retail` first.")
    return duckdb.connect(str(database), read_only=True)


def query(db: duckdb.DuckDBPyConnection, sql: str, params=None) -> pd.DataFrame:
    return db.execute(sql, params).df()


def scalar(db: duckdb.DuckDBPyConnection, sql: str, params=None):
    return db.execute(sql, params).fetchall()[0][0]


def audit(db: duckdb.DuckDBPyConnection) -> dict:
    """Row counts for each cleaning rule, so exclusions are visible."""
    counts = query(db, """
        SELECT count(*) AS source_rows,
               count(*) FILTER (WHERE is_purchase AND is_merchandise) AS sales_rows,
               count(*) FILTER (WHERE is_credit) AS credit_rows,
               count(*) FILTER (WHERE NOT is_merchandise) AS fee_or_adjustment_rows,
               count(*) FILTER (WHERE NOT is_credit AND is_merchandise
                                AND (quantity <= 0 OR unit_price <= 0)) AS zero_or_negative_rows,
               count(*) FILTER (WHERE customer_id IS NULL) AS missing_customer_rows,
               min(invoice_date)::VARCHAR AS first_timestamp,
               max(invoice_date)::VARCHAR AS last_timestamp
        FROM checked_transactions
    """).to_dict("records")[0]
    totals = query(db, """
        SELECT sum(sales_gbp) AS sales_gbp,
               count(DISTINCT invoice) AS orders,
               count(DISTINCT customer_id) AS customers,
               count(DISTINCT product_id) AS products,
               count(DISTINCT country) AS countries
        FROM purchases
    """).to_dict("records")[0]
    identical = scalar(db, """
        SELECT count(*) - count(DISTINCT (invoice, product_id, description, quantity,
                                          invoice_date, unit_price, customer_id, country))
        FROM raw_transactions
    """)
    result = {**counts, "identical_rows": identical, **totals}
    return {key: value.item() if hasattr(value, "item") else value for key, value in result.items()}
