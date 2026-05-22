from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

import models
from auth import get_current_user, hash_password, is_admin_user
from database import get_db

router = APIRouter()


class UserUpdate(BaseModel):
    username: str | None = None
    email: EmailStr | None = None
    password: str | None = None


@router.get("/users/{user_id}")
def get_user(user_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Return user information for an authenticated request."""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
    }


@router.put("/users/{user_id}")
def update_user(user_id: int, user_update: UserUpdate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Update user information. Only the user themselves or root can update."""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    if current_user.id != user_id and not is_admin_user(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the user, root or admin can update this account")

    if user_update.username and user_update.username != user.username:
        existing = db.query(models.User).filter(models.User.username == user_update.username).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken")
        user.username = user_update.username

    if user_update.email and user_update.email != user.email:
        existing = db.query(models.User).filter(models.User.email == user_update.email).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already taken")
        user.email = user_update.email

    if user_update.password:
        user.password_hash = hash_password(user_update.password)

    db.commit()
    db.refresh(user)
    return {"id": user.id, "username": user.username, "email": user.email, "role": user.role}


@router.delete("/users/{user_id}")
def delete_user(user_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Delete a user. Only the user themselves or root can delete."""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    if current_user.id != user_id and not is_admin_user(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the user, root or admin can delete this account")

    db.delete(user)
    db.commit()
    return {"message": f"User {user.username} deleted successfully"}
