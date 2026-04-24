from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

import models
from auth import get_current_user
from database import get_db

router = APIRouter(prefix="/projects", tags=["projects"])

class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    is_private: bool = True

class ProjectUpdate(BaseModel):
    name: str
    description: str = ""
    is_private: bool = True


class AddUserRequest(BaseModel):
    username: str
    role: str


class AddTeamRequest(BaseModel):
    team_name: str
    role: str


@router.post("", status_code=status.HTTP_201_CREATED)
def create_project(project: ProjectCreate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Create a new project. The creator becomes the owner."""
    # Check if project name already exists
    existing = db.query(models.Project).filter(models.Project.name == project.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A project with this name already exists",
        )

    # Create the project
    project_obj = models.Project(
        name=project.name,
        description=project.description,
        is_private=project.is_private,
        owner_id=current_user.id
    )
    db.add(project_obj)
    db.commit()
    db.refresh(project_obj)

    return {
        "id": project_obj.id,
        "name": project_obj.name,
        "description": project_obj.description,
        "is_private": project_obj.is_private,
        "owner_id": project_obj.owner_id
    }


@router.post("/{project_id}/users", status_code=status.HTTP_201_CREATED)
def add_user_to_project(
    project_id: int,
    request: AddUserRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add a user to a project. Only the owner can perform this action."""
    # Check if project exists
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Check if current user is the owner
    if project.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the project owner can add users",
        )

    # Validate role
    if request.role not in ("collaborator", "viewer"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role must be 'collaborator' or 'viewer'",
        )

    # Find the user to add
    user_to_add = db.query(models.User).filter(models.User.username == request.username).first()
    if not user_to_add:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Check if user is the owner
    if user_to_add.id == project.owner_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot add the project owner as a member",
        )

    # Check if user is already a member
    existing_membership = db.query(models.ProjectUser).filter(
        models.ProjectUser.project_id == project_id,
        models.ProjectUser.user_id == user_to_add.id
    ).first()
    if existing_membership:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a member of this project",
        )

    # Add the user to the project
    project_user = models.ProjectUser(
        project_id=project_id,
        user_id=user_to_add.id,
        role=request.role
    )
    db.add(project_user)
    db.commit()
    db.refresh(project_user)

    return {
        "message": f"User {request.username} added to project {project.name} as {request.role}",
    }


@router.get("")
def list_projects(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """List all projects where the user has access (owner or invited)."""
    # Get projects where user is owner
    owned_projects = db.query(models.Project).filter(models.Project.owner_id == current_user.id).all()

    # Get projects where user is directly invited
    invited_projects = db.query(models.Project).join(models.ProjectUser).filter(
        models.ProjectUser.user_id == current_user.id
    ).all()

    # Get projects where user is member of an invited team
    team_projects = db.query(models.Project).join(models.ProjectTeam).join(models.TeamMember, models.TeamMember.team_id == models.ProjectTeam.team_id).filter(
        models.TeamMember.user_id == current_user.id
    ).all()

    # Combine and deduplicate
    all_projects = owned_projects + invited_projects + team_projects
    unique_projects = list(set(all_projects))

    result = []
    for project in unique_projects:
        # Determine user's role in this project
        role = "viewer"  # default

        if project.owner_id == current_user.id:
            role = "owner"
        else:
            # Check direct user access
            user_access = db.query(models.ProjectUser).filter(
                models.ProjectUser.project_id == project.id,
                models.ProjectUser.user_id == current_user.id
            ).first()
            if user_access:
                role = user_access.role
            else:
                # Check team access
                team_access = db.query(models.ProjectTeam).join(models.TeamMember, models.TeamMember.team_id == models.ProjectTeam.team_id).filter(
                    models.ProjectTeam.project_id == project.id,
                    models.TeamMember.user_id == current_user.id
                ).first()
                if team_access:
                    role = team_access.role

        result.append({
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "is_private": project.is_private,
            "owner_id": project.owner_id,
            "user_role": role
        })

    return {"projects": result}


@router.get("/{project_id}")
def get_project(project_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get details of a specific project."""
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Check if user has access
    has_access = False
    user_role = "viewer"

    if project.owner_id == current_user.id:
        has_access = True
        user_role = "owner"
    else:
        # Check direct user access
        user_access = db.query(models.ProjectUser).filter(
            models.ProjectUser.project_id == project.id,
            models.ProjectUser.user_id == current_user.id
        ).first()
        if user_access:
            has_access = True
            user_role = user_access.role
        else:
            # Check team access
            team_access = db.query(models.ProjectTeam).join(models.TeamMember, models.TeamMember.team_id == models.ProjectTeam.team_id).filter(
                models.ProjectTeam.project_id == project.id,
                models.TeamMember.user_id == current_user.id
            ).first()
            if team_access:
                has_access = True
                user_role = team_access.role

    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this project",
        )

    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "is_private": project.is_private,
        "owner_id": project.owner_id,
        "user_role": user_role
    }


@router.put("/{project_id}")
def update_project(project_id: int, project_update: ProjectUpdate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Update a project. Only the owner can perform this action."""
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Check if user is the owner
    if project.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the project owner can update the project",
        )

    # Check if new name conflicts with existing projects
    if project_update.name != project.name:
        existing = db.query(models.Project).filter(
            models.Project.name == project_update.name,
            models.Project.id != project_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A project with this name already exists",
            )

    # Update the project
    project.name = project_update.name
    project.description = project_update.description
    project.is_private = project_update.is_private
    db.commit()
    db.refresh(project)

    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "is_private": project.is_private,
        "owner_id": project.owner_id
    }


@router.delete("/{project_id}")
def delete_project(project_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Delete a project. Only the owner can perform this action."""
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Check if user is the owner
    if project.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the project owner can delete the project",
        )

    # Delete the project (cascade will handle related records)
    db.delete(project)
    db.commit()

    return {"message": f"Project '{project.name}' deleted successfully"}


@router.post("/{project_id}/teams", status_code=status.HTTP_201_CREATED)
def add_team_to_project(
    project_id: int,
    request: AddTeamRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add a team to a project. Only the owner can perform this action."""
    # Check if project exists
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Check if current user is the owner
    if project.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the project owner can add teams",
        )

    # Validate role
    if request.role not in ("collaborator", "viewer"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role must be 'collaborator' or 'viewer'",
        )

    # Find the team to add
    team_to_add = db.query(models.Team).filter(models.Team.name == request.team_name).first()
    if not team_to_add:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    # Check if team is already a member
    existing_membership = db.query(models.ProjectTeam).filter(
        models.ProjectTeam.project_id == project_id,
        models.ProjectTeam.team_id == team_to_add.id
    ).first()
    if existing_membership:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Team is already a member of this project",
        )

    # Add the team to the project
    project_team = models.ProjectTeam(
        project_id=project_id,
        team_id=team_to_add.id,
        role=request.role
    )
    db.add(project_team)
    db.commit()
    db.refresh(project_team)

    return {
        "message": f"Team {request.team_name} added to project {project.name} as {request.role}",
        "team_id": team_to_add.id,
        "team_name": team_to_add.name,
        "role": request.role
    }


@router.get("/user/{user_id}/projects")
def get_user_projects(
    user_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all projects where a user is involved and their role."""
    # Check if user exists
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    result = []

    # Get projects where user is owner
    owned_projects = db.query(models.Project).filter(models.Project.owner_id == user_id).all()
    for project in owned_projects:
        result.append({
            "project_id": project.id,
            "project_name": project.name,
            "role": "owner"
        })

    # Get projects where user is directly invited
    user_memberships = db.query(models.ProjectUser).filter(models.ProjectUser.user_id == user_id).all()
    for membership in user_memberships:
        project = db.query(models.Project).filter(models.Project.id == membership.project_id).first()
        if project:
            result.append({
                "project_id": project.id,
                "project_name": project.name,
                "role": membership.role
            })

    # Get projects where user is member of a team
    team_memberships = db.query(models.TeamMember).filter(models.TeamMember.user_id == user_id).all()
    for team_membership in team_memberships:
        project_teams = db.query(models.ProjectTeam).filter(models.ProjectTeam.team_id == team_membership.team_id).all()
        for pt in project_teams:
            project = db.query(models.Project).filter(models.Project.id == pt.project_id).first()
            if project:
                # Check if not already added
                if not any(p["project_id"] == project.id for p in result):
                    result.append({
                        "project_id": project.id,
                        "project_name": project.name,
                        "role": pt.role
                    })

    return {"user_id": user_id, "username": user.username, "projects": result}