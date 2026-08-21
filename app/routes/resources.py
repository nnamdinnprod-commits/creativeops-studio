from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/resources")
def resources(request: Request):
    return templates.TemplateResponse(request, "resources.html")
