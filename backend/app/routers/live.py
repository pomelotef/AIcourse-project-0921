"""GET /api/stream: one Server-Sent Events connection per open tab (see app/live.py)."""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from .. import live
from ..db import get_db
from ..models import User
from ..security import current_user

router = APIRouter(prefix="/api", tags=["live"])


@router.get("/stream")
def stream(db: Session = Depends(get_db), user: User = Depends(current_user)):
    user_id = user.id
    # The stream stays open for hours; do not hold a DB connection (and SQLite read lock) that long.
    db.close()
    return StreamingResponse(
        live.stream(user_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
