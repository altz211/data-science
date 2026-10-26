import json
from functools import lru_cache
import joblib
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from retail.paths import ARTIFACTS, ROOT
from retail.recommend import recommend

app = FastAPI(title='Retail Intelligence', version='0.1.0')


@lru_cache
def state():
    snapshot = json.loads((ROOT/'web/assets/results.json').read_text())
    model_file = ARTIFACTS/'recommendations.joblib'
    return snapshot, joblib.load(model_file) if model_file.exists() else None


@app.get('/api/health')
def health():
    return {'status': 'ok', 'results_available': (ROOT/'web/assets/results.json').exists()}


@app.get('/api/results')
def results():
    return state()[0]


@app.get('/api/recommendations/{customer}')
def recommendations(customer: str):
    snapshot, model = state()
    if model is None:
        raise HTTPException(503, 'Run python -m retail.pipeline to generate the local model and customer examples.')
    if customer not in snapshot['customers']:
        raise HTTPException(404, 'Customer not found')
    profile = snapshot['customers'][customer]
    return {'customer': customer, 'as_of': model['cutoff'],
            'products': recommend(model, profile['history'])}

app.mount('/', StaticFiles(directory=ROOT/'web', html=True), name='web')
