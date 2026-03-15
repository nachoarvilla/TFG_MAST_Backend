from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

import models
from auth import create_access_token, hash_password, verify_password
from database import SessionLocal, engine

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="MAST Backend API")


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    username_or_email: str
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

@app.post("/login")
def login(user: UserLogin, db: Session = Depends(get_db)):
    """Authenticate user and return JWT token."""
    # Find user by username or email
    db_user = (
        db.query(models.User)
        .filter(
            (models.User.username == user.username_or_email) |
            (models.User.email == user.username_or_email)
        )
        .first()
    )
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    # Verify password
    if not verify_password(user.password, db_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    # Create access token
    access_token = create_access_token(data={"sub": db_user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/")
def read_root():
    return {"message": "Welcome to the MAST backend", "status": "online"}

@app.get("/health")
def health_check():
    return {"database": "connected_placeholder", "api": "running"}