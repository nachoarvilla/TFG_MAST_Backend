from typing import List, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

import models
from auth import get_current_user
from database import get_db

router = APIRouter(prefix="/schemas", tags=["schemas"])


class AnnotationSchemaNode(BaseModel):
    name: str
    type: Literal["schema", "class", "annotation"]
    children: List["AnnotationSchemaNode"] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_children_for_annotation(self):
        if self.type == "annotation" and self.children:
            raise ValueError("Annotation nodes cannot have children")
        return self


AnnotationSchemaNode.update_forward_refs()


class AnnotationSchemaResponse(BaseModel):
    id: int
    name: str
    type: Literal["schema", "class", "annotation"]
    parent_id: int | None
    children: List["AnnotationSchemaResponse"] = Field(default_factory=list)

    class Config:
        orm_mode = True


AnnotationSchemaResponse.update_forward_refs()


SchemaPublicationResponse = AnnotationSchemaResponse


def _create_schema_node(
    node: AnnotationSchemaNode,
    current_user: models.User,
    db: Session,
    parent_id: int | None = None,
) -> dict:
    schema_obj = models.AnnotationSchema(
        name=node.name,
        type=node.type,
        parent_id=parent_id,
        user_creator_id=current_user.id,
    )
    db.add(schema_obj)
    db.flush()

    children = [
        _create_schema_node(child, current_user=current_user, db=db, parent_id=schema_obj.id)
        for child in node.children
    ]

    return {
        "id": schema_obj.id,
        "name": schema_obj.name,
        "type": schema_obj.type,
        "parent_id": schema_obj.parent_id,
        "children": children,
    }


def _build_schema_response(node: models.AnnotationSchema) -> dict:
    return {
        "id": node.id,
        "name": node.name,
        "type": node.type,
        "parent_id": node.parent_id,
        "children": [_build_schema_response(child) for child in node.children],
    }


def _build_publication_response(node: models.SchemaPublication) -> dict:
    return {
        "id": node.id,
        "name": node.name,
        "type": node.type,
        "parent_id": node.parent_id,
        "children": [_build_publication_response(child) for child in node.children],
    }


def _publish_schema_node(
    node: models.AnnotationSchema,
    annotation_schema_id: int,
    db: Session,
    parent_id: int | None = None,
    name_suffix: str | None = None,
) -> models.SchemaPublication:
    node_name = f"{node.name}{name_suffix}" if name_suffix else node.name
    publication_obj = models.SchemaPublication(
        name=node_name,
        type=node.type,
        parent_id=parent_id,
        annotation_schema_id=annotation_schema_id,
    )
    db.add(publication_obj)
    db.flush()

    for child in node.children:
        _publish_schema_node(
            child,
            annotation_schema_id=annotation_schema_id,
            db=db,
            parent_id=publication_obj.id,
        )

    return publication_obj


def _get_root_schema(db: Session, schema_id: int) -> models.AnnotationSchema:
    schema_obj = db.get(models.AnnotationSchema, schema_id)
    if not schema_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schema not found",
        )
    if schema_obj.type != "schema" or schema_obj.parent_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The provided id is not a root schema",
        )
    return schema_obj


@router.get("/{schema_id}", response_model=AnnotationSchemaResponse)
def get_annotation_schema(
    schema_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    schema_obj = _get_root_schema(db, schema_id)
    return _build_schema_response(schema_obj)


@router.post("/publish_annotation_schema/{schema_id}", status_code=status.HTTP_201_CREATED, response_model=SchemaPublicationResponse)
def publish_annotation_schema(
    schema_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    schema_obj = _get_root_schema(db, schema_id)
    if schema_obj.user_creator_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the schema owner can publish this schema",
        )

    version_count = (
        db.query(models.SchemaPublication)
        .filter(
            models.SchemaPublication.annotation_schema_id == schema_id,
            models.SchemaPublication.parent_id.is_(None),
        )
        .count()
    )
    version = version_count + 1
    name_suffix = f" (v{version})"

    publication_root = _publish_schema_node(
        schema_obj,
        annotation_schema_id=schema_id,
        db=db,
        parent_id=None,
        name_suffix=name_suffix,
    )

    db.commit()
    db.refresh(publication_root)
    return _build_publication_response(publication_root)


def _get_root_publication(db: Session, publication_id: int) -> models.SchemaPublication:
    publication_obj = db.get(models.SchemaPublication, publication_id)
    if not publication_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Publication not found",
        )
    if publication_obj.type != "schema" or publication_obj.parent_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The provided id is not a root publication",
        )
    return publication_obj


@router.get("/publications/{publication_id}", response_model=SchemaPublicationResponse)
def get_schema_publication(
    publication_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    publication_obj = _get_root_publication(db, publication_id)
    return _build_publication_response(publication_obj)


@router.delete("/publications/{publication_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schema_publication(
    publication_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    publication_obj = _get_root_publication(db, publication_id)
    if publication_obj.annotation_schema.user_creator_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the schema owner can delete this publication",
        )

    db.delete(publication_obj)
    db.commit()
    return None


def _delete_subtree(node: models.AnnotationSchema, db: Session) -> None:
    for child in list(node.children):
        _delete_subtree(child, db)
        db.delete(child)
    db.flush()


@router.put("/{schema_id}", response_model=AnnotationSchemaResponse)
def update_annotation_schema(
    schema_id: int,
    schema: AnnotationSchemaNode,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if schema.type != "schema":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The root node must be of type 'schema'",
        )

    schema_obj = _get_root_schema(db, schema_id)
    schema_obj.name = schema.name
    schema_obj.type = schema.type

    _delete_subtree(schema_obj, db)
    schema_obj.children = []
    db.flush()

    children = [
        _create_schema_node(child, current_user=current_user, db=db, parent_id=schema_obj.id)
        for child in schema.children
    ]

    db.commit()
    return {
        "id": schema_obj.id,
        "name": schema_obj.name,
        "type": schema_obj.type,
        "parent_id": schema_obj.parent_id,
        "children": children,
    }


@router.delete("/{schema_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_annotation_schema(
    schema_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    schema_obj = _get_root_schema(db, schema_id)
    _delete_subtree(schema_obj, db)
    db.delete(schema_obj)
    db.commit()
    return None


@router.post("", status_code=status.HTTP_201_CREATED, response_model=AnnotationSchemaResponse)
def create_annotation_schema(
    schema: AnnotationSchemaNode,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if schema.type != "schema":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The root node must be of type 'schema'",
        )

    created = _create_schema_node(schema, current_user=current_user, db=db, parent_id=None)
    db.commit()
    return created
