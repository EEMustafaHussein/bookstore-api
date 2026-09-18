from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.database import get_session
from app.dependencies import require_roles
from app.dtos.requests import GenreCreateRequest
from app.dtos.responses import GenreResponse
from app.enums import Role
from app.models import Genre, User

router = APIRouter(prefix="/genres", tags=["genres"])

staff_or_admin = require_roles([Role.staff, Role.admin])
admin_only = require_roles([Role.admin])


@router.get("", response_model=list[GenreResponse])
def list_genres(session: Session = Depends(get_session)):
    return session.exec(select(Genre).order_by(Genre.name)).all()


@router.post("", response_model=GenreResponse, status_code=201)
def create_genre(
    new_genre: GenreCreateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(staff_or_admin),
):
    if session.exec(select(Genre).where(Genre.name == new_genre.name)).first():
        raise HTTPException(status_code=409, detail="That genre already exists")
    genre = Genre(name=new_genre.name)
    session.add(genre)
    session.commit()
    session.refresh(genre)
    return genre


@router.delete("/{genre_id}", status_code=204)
def delete_genre(
    genre_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(admin_only),
):
    genre = session.get(Genre, genre_id)
    if genre is None:
        raise HTTPException(status_code=404, detail="Genre not found")
    if genre.books:
        raise HTTPException(
            status_code=409,
            detail="This genre still has books. Delete or reassign them first.",
        )
    session.delete(genre)
    session.commit()