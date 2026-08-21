from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/brief")
def brief(request: Request):
    return templates.TemplateResponse(request, "brief.html")
