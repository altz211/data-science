import pytest
from fastapi.testclient import TestClient

from retail.api import app
from retail.paths import MODELS, WEB_DATA

pytestmark = pytest.mark.skipif(not (WEB_DATA / "overview.json").exists(), reason="run `python -m retail` first")
client = TestClient(app)


def test_health_and_dashboard():
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/").status_code == 200


def test_kpis_and_forecast():
    november = client.get("/api/kpis/2011-11").json()
    assert november["orders"] > 0
    assert client.get("/api/kpis/1999-01").status_code == 404
    forecast = client.get("/api/forecast/85123a").json()
    assert len(forecast["weeks"]) == 4


@pytest.mark.skipif(not (MODELS / "recommendations.joblib").exists(), reason="no trained model")
def test_recommendations_exclude_the_basket():
    basket = ["85123A", "22423"]
    picks = client.post("/api/recommendations", json={"products": basket, "k": 5}).json()["products"]
    assert len(picks) == 5
    assert not {p["product_id"] for p in picks} & set(basket)
    assert client.post("/api/recommendations", json={"products": []}).status_code == 422
