from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from sqlmodel import Session

from app.config import settings
from app.database import get_session
from app.models import MediaFile

router = APIRouter()

# Every photo gets a new random name, so browsers may keep it for good.
CACHE_HEADERS = {"Cache-Control": "public, max-age=31536000, immutable"}


@router.get("/media/{name:path}")
def media(name: str, session: Session = Depends(get_session)):
    if settings.media_storage == "database":
        row = session.get(MediaFile, name[:120])
        if row is None:
            raise HTTPException(status_code=404, detail="الصورة غير موجودة")
        return Response(row.data, media_type=row.content_type, headers=CACHE_HEADERS)

    root = settings.media_dir.resolve()
    target = (root / name).resolve()
    if root not in target.parents or not target.is_file():
        raise HTTPException(status_code=404, detail="الصورة غير موجودة")
    return FileResponse(target, headers=CACHE_HEADERS)
