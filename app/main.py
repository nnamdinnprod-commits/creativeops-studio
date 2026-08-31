import logging

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse

from app.config import settings
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

logging.basicConfig(level=settings.log_level)
ref_logger = logging.getLogger("creativeops.ref")

app = FastAPI(title="CreativeOps Studio")


# REVIEW_02.md P7 "Per-application tracking": a `?ref=` link per application sent
# out, counted by grepping Render's log viewer for `ref=<value>` — not IP logging,
# which is personal data under GDPR and doesn't reliably identify anyone anyway.
@app.middleware("http")
async def log_ref_hits(request: Request, call_next):
    ref = request.query_params.get("ref")
    if ref:
        ref_logger.info("ref hit: ref=%s path=%s", ref, request.url.path)
    return await call_next(request)

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
