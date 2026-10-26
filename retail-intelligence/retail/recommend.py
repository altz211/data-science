"""'Customers who bought this also bought' recommendations.

Item-to-item cosine similarity on who bought what, blended with what is
selling right now. It is simple, explainable to a buyer, and only needs a
product list to make recommendations, so the dashboard and API never need
to see customer data.
"""
from __future__ import annotations

from collections import Counter

import joblib
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from sklearn.preprocessing import normalize

from retail.paths import MODELS
from retail.warehouse import query

CATALOGUE = 1500   # most-bought products; the long tail is too sparse to score
NEIGHBOURS = 30
K = 10
WINDOW = pd.Timedelta(days=28)
FUSION_GRID = (5, 10, 30, 60)


def fit(purchases: pd.DataFrame, fusion_k: int | None = None) -> dict:
    """purchases: customer_id, product_id, invoice_date (repeats are fine)."""
    popular = purchases.product_id.value_counts().index[:CATALOGUE].tolist()
    items = {product: i for i, product in enumerate(popular)}
    pairs = purchases[purchases.product_id.isin(items)].drop_duplicates(["customer_id", "product_id"])
    customers = pd.Categorical(pairs.customer_id).codes
    matrix = csr_matrix((np.ones(len(pairs)), (pairs.product_id.map(items), customers)),
                        shape=(len(items), customers.max() + 1))
    unit = normalize(matrix)
    similarity = (unit @ unit.T).toarray()
    np.fill_diagonal(similarity, 0)

    count = min(NEIGHBOURS, len(popular) - 1)
    nearest = np.argsort(-similarity, axis=1)[:, :count]
    neighbours = {
        product: [(popular[j], float(similarity[i, j])) for j in nearest[i] if similarity[i, j] > 0]
        for i, product in enumerate(popular)
    }
    recent = purchases[purchases.invoice_date >= purchases.invoice_date.max() - WINDOW]
    trending = recent.product_id.value_counts().index[:300].tolist()
    return {"popular": popular, "neighbours": neighbours, "trending": trending, "fusion_k": fusion_k}


def similar_to(model: dict, basket: set) -> list[str]:
    scores = Counter()
    for product in basket:
        for other, similarity in model["neighbours"].get(product, []):
            if other not in basket:
                scores[other] += similarity
    return [product for product, _ in scores.most_common(100)]


def recommend(model: dict, basket, k: int = K) -> list[str]:
    """Rank unseen products for a basket of products the customer already bought.

    With `fusion_k` set, similarity and trending rankings are merged with
    reciprocal rank fusion: each list adds 1 / (fusion_k + rank). A smaller
    fusion_k trusts the top of each list more.
    """
    owned = set(basket)
    ranked = similar_to(model, owned)
    if model.get("fusion_k"):
        trending = [p for p in model["trending"] if p not in owned][:100]
        fused = Counter()
        for ranking in (ranked, trending):
            for position, product in enumerate(ranking):
                fused[product] += 1 / (model["fusion_k"] + position)
        ranked = [product for product, _ in fused.most_common()]
    ranked += [p for p in model["popular"] if p not in owned and p not in ranked]
    return ranked[:k]


def ranking_scores(ranked: list[str], relevant: set[str]) -> tuple[float, float, float]:
    hits = [product in relevant for product in ranked]
    ideal = sum(1 / np.log2(i + 2) for i in range(min(len(ranked), len(relevant))))
    dcg = sum(hit / np.log2(i + 2) for i, hit in enumerate(hits))
    return sum(hits) / len(relevant), dcg / ideal, float(any(hits))


def evaluate(purchases: pd.DataFrame, cutoff: pd.Timestamp, fusion_k: int) -> pd.DataFrame:
    """Train before `cutoff`; score against products each customer buys for the first time in the next 28 days.

    Only returning customers can be scored: a brand-new customer has no basket
    to start from and would simply be shown best sellers.
    """
    before = purchases[purchases.invoice_date < cutoff]
    after = purchases[(purchases.invoice_date >= cutoff) & (purchases.invoice_date < cutoff + WINDOW)]
    model = fit(before)
    hybrid = {**model, "fusion_k": fusion_k}
    strategies = {
        "Hybrid (similarity + trending)": lambda basket: recommend(hybrid, basket),
        "Item similarity": lambda basket: recommend(model, basket),
        "Trending (last 28 days)": lambda basket: [p for p in model["trending"] if p not in basket][:K],
        "Best sellers": lambda basket: [p for p in model["popular"] if p not in basket][:K],
    }

    catalogue = set(model["popular"])
    histories = before.groupby("customer_id").product_id.agg(set)
    targets = after.groupby("customer_id").product_id.agg(set)
    results = {name: [] for name in strategies}
    shown = {name: set() for name in strategies}
    for customer, bought in targets.items():
        if customer not in histories.index:
            continue
        basket = histories[customer]
        relevant = (bought & catalogue) - basket
        if not relevant:
            continue
        for name, strategy in strategies.items():
            ranked = strategy(basket)
            shown[name].update(ranked)
            results[name].append(ranking_scores(ranked, relevant))

    rows = []
    for name, values in results.items():
        recall, ndcg, hit = np.mean(values, axis=0)
        rows.append({"model": name, "recall_at_10": recall, "ndcg_at_10": ndcg, "hit_rate_at_10": hit,
                     "catalogue_coverage": len(shown[name]) / len(catalogue), "customers": len(values)})
    return pd.DataFrame(rows)


def run(db, examples: int = 150) -> dict:
    purchases = query(db, """
        SELECT customer_id, product_id, invoice_date FROM purchases
        WHERE customer_id IS NOT NULL
    """)
    cutoff = purchases.invoice_date.max().normalize() + pd.Timedelta(days=1) - WINDOW

    # Pick the blend on the previous four weeks, then report on the final four.
    tuning = {k: evaluate(purchases, cutoff - WINDOW, k).set_index("model").loc[
                  "Hybrid (similarity + trending)", "recall_at_10"] for k in FUSION_GRID}
    fusion_k = max(tuning, key=tuning.get)
    metrics = evaluate(purchases, cutoff, fusion_k)

    model = fit(purchases, fusion_k)
    MODELS.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODELS / "recommendations.joblib")

    similar = [{"id": product,
                "similar": [[other, round(score, 3)] for other, score in model["neighbours"][product][:K]]}
               for product in model["popular"][:examples]]
    return {
        "cutoff": f"{cutoff:%Y-%m-%d}",
        "evaluation_days": WINDOW.days,
        "catalogue": len(model["popular"]),
        "fusion_k": fusion_k,
        "tuning_recall": {str(k): round(v, 4) for k, v in tuning.items()},
        "metrics": metrics,
        "similar": similar,
        "trending": model["trending"][:20],
    }
