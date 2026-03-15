from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

import models
from auth import hash_password
from database import SessionLocal, engine

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="MAST Backend API")


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.post("/register", status_code=status.HTTP_201_CREATED)
def register(user: UserCreate, db: Session = Depends(get_db)):
    """Register a new user (hash the password)."""
    existing = (
        db.query(models.User)
        .filter((models.User.username == user.username) | (models.User.email == user.email))
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The username or email is already in use",
        )

    user_obj = models.User(
        username=user.username,
        email=user.email,
        password_hash=hash_password(user.password),
    )
    db.add(user_obj)
    db.commit()
    db.refresh(user_obj)

    return {"id": user_obj.id, "username": user_obj.username, "email": user_obj.email}


@app.get("/")
def read_root():
    return {"message": "Welcome to the MAST backend", "status": "online"}

@app.get("/health")
def health_check():
    return {"database": "connected_placeholder", "api": "running"}