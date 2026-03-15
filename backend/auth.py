import os
from datetime import datetime, timedelta
from typing import Optional

import argon2
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from database import SessionLocal
from models import User

# Configuration for Argon2
ph = argon2.PasswordHasher()

# Configuration for JWT
SECRET_KEY = os.getenv("SECRET_KEY", "secret_key_for_JWT_hashing")  # We can change in production
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

def hash_password(password: str) -> str:
    """Hash a password using Argon2."""
    return ph.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash."""
    try:
        ph.verify(hashed, password)
        return True
    except argon2.exceptions.VerifyMismatchError:
        return False

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create an access JWT token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Optional[dict]:
    """Verify and decode a JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

def get_current_user(token: str) -> Optional[User]:
    """Get the current user from the JWT token."""
    payload = verify_token(token)
    if payload is None:
        return None
    username: str = payload.get("sub")
    if username is None:
        return None
    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        return user
    finally:
        db.close()