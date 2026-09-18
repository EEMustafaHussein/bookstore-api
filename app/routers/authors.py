from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, func, select
from app.database import get_session
from app.dependencies import require_roles
from app.dtos.requests import AuthorCreateRequest, AuthorProfileRequest
from app.dtos.responses import AuthorListItemResponse, AuthorResponse
from app.enums import Role
from app.models import Author, AuthorProfile, Book, User

router = APIRouter(prefix="/authors", tags=["authors"])

staff_or_admin = require_roles([Role.staff, Role.admin])
admin_only = require_roles([Role.admin])


def get_author_or_404(session, author_id):
    author = session.get(Author, author_id)
    if author is None:
        raise HTTPException(status_code=404, detail="Author not found")
    return author


@router.get("", response_model=list[AuthorListItemResponse])
def list_authors(has_books: bool = False, session: Session = Depends(get_session)):
    query = select(Author, func.count(Book.id))
    if has_books:
        query = query.join(Book)
    else:
        query = query.outerjoin(Book)
    query = query.group_by(Author.id).order_by(Author.id)

    return [
        AuthorListItemResponse(id=author.id, name=author.name, book_count=book_count)
        for author, book_count in session.exec(query).all()
    ]


@router.get("/{author_id}", response_model=AuthorResponse)
def get_author(author_id: int, session: Session = Depends(get_session)):
    return get_author_or_404(session, author_id)


@router.post("", response_model=AuthorResponse, status_code=201)
def create_author(
    new_author: AuthorCreateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(staff_or_admin),
):
    author = Author.model_validate(new_author.model_dump())
    session.add(author)
    session.commit()
    session.refresh(author)
    return author


@router.put("/{author_id}/profile", response_model=AuthorResponse)
def set_author_profile(
    author_id: int,
    profile: AuthorProfileRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(staff_or_admin),
):
    author = get_author_or_404(session, author_id)
    if author.profile is None:
        author.profile = AuthorProfile(
            author_id=author.id, bio=profile.bio, website=profile.website
        )
    else:
        author.profile.bio = profile.bio
        author.profile.website = profile.website
    session.add(author)
    session.commit()
    session.refresh(author)
    return author


@router.delete("/{author_id}", status_code=204)
def delete_author(
    author_id: int,
    session: Session,
    current_user: User = Depends(admin_only),
):
    author = get_author_or_404(session, author_id)
    if author.books:
        raise HTTPException(
            status_code=409,
            detail="This author still has books. Delete or reassign them first.",
        )
    session.delete(author)
    session.commit()