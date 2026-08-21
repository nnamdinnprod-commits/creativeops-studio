from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/intelligence")
def intelligence(request: Request):
    return templates.TemplateResponse(request, "intelligence.html")
