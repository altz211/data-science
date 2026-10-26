"""Small API around the saved results, plus the dashboard itself.

    uvicorn retail.api:app --reload      then open http://localhost:8000

Recommendations only need a list of product codes, so no customer data is
ever loaded or exposed.
"""
from __future__ import annotations

import json
from functools import lru_cache

import joblib
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from retail.paths import MODELS, ROOT, WEB_DATA
from retail.recommend import recommend

app = FastAPI(title="Retail Intelligence", version="2.0.0")


class Basket(BaseModel):
    products: list[str] = Field(..., min_length=1, examples=[["85123A", "22423"]])
    k: int = Field(10, ge=1, le=50)


@lru_cache
def page(name: str) -> dict:
    path = WEB_DATA / f"{name}.json"
    if not path.exists():
        raise HTTPException(503, f"{name}.json is missing. Run `python -m retail` first.")
    return json.loads(path.read_text())


@lru_cache
def recommender() -> dict:
    path = MODELS / "recommendations.joblib"
    if not path.exists():
        raise HTTPException(503, "No trained recommender. Run `python -m retail` first.")
    return joblib.load(path)


def names() -> dict:
    return {**page("products")["names"], **page("recommendations")["names"], **page("overview")["names"]}


@app.get("/api/health")
def health():
    return {"status": "ok", "model_available": (MODELS / "recommendations.joblib").exists()}


@app.get("/api/kpis/{period}")
def kpis(period: str, market: str = "All markets"):
    """Headline figures for a month (YYYY-MM) or 'all'."""
    table = page("overview")["kpis"]
    for row in table["rows"]:
        record = dict(zip(table["columns"], row))
        if record["period"] == period and record["market"] == market:
            return record
    raise HTTPException(404, f"No figures for {period} / {market}")


@app.get("/api/forecast/{product_id}")
def forecast(product_id: str):
    """Next four weeks of units, with an 80% range."""
    for product in page("forecast")["products"]:
        if product["id"] == product_id.upper():
            return {"product_id": product["id"], "name": product["name"],
                    "weeks": [{"week": w, "units": p, "low": lo, "high": hi} for w, p, lo, hi in product["future"]]}
    raise HTTPException(404, "Forecasts cover the top 100 products only")


@app.post("/api/recommendations")
def recommendations(basket: Basket):
    """Products to suggest to someone who has bought `products`."""
    model = recommender()
    lookup = names()
    picks = recommend(model, [p.upper() for p in basket.products], basket.k)
    return {"products": [{"product_id": p, "name": lookup.get(p, p)} for p in picks]}


app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="dashboard")
