from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.routes import (
    assumptions,
    brief,
    dashboard,
    intelligence,
    localisation,
    pipeline,
    recommendations,
    resources,
    timeline,
)

app = FastAPI(title="CreativeOps Studio")

app.include_router(dashboard.router)
app.include_router(pipeline.router)
app.include_router(resources.router)
app.include_router(brief.router)
app.include_router(intelligence.router)
app.include_router(recommendations.router)
app.include_router(localisation.router)
app.include_router(timeline.router)
app.include_router(assumptions.router)


@app.get("/")
def root():
    return RedirectResponse(url="/dashboard")


@app.get("/health")
def health():
    return {"status": "ok"}
