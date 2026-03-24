from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

import models
from auth import create_access_token, get_current_user, hash_password, verify_password
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


class TeamCreate(BaseModel):
    name: str
    description: str


class AddMemberRequest(BaseModel):
    username: str


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


@app.post("/teams", status_code=status.HTTP_201_CREATED)
def create_team(team: TeamCreate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Create a new team. The creator becomes the leader."""
    # Check if team name already exists
    existing_team = db.query(models.Team).filter(models.Team.name == team.name).first()
    if existing_team:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A team with this name already exists",
        )

    # Create the team
    team_obj = models.Team(name=team.name, description=team.description)
    db.add(team_obj)
    db.commit()
    db.refresh(team_obj)

    # Add the creator as leader
    member = models.TeamMember(team_id=team_obj.id, user_id=current_user.id, role="leader")
    db.add(member)
    db.commit()

    return {"id": team_obj.id, "name": team_obj.name, "description": team_obj.description}


@app.post("/teams/{team_id}/members", status_code=status.HTTP_201_CREATED)
def add_team_member(team_id: int, request: AddMemberRequest, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Add a member to a team. Only the team leader can perform this action."""
    # Check if the team exists
    team = db.query(models.Team).filter(models.Team.id == team_id).first()
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    # Check if current user is the leader of the team
    leader_membership = db.query(models.TeamMember).filter(
        models.TeamMember.team_id == team_id,
        models.TeamMember.user_id == current_user.id,
        models.TeamMember.role == "leader"
    ).first()
    if not leader_membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the team leader can add members",
        )

    # Find the user to add
    user_to_add = db.query(models.User).filter(models.User.username == request.username).first()
    if not user_to_add:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Check if user is already a member
    existing_membership = db.query(models.TeamMember).filter(
        models.TeamMember.team_id == team_id,
        models.TeamMember.user_id == user_to_add.id
    ).first()
    if existing_membership:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a member of this team",
        )

    # Add the user as a member
    member = models.TeamMember(team_id=team_id, user_id=user_to_add.id, role="member")
    db.add(member)
    db.commit()

    return {"message": f"User {request.username} added to team {team.name} as member"}