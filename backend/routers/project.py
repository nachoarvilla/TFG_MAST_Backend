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