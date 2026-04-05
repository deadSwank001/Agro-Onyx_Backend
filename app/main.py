from fastapi import FastAPI
from app.routers import auth, routes

app = FastAPI(title="2-leg Swap Aggregator (Build-Only)", version="0.1.0")

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(routes.router, prefix="/v1", tags=["aggregator"])


@app.get("/health")
def health():
    return {"ok": True}
