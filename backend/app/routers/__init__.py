from fastapi import APIRouter

from app.routers import (
    batches,
    curated,
    dashboard,
    datasets,
    inspect,
    quarantine,
    rule_packs,
    rules,
)

api = APIRouter(prefix="/api")
api.include_router(dashboard.router)
api.include_router(datasets.router)
api.include_router(rules.router)
api.include_router(rule_packs.router)
api.include_router(inspect.router)
api.include_router(batches.router)
api.include_router(quarantine.router)
api.include_router(curated.router)
