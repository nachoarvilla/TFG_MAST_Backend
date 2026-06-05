from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

import models
from auth import get_current_user, is_admin_user
from database import get_db

router = APIRouter(prefix="/projects", tags=["annotations"])


class CreateAnnotationRequest(BaseModel):
    schema_publication_id: int


def can_create_annotations(project: models.Project, current_user: models.User, db: Session) -> bool:
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


def _get_root_publication(db: Session, publication: models.SchemaPublication) -> models.SchemaPublication:
    while publication.parent_id is not None:
        publication = db.get(models.SchemaPublication, publication.parent_id)
        if publication is None:
            break
    return publication


def _has_project_member(project: models.Project, current_user: models.User, db: Session) -> bool:
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


@router.post("/{project_id}/documents/{document_id}/regions/{region_id}/annotations", status_code=status.HTTP_201_CREATED)
def create_annotation(
    project_id: int,
    document_id: int,
    region_id: int,
    request: CreateAnnotationRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create an annotation in a project region. Only owners and collaborators can perform this action."""
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    if not can_create_annotations(project, current_user, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only project owners and collaborators can create annotations",
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

    schema_publication = db.query(models.SchemaPublication).filter(
        models.SchemaPublication.id == request.schema_publication_id
    ).first()
    if not schema_publication:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schema publication not found",
        )

    if schema_publication.type != "annotation":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Schema publication must be of type 'annotation'",
        )

    root_publication = _get_root_publication(db, schema_publication)
    if root_publication is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid schema publication hierarchy",
        )

    project_schema_publication = db.query(models.ProjectSchemaPublication).filter(
        models.ProjectSchemaPublication.project_id == project_id,
        models.ProjectSchemaPublication.schema_publication_id == root_publication.id,
    ).first()
    if not project_schema_publication:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Schema publication is not associated with this project",
        )

    annotation = models.Annotation(
        region_id=region.id,
        schema_publication_id=schema_publication.id,
        root_schema_publication_id=root_publication.id,
    )
    db.add(annotation)
    db.commit()
    db.refresh(annotation)

    return {
        "id": annotation.id,
        "project_id": project_id,
        "document_id": document_id,
        "region_id": region_id,
        "schema_publication_id": annotation.schema_publication_id,
        "root_schema_publication_id": annotation.root_schema_publication_id,
        "created_date": annotation.created_date,
    }


@router.get("/{project_id}/documents/{document_id}/regions/{region_id}/annotations", status_code=200)
def list_region_annotations(
    project_id: int,
    document_id: int,
    region_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Verify project and membership (any role allowed)
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    if not _has_project_member(project, current_user, db) and not is_admin_user(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    project_document = db.query(models.ProjectDocument).filter(
        models.ProjectDocument.project_id == project_id,
        models.ProjectDocument.document_id == document_id,
    ).first()
    if not project_document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document is not added to this project")

    region = db.query(models.Region).filter(
        models.Region.id == region_id,
        models.Region.project_document_id == project_document.id,
    ).first()
    if not region:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Region not found")

    annotations = db.query(models.Annotation).filter(models.Annotation.region_id == region.id).all()
    results = []
    for a in annotations:
        sp = db.query(models.SchemaPublication).filter(models.SchemaPublication.id == a.schema_publication_id).first()
        results.append({
            "id": a.id,
            "project_id": project_id,
            "document_id": document_id,
            "region_id": region.id,
            "schema_publication_id": a.schema_publication_id,
            "root_schema_publication_id": a.root_schema_publication_id,
            "schema_publication_name": sp.name if sp else None,
            "created_date": a.created_date,
        })

    return results


@router.get("/annotations/{annotation_id}", status_code=200)
def get_annotation(
    annotation_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    annotation = db.query(models.Annotation).filter(models.Annotation.id == annotation_id).first()
    if not annotation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Annotation not found")

    region = db.query(models.Region).filter(models.Region.id == annotation.region_id).first()
    if not region:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Region not found")

    project_document = db.query(models.ProjectDocument).filter(models.ProjectDocument.id == region.project_document_id).first()
    if not project_document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project document not found")

    project = db.query(models.Project).filter(models.Project.id == project_document.project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    if not _has_project_member(project, current_user, db) and not is_admin_user(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    sp = db.query(models.SchemaPublication).filter(models.SchemaPublication.id == annotation.schema_publication_id).first()

    return {
        "id": annotation.id,
        "project_id": project.id,
        "document_id": project_document.document_id,
        "region_id": annotation.region_id,
        "schema_publication_id": annotation.schema_publication_id,
        "root_schema_publication_id": annotation.root_schema_publication_id,
        "schema_publication_name": sp.name if sp else None,
        "created_date": annotation.created_date,
    }


@router.delete("/annotations/{annotation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_annotation(
    annotation_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    annotation = db.query(models.Annotation).filter(models.Annotation.id == annotation_id).first()
    if not annotation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Annotation not found")

    region = db.query(models.Region).filter(models.Region.id == annotation.region_id).first()
    if not region:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Region not found")

    project_document = db.query(models.ProjectDocument).filter(models.ProjectDocument.id == region.project_document_id).first()
    if not project_document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project document not found")

    project = db.query(models.Project).filter(models.Project.id == project_document.project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    # Only owner or collaborator allowed to delete
    if not can_create_annotations(project, current_user, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only project owners and collaborators can delete annotations")

    db.delete(annotation)
    db.commit()

    return None
