from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/pipeline")
def pipeline(request: Request):
    return templates.TemplateResponse(request, "pipeline.html")
