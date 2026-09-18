from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from app.database import get_session
from app.dependencies import get_current_user
from app.dtos.requests import ActiveUpdateRequest, RoleUpdateRequest
from app.dtos.responses import UserResponse
from app.enums import Role
from app.models import User

router = APIRouter(prefix="/users", tags=["users"])


def get_current_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != Role.admin:
        raise HTTPException(
            status_code=403,
            detail="The user doesn't have enough privileges",
        )
    return current_user


@router.get("/", response_model=list[UserResponse])
def get_users(
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    users = session.exec(select(User)).all()
    return users


@router.patch("/{user_id}/role", response_model=UserResponse)
def update_user_role(
    user_id: int,
    role_in: RoleUpdateRequest,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    user.role = role_in.role
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.patch("/{user_id}/active", response_model=UserResponse)
def update_user_active_status(
    user_id: int,
    active_in: ActiveUpdateRequest,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    user.is_active = active_in.is_active
    session.add(user)
    session.commit()
    session.refresh(user)
    return user