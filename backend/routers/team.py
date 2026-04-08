from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

import models
from auth import get_current_user
from database import get_db

router = APIRouter()


class TeamCreate(BaseModel):
    name: str
    description: str


class AddMemberRequest(BaseModel):
    username: str


@router.post("/teams", status_code=status.HTTP_201_CREATED)
def create_team(team: TeamCreate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    existing_team = db.query(models.Team).filter(models.Team.name == team.name).first()
    if existing_team:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A team with this name already exists",
        )

    team_obj = models.Team(name=team.name, description=team.description)
    db.add(team_obj)
    db.commit()
    db.refresh(team_obj)

    member = models.TeamMember(team_id=team_obj.id, user_id=current_user.id, role="leader")
    db.add(member)
    db.commit()

    return {"id": team_obj.id, "name": team_obj.name, "description": team_obj.description}


@router.post("/teams/{team_id}/members", status_code=status.HTTP_201_CREATED)
def add_team_member(team_id: int, request: AddMemberRequest, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    team = db.query(models.Team).filter(models.Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    leader_membership = db.query(models.TeamMember).filter(
        models.TeamMember.team_id == team_id,
        models.TeamMember.user_id == current_user.id,
        models.TeamMember.role == "leader"
    ).first()
    if not leader_membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the team leader can add members")

    user_to_add = db.query(models.User).filter(models.User.username == request.username).first()
    if not user_to_add:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    existing_membership = db.query(models.TeamMember).filter(
        models.TeamMember.team_id == team_id,
        models.TeamMember.user_id == user_to_add.id
    ).first()
    if existing_membership:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is already a member of this team")

    member = models.TeamMember(team_id=team_id, user_id=user_to_add.id, role="member")
    db.add(member)
    db.commit()

    return {"message": f"User {request.username} added to team {team.name} as member"}


@router.delete("/teams/{team_id}/members", status_code=status.HTTP_200_OK)
def remove_team_member(team_id: int, request: AddMemberRequest, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    team = db.query(models.Team).filter(models.Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    leader_membership = db.query(models.TeamMember).filter(
        models.TeamMember.team_id == team_id,
        models.TeamMember.user_id == current_user.id,
        models.TeamMember.role == "leader"
    ).first()
    if not leader_membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the team leader can remove members")

    user_to_remove = db.query(models.User).filter(models.User.username == request.username).first()
    if not user_to_remove:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    membership = db.query(models.TeamMember).filter(
        models.TeamMember.team_id == team_id,
        models.TeamMember.user_id == user_to_remove.id
    ).first()
    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User is not a member of this team")

    if membership.role == "leader":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot remove the team leader")

    db.delete(membership)
    db.commit()

    return {"message": f"User {request.username} removed from team {team.name}"}


@router.delete("/teams/{team_id}", status_code=status.HTTP_200_OK)
def delete_team(team_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    team = db.query(models.Team).filter(models.Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    leader_membership = db.query(models.TeamMember).filter(
        models.TeamMember.team_id == team_id,
        models.TeamMember.user_id == current_user.id,
        models.TeamMember.role == "leader"
    ).first()
    if not leader_membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the team leader can delete the team")

    db.query(models.TeamMember).filter(models.TeamMember.team_id == team_id).delete()
    db.delete(team)
    db.commit()

    return {"message": f"Team {team.name} deleted successfully"}


@router.get("/teams/{team_id}/members", status_code=status.HTTP_200_OK)
def list_team_members(team_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    team = db.query(models.Team).filter(models.Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    memberships = db.query(models.TeamMember).filter(models.TeamMember.team_id == team_id).all()
    result = []
    for membership in memberships:
        user = db.query(models.User).filter(models.User.id == membership.user_id).first()
        if user:
            result.append({"username": user.username, "role": membership.role})

    return {"team_id": team_id, "team_name": team.name, "members": result}
