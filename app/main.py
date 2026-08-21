from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.routes import brief, dashboard, intelligence, pipeline, recommendations, resources

app = FastAPI(title="CreativeOps Studio")

app.include_router(dashboard.router)
app.include_router(pipeline.router)
app.include_router(resources.router)
app.include_router(brief.router)
app.include_router(intelligence.router)
app.include_router(recommendations.router)


@app.get("/")
def root():
    return RedirectResponse(url="/dashboard")


@app.get("/health")
def health():
    return {"status": "ok"}
