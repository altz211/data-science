import argparse
import calendar
import json
from pathlib import Path
import duckdb
import pandas as pd
from retail.paths import DATABASE, ROOT


def change(current, previous):
    return (current / previous - 1) * 100 if previous else None


def export(database=DATABASE):
    with duckdb.connect(str(database), read_only=True) as db:
        first, last = db.execute('SELECT min(invoice_date), max(invoice_date) FROM purchases').fetchone()
        first = pd.Timestamp(first).normalize()
        end_of_data = pd.Timestamp(last).normalize() + pd.Timedelta(days=1)
        countries = db.execute('SELECT country FROM purchases GROUP BY 1 ORDER BY sum(sales_gbp) DESC LIMIT 5').df().country.tolist()
        markets = ['All markets'] + countries
        months = pd.date_range(first.replace(day=1), end_of_data-pd.Timedelta(days=1), freq='MS')
        periods = [{'id':'all', 'label':'All history', 'start':first, 'end':end_of_data, 'previous':None}]
        for start in months:
            end = min(start + pd.offsets.MonthBegin(1), end_of_data)
            previous_start = start - pd.offsets.MonthBegin(1)
            days = (end-start).days
            previous_end = min(previous_start+pd.Timedelta(days=days),start) if end < start+pd.offsets.MonthBegin(1) else start
            periods.append({'id':start.strftime('%Y-%m'),
                'label':start.strftime('%B %Y') + (' · partial' if end.day != 1 else ''),
                'start':start,'end':end,
                'previous':(previous_start,previous_end) if previous_start >= first else None})
        sql = (ROOT/'sql/kpis.sql').read_text()
        slices = {}
        for period in periods:
            slices[period['id']] = {}
            for market in markets:
                def measures(start, end):
                    values = db.execute(sql, {'start':start,'end':end,'market':market}).df().iloc[0].to_dict()
                    values = {key:float(value) if pd.notna(value) else 0 for key,value in values.items()}
                    values['aov'] = values['sales_gbp']/values['orders'] if values['orders'] else 0
                    values['returning_share'] = values['returning_customers']/values['customers']*100 if values['customers'] else None
                    return values
                current = measures(period['start'],period['end'])
                previous = measures(*period['previous']) if period['previous'] else None
                params = {'start':period['start'], 'end':period['end'], 'market':market}
                where = "invoice_date >= $start AND invoice_date < $end AND ($market = 'All markets' OR country = $market)"
                daily = db.execute(f'''SELECT CAST(invoice_date AS DATE) AS day, sum(sales_gbp)::DOUBLE AS sales_gbp,
                    count(DISTINCT invoice) AS orders, count(DISTINCT customer_id) AS customers, sum(quantity)::DOUBLE AS units
                    FROM purchases WHERE {where} GROUP BY 1 ORDER BY 1''', params).df()
                calendar_days = pd.date_range(period['start'],period['end']-pd.Timedelta(days=1),freq='D')
                daily = daily.set_index('day').reindex(calendar_days).fillna(0).rename_axis('day').reset_index()
                daily['day'] = daily.day.dt.strftime('%Y-%m-%d')
                prior_daily = []
                if period['previous']:
                    start,end = period['previous']
                    prior = db.execute(f'''SELECT CAST(invoice_date AS DATE) AS day, sum(sales_gbp)::DOUBLE AS sales_gbp,
                        count(DISTINCT invoice) AS orders, count(DISTINCT customer_id) AS customers, sum(quantity)::DOUBLE AS units
                        FROM purchases WHERE {where} GROUP BY 1 ORDER BY 1''', {'start':start,'end':end,'market':market}).df()
                    prior = prior.set_index('day').reindex(pd.date_range(start,end-pd.Timedelta(days=1),freq='D')).fillna(0).rename_axis('day').reset_index()
                    prior['day'] = prior.day.dt.strftime('%Y-%m-%d')
                    prior_daily = prior.to_dict('records')
                products = db.execute(f'''SELECT product_id, arg_max(description,invoice_date) AS description,
                    sum(sales_gbp)::DOUBLE AS sales_gbp, sum(quantity)::DOUBLE AS units, count(DISTINCT invoice) AS orders
                    FROM purchases WHERE {where} GROUP BY 1 ORDER BY sales_gbp DESC, product_id LIMIT 100''',params).df()
                mix = db.execute(f'''SELECT country, sum(sales_gbp)::DOUBLE AS sales_gbp FROM purchases
                    WHERE {where} GROUP BY 1 ORDER BY 2 DESC''',params).df()
                slices[period['id']][market] = {'metrics':current,'previous':previous,
                    'daily':daily.to_dict('records'),'prior_daily':prior_daily,
                    'products':products.to_dict('records'),'markets':mix.to_dict('records')}
        output = {'markets':markets, 'default_period':periods[-2]['id'],
            'periods':[{'id':p['id'],'label':p['label'],'start':str(p['start'].date()),
                'end':str((p['end']-pd.Timedelta(days=1)).date()),
                'comparison':f"{p['previous'][0].date()} to {(p['previous'][1]-pd.Timedelta(days=1)).date()}" if p['previous'] else None} for p in periods],
            'slices':slices,'source_rows':db.execute('SELECT count(*) FROM raw_transactions').fetchone()[0]}
    destination = ROOT/'web/assets/kpis.json'
    destination.write_text(json.dumps(output,allow_nan=False,separators=(',',':'))+'\n')
    print(destination, destination.stat().st_size)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--database',type=Path,default=DATABASE)
    export(parser.parse_args().database)
