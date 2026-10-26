import json
import duckdb
import pandas as pd
from retail.download import download
from retail.paths import ROOT, DATA, DATABASE, ARTIFACTS


def prepare():
    source = download()
    sheets = pd.read_excel(source, sheet_name=None, dtype={'Invoice': str, 'StockCode': str})
    rows = pd.concat(sheets.values(), ignore_index=True)
    rows.columns = ['invoice', 'product_id', 'description', 'quantity', 'invoice_date',
                    'unit_price', 'customer_id', 'country']
    rows['invoice_date'] = pd.to_datetime(rows.invoice_date, errors='coerce')
    rows['customer_id'] = rows.customer_id.astype('Int64').astype('string')
    rows['description'] = rows.description.fillna('Unknown product').astype(str)
    for name in ['quantity', 'unit_price']:
        rows[name] = pd.to_numeric(rows[name], errors='coerce')
    DATA.mkdir(exist_ok=True)
    ARTIFACTS.mkdir(exist_ok=True)
    with duckdb.connect(str(DATABASE)) as db:
        db.register('incoming', rows)
        db.execute('CREATE OR REPLACE TABLE raw_transactions AS SELECT * FROM incoming')
        db.execute((ROOT / 'sql/clean.sql').read_text())
        audit = {'source_rows': len(rows), 'exact_duplicate_rows': int(rows.duplicated().sum()),
                 'missing_customer_rows': int(rows.customer_id.isna().sum()),
                 'purchase_rows': db.execute('SELECT count(*) FROM purchases').fetchone()[0],
                 'non_merchandise_positive_rows': db.execute('SELECT count(*) FROM checked_transactions WHERE is_purchase AND NOT is_merchandise').fetchone()[0],
                 'credit_rows': db.execute('SELECT count(*) FROM checked_transactions WHERE is_credit').fetchone()[0],
                 'first_date': str(rows.invoice_date.min()), 'last_date': str(rows.invoice_date.max()),
                 'duplicate_policy': 'Retained: identical line items are not necessarily duplicated events.',
                 'sales_definition': 'Positive merchandise purchases only: numeric five-digit SKU with optional letter suffix; credit invoices and fee codes excluded. GBP, not profit.'}
        db.execute(f"COPY purchases TO '{DATA / 'purchases.parquet'}' (FORMAT PARQUET)")
    (ARTIFACTS / 'audit.json').write_text(json.dumps(audit, indent=2) + '\n')
    print(json.dumps(audit, indent=2))


if __name__ == '__main__':
    prepare()
