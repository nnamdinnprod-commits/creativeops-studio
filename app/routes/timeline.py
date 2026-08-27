from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.templates_env import templates
from app.models import Person, Project, ProjectPhase, ProjectType
from app.services.timeline import build_timeline

router = APIRouter()


@router.get("/timeline")
def timeline(request: Request, brand: str | None = None, market: str | None = None,
            project_type: str | None = None, owner: str | None = None,
            db: Session = Depends(get_db)):
    scheduled_ids = [row[0] for row in db.query(ProjectPhase.project_id).distinct().all()]
    scheduled_projects = db.query(Project).filter(Project.id.in_(scheduled_ids)).all()
    people_by_id = {p.id: p for p in db.query(Person).all()}

    projects = scheduled_projects
    if brand:
        projects = [p for p in projects if p.brand == brand]
    if market:
        projects = [p for p in projects if p.source_market == market]
    if project_type:
        projects = [p for p in projects if p.project_type_id == int(project_type)]
    if owner:
        projects = [p for p in projects if p.owner_id == int(owner)]

    projects_with_phases = []
    for project in sorted(projects, key=lambda p: p.deadline):
        phases = (
            db.query(ProjectPhase)
            .filter_by(project_id=project.id)
            .order_by(ProjectPhase.start_date, ProjectPhase.id)
            .all()
        )
        projects_with_phases.append((project, phases))

    context = build_timeline(projects_with_phases)

    owners = sorted(
        {people_by_id[p.owner_id] for p in scheduled_projects if p.owner_id in people_by_id},
        key=lambda person: person.name,
    )

    return templates.TemplateResponse(request, "timeline.html", {
        "timeline": context,
        "all_brands": sorted({p.brand for p in scheduled_projects}),
        "all_markets": sorted({p.source_market for p in scheduled_projects}),
        "project_types": db.query(ProjectType).order_by(ProjectType.name).all(),
        "owners": owners,
        "selected_brand": brand,
        "selected_market": market,
        "selected_project_type": project_type,
        "selected_owner": owner,
        "has_any_schedules": len(scheduled_projects) > 0,
    })
