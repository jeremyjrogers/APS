from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.planning.engine import run_planning

router = APIRouter(prefix="/planning", tags=["planning"])


@router.post("/run")
def run(db: Session = Depends(get_db)) -> dict:
    return run_planning(db)
