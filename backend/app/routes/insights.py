from fastapi import APIRouter, Query
from app.services.cricket_trends import get_ipl_chasing_bias_insight

router = APIRouter()

@router.get("/cricket/ipl/chasing-bias")
def cricket_chasing_bias(history_limit: int = Query(default=3, ge=1, le=50)):
    return get_ipl_chasing_bias_insight(history_limit=history_limit)