from fastapi import APIRouter, Depends

from app.auth import require_permission
from app.data.store import reference_date
from app.query.fields import FIELDS
from app.query.model import default_period

router = APIRouter(prefix="/api/query", tags=["query"], dependencies=[Depends(require_permission("explorer:use"))])


@router.get("/schema")
def schema() -> dict:
    date_from, date_to = default_period()
    return {
        "fields": [f.schema() for f in FIELDS.values()],
        "reference_date": reference_date().isoformat(),
        "default_period": {"from": date_from.isoformat(), "to": date_to.isoformat()},
    }
