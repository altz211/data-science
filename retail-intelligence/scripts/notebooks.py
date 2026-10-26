from pathlib import Path
import nbformat as nbf

root = Path(__file__).resolve().parents[1]
setup = '''from pathlib import Path
import json
import pandas as pd
import matplotlib.pyplot as plt
root = Path.cwd() if (Path.cwd() / 'artifacts').exists() else Path.cwd().parent
artifacts = root / 'artifacts'
plt.rcParams.update({'figure.figsize': (10, 4), 'axes.spines.top': False, 'axes.spines.right': False})'''
notebooks = {
    '01_data_review.ipynb': [
        ('md', '# Transaction data review\n\n## Context & methods\nReal UK gift-retailer transactions from 2009–2011. Source: Chen, D. (2012), Online Retail II, https://doi.org/10.24432/C5CG6D, CC BY 4.0.\n\n### Key assumptions\nPositive purchase sales exclude credits and nonpositive quantity/price. Missing customer IDs are retained for sales analysis. Identical line items are retained. This is not a margin or net-revenue analysis.'),
        ('code', setup),
        ('md', '## Data\nReview the source hash and cleaning counts.'),
        ('code', "run = json.loads((artifacts/'run.json').read_text())\nprint(run['source']['sha256'])\naudit = json.loads((artifacts/'audit.json').read_text())\npd.DataFrame({'value': audit}).astype(str)"),
        ('md', '## Results\nThe dashboard uses the same exported monthly aggregates.'),
        ('code', "snapshot = json.loads((root/'web/assets/results.json').read_text())\nmonthly = pd.DataFrame(snapshot['monthly'])\nmonthly['month'] = pd.to_datetime(monthly['month'])\nfig, ax = plt.subplots()\nax.plot(monthly.month, monthly.sales_gbp, color='#255f92', marker='o', markersize=3)\nax.set(title='Monthly positive purchase sales · UK retailer, 2009–2011', ylabel='Sales (GBP)', xlabel='Month')\nax.ticklabel_format(axis='y', style='plain')\nfig.autofmt_xdate()\nfig.tight_layout()\nplt.show()"),
        ('md', '## Takeaways\nThe first and final months must be checked for incomplete coverage before comparing growth rates. Sales include customers without an ID; customer modelling uses only identified customers. The audit records excluded credits and the duplicate-retention policy.')
    ],
    '02_forecasts.ipynb': [
        ('md', '# Four-week product sales forecasts\n\n## Context & methods\nTrain earlier, select on four validation weeks, then evaluate the selected model on four untouched weeks. The top 60 products are chosen before validation. Forecasts use only information available at one origin.\n\n### Key assumptions\nMissing product-weeks mean zero observed purchases, not proven zero demand. Forecasts are point estimates; uncertainty has not been calibrated. This initial experiment uses one validation origin and one test origin.'),
        ('code', setup),
        ('md', '## Data'),
        ('code', "metrics = json.loads((artifacts/'forecast_metrics.json').read_text())\nprint('Selected:', metrics['selected_model'])\nprint('Validation starts:', metrics['validation_start'])\nprint('Test starts:', metrics['test_start'])\npd.DataFrame(metrics['validation']).T"),
        ('md', '## Results'),
        ('code', "test = pd.DataFrame(metrics['test']).T\ndisplay(test)\nfig, ax = plt.subplots()\nax.bar(test.index, test.mae_units, color=['#255f92','#777777'])\nax.set(title='Untouched holdout · mean absolute error', ylabel='Units per product-week')\nfig.tight_layout()\nplt.show()"),
        ('code', "predictions = pd.read_csv(artifacts/'forecast_test.csv', dtype={'product_id': str})\nby_horizon = predictions.assign(error=lambda x: abs(x.actual-x.prediction)).groupby('horizon').error.mean()\nfig, ax = plt.subplots()\nax.bar(by_horizon.index, by_horizon.values, color='#255f92')\nax.set(title='Holdout error by forecast horizon', xlabel='Weeks ahead', ylabel='MAE (units)')\nax.set_xticks([1,2,3,4])\nfig.tight_layout()\nplt.show()"),
        ('md', '## Takeaways\nCompare validation and holdout tables before drawing a model-quality conclusion. The selected model is refitted after testing for the final historical forward projection. Those projections are not predictions for the present day. Rolling backtests and error concentration by product remain next steps.')
    ],
    '03_recommendations.ipynb': [
        ('md', '# Unseen-product recommendations\n\n## Context & methods\nCosine similarity on binary customer-product histories, compared with popularity. Evaluate on the next 28 days.\n\n### Key assumptions\nOnly returning customers with an unseen purchase inside the preselected top-1,500 catalogue are evaluated. Repeat purchases are excluded. This does not measure conversion uplift or all-customer performance.'),
        ('code', setup),
        ('md', '## Data'),
        ('code', "results = json.loads((artifacts/'recommendation_metrics.json').read_text())\nprint('History cutoff:', results['cutoff'])\nprint(results['scope'])"),
        ('md', '## Results'),
        ('code', "table = pd.DataFrame({key: results[key] for key in ['item_similarity','popularity']}).T\ndisplay(table)\nfig, axes = plt.subplots(1,2,figsize=(10,4))\nfor ax, metric in zip(axes, ['recall_at_10','ndcg_at_10']):\n    ax.bar(table.index, table[metric], color=['#255f92','#777777'])\n    ax.set(title=metric.replace('_',' ').upper(), ylabel='Score')\nfig.suptitle('Next-28-day unseen purchases · eligible returning customers')\nfig.tight_layout()\nplt.show()"),
        ('md', '## Takeaways\nA similarity model must be compared with popularity before adding complexity. These scores cover a restricted cohort; adding all-customer and repeat-purchase evaluation could change the conclusion. The dashboard shows 200 customer aliases for inspection, while evaluation uses the full eligible cohort.')
    ]
}
for filename, cells in notebooks.items():
    nb = nbf.v4.new_notebook(cells=[nbf.v4.new_markdown_cell(text) if kind == 'md' else nbf.v4.new_code_cell(text) for kind,text in cells])
    nb.metadata.kernelspec = {'display_name':'Python 3', 'language':'python', 'name':'python3'}
    nbf.validate(nb)
    nbf.write(nb, root/'notebooks'/filename)
