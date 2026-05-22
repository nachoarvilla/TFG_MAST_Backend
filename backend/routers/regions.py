from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Any, Literal

import models
from auth import get_current_user, is_admin_user
from database import get_db

router = APIRouter(prefix="/projects", tags=["regions"])


class CreateRegionRequest(BaseModel):
    page_number: int
    type: Literal["Polygon", "Polyline", "Rectangle"]
    coordinates: list[Any]


class UpdateRegionRequest(BaseModel):
    type: Literal["Polygon", "Polyline", "Rectangle"]
    coordinates: list[Any]


def is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def is_valid_coordinate(coordinate) -> bool:
    if isinstance(coordinate, list):
        return len(coordinate) == 2 and is_number(coordinate[0]) and is_number(coordinate[1])

    return False


def validate_region_coordinates(region_type: str, coordinates: list[Any]):
    if not isinstance(coordinates, list) or not coordinates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Coordinates must be a non-empty list",
        )

    if any(not is_valid_coordinate(coordinate) for coordinate in coordinates):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Each coordinate must be [[x, y], [x, y], ...] with numeric values",
        )

    if region_type == "Rectangle" and len(coordinates) != 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rectangle regions must have exactly 2 coordinates",
        )

    if region_type in ("Polygon", "Polyline") and len(coordinates) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Polygon and Polyline regions must have at least 2 coordinates",
        )


def can_create_regions(project: models.Project, current_user: models.User, db: Session) -> bool:
    if is_admin_user(current_user):
        return True

    if project.owner_id == current_user.id:
        return True

    user_access = db.query(models.ProjectUser).filter(
        models.ProjectUser.project_id == project.id,
        models.ProjectUser.user_id == current_user.id,
        models.ProjectUser.role.in_(("owner", "collaborator")),
    ).first()
    if user_access:
        return True

    team_access = db.query(models.ProjectTeam).join(
        models.TeamMember,
        models.TeamMember.team_id == models.ProjectTeam.team_id,
    ).filter(
        models.ProjectTeam.project_id == project.id,
        models.TeamMember.user_id == current_user.id,
        models.ProjectTeam.role == "collaborator",
    ).first()
    return team_access is not None


def can_read_regions(project: models.Project, current_user: models.User, db: Session) -> bool:
    if is_admin_user(current_user):
        return True

    if not project.is_private:
        return True

    if project.owner_id == current_user.id:
        return True

    user_access = db.query(models.ProjectUser).filter(
        models.ProjectUser.project_id == project.id,
        models.ProjectUser.user_id == current_user.id,
    ).first()
    if user_access:
        return True

    team_access = db.query(models.ProjectTeam).join(
        models.TeamMember,
        models.TeamMember.team_id == models.ProjectTeam.team_id,
    ).filter(
        models.ProjectTeam.project_id == project.id,
        models.TeamMember.user_id == current_user.id,
    ).first()
    return team_access is not None


@router.post("/{project_id}/documents/{document_id}/regions", status_code=status.HTTP_201_CREATED)
def create_region(
    project_id: int,
    document_id: int,
    request: CreateRegionRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a region in a project document. Owners and collaborators can perform this action."""
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    if not can_create_regions(project, current_user, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only project owners and collaborators can create regions",
        )

    project_document = db.query(models.ProjectDocument).filter(
        models.ProjectDocument.project_id == project_id,
        models.ProjectDocument.document_id == document_id,
    ).first()
    if not project_document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document is not added to this project",
        )

    validate_region_coordinates(request.type, request.coordinates)

    region = models.Region(
        project_document_id=project_document.id,
        page_number=request.page_number,
        type=request.type,
        coordinates=request.coordinates,
    )
    db.add(region)
    db.commit()
    db.refresh(region)

    return {
        "id": region.id,
        "project_id": project_id,
        "document_id": document_id,
        "project_document_id": region.project_document_id,
        "page_number": region.page_number,
        "type": region.type,
        "coordinates": region.coordinates,
    }


@router.put("/{project_id}/documents/{document_id}/regions/{region_id}")
def update_region(
    project_id: int,
    document_id: int,
    region_id: int,
    request: UpdateRegionRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a region's type and coordinates. Owners and collaborators can perform this action."""
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    if not can_create_regions(project, current_user, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only project owners and collaborators can update regions",
        )

    project_document = db.query(models.ProjectDocument).filter(
        models.ProjectDocument.project_id == project_id,
        models.ProjectDocument.document_id == document_id,
    ).first()
    if not project_document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document is not added to this project",
        )

    region = db.query(models.Region).filter(
        models.Region.id == region_id,
        models.Region.project_document_id == project_document.id,
    ).first()
    if not region:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Region not found",
        )

    validate_region_coordinates(request.type, request.coordinates)

    region.type = request.type
    region.coordinates = request.coordinates
    db.commit()
    db.refresh(region)

    return {
        "project_document_id": region.project_document_id,
        "page_number": region.page_number,
        "type": region.type,
        "coordinates": region.coordinates,
    }


@router.get("/{project_id}/documents/{document_id}/regions/{region_id}")
def get_region(
    project_id: int,
    document_id: int,
    region_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a region from a project document."""
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    if not can_read_regions(project, current_user, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this project",
        )

    project_document = db.query(models.ProjectDocument).filter(
        models.ProjectDocument.project_id == project_id,
        models.ProjectDocument.document_id == document_id,
    ).first()
    if not project_document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document is not added to this project",
        )

    region = db.query(models.Region).filter(
        models.Region.id == region_id,
        models.Region.project_document_id == project_document.id,
    ).first()
    if not region:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Region not found",
        )

    return {
        "project_document_id": region.project_document_id,
        "page_number": region.page_number,
        "type": region.type,
        "coordinates": region.coordinates,
    }


@router.delete("/{project_id}/documents/{document_id}/regions/{region_id}", status_code=status.HTTP_200_OK)
def delete_region(
    project_id: int,
    document_id: int,
    region_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a region from a project document. Owners and collaborators can perform this action."""
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    if not can_create_regions(project, current_user, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only project owners and collaborators can delete regions",
        )

    project_document = db.query(models.ProjectDocument).filter(
        models.ProjectDocument.project_id == project_id,
        models.ProjectDocument.document_id == document_id,
    ).first()
    if not project_document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document is not added to this project",
        )

    region = db.query(models.Region).filter(
        models.Region.id == region_id,
        models.Region.project_document_id == project_document.id,
    ).first()
    if not region:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Region not found",
        )

    db.delete(region)
    db.commit()

    return {
        "message": "Region deleted successfully",
        "region_id": region_id,
    }
