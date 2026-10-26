import json
from collections import Counter
import duckdb
import joblib
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from sklearn.neighbors import NearestNeighbors
from retail.paths import DATABASE, ARTIFACTS


def recommend(model, history, k=10):
    scores = Counter()
    for product in set(history):
        for other, similarity in model['neighbors'].get(product, []):
            if other not in history:
                scores[other] += similarity
    ranked = [product for product, score in scores.most_common() if score > 0]
    ranked += [p for p in model['popular'] if p not in history and p not in ranked]
    return ranked[:k]


def train():
    cutoff = pd.Timestamp(json.loads((ARTIFACTS/'forecast_metrics.json').read_text())['test_start'])
    with duckdb.connect(str(DATABASE), read_only=True) as db:
        rows = db.execute('''SELECT customer_id, product_id, invoice_date FROM purchases
            WHERE customer_id IS NOT NULL''').df()
    before = rows[rows.invoice_date < cutoff]
    after = rows[(rows.invoice_date >= cutoff) & (rows.invoice_date < cutoff+pd.Timedelta(days=28))]
    popular = before.groupby('product_id').size().sort_values(ascending=False).head(1500).index.tolist()
    customers = sorted(before.customer_id.unique())
    items = {p: i for i, p in enumerate(popular)}
    users = {p: i for i, p in enumerate(customers)}
    pairs = before[before.product_id.isin(items)].drop_duplicates(['customer_id','product_id'])
    matrix = csr_matrix((np.ones(len(pairs)), (pairs.product_id.map(items), pairs.customer_id.map(users))),
                        shape=(len(items),len(users)))
    search = NearestNeighbors(metric='cosine', algorithm='brute', n_neighbors=min(31,len(items))).fit(matrix)
    distances, indices = search.kneighbors(matrix)
    neighbors = {p: [(popular[j], float(1-d)) for d,j in zip(distances[i],indices[i]) if j != i]
                 for i,p in enumerate(popular)}
    model = {'popular': popular, 'neighbors': neighbors, 'cutoff': str(cutoff.date())}
    histories = before.groupby('customer_id').product_id.agg(lambda x: list(dict.fromkeys(x))).to_dict()
    targets = after.groupby('customer_id').product_id.agg(set).to_dict()
    scores = {'item_similarity': [], 'popularity': []}
    for user, target in targets.items():
        if user not in histories:
            continue
        history = histories[user]
        relevant = (target & set(items)) - set(history)
        if not relevant:
            continue
        alternatives = {'item_similarity': recommend(model, history),
                        'popularity': [p for p in popular if p not in history][:10]}
        for name, ranking in alternatives.items():
            hits = [int(p in relevant) for p in ranking]
            ideal = sum(1/np.log2(i+2) for i in range(min(10,len(relevant))))
            scores[name].append([sum(hits)/len(relevant),
                sum(hit/np.log2(i+2) for i,hit in enumerate(hits))/ideal])
    metrics = {name: {'recall_at_10': float(np.mean(values,axis=0)[0]),
                     'ndcg_at_10': float(np.mean(values,axis=0)[1]), 'evaluated_customers': len(values)}
               for name,values in scores.items()}
    metrics['scope'] = 'Returning customers with unseen purchases in the training top-1500 catalogue. Previously purchased products excluded; not all-customer performance.'
    metrics['cutoff'] = str(cutoff.date())
    sample = {f'Customer {i+1:03d}': {'history': history,
              'actual_next': sorted(targets.get(user,set()) - set(history))}
              for i,(user,history) in enumerate(histories.items()) if i < 200}
    joblib.dump(model, ARTIFACTS/'recommendations.joblib')
    (ARTIFACTS/'customers.json').write_text(json.dumps(sample))
    (ARTIFACTS/'recommendation_metrics.json').write_text(json.dumps(metrics,indent=2)+'\n')
    print(json.dumps(metrics,indent=2))


if __name__ == '__main__':
    train()
