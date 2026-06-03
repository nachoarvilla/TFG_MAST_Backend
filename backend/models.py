from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, DateTime, func, UniqueConstraint, Index, Enum, JSON
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    email = Column(String(100), unique=True, index=True)
    password_hash = Column(String(255))
    role = Column(String(50), default="user")

    # Relationships
    teams = relationship("TeamMember", back_populates="user")
    owned_projects = relationship("Project", back_populates="owner", foreign_keys="Project.owner_id")
    project_access = relationship("ProjectUser", back_populates="user")
    uploaded_documents = relationship("Document", back_populates="uploader", cascade="all, delete-orphan")
    created_annotation_schemas = relationship(
        "AnnotationSchema",
        back_populates="user_creator",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, index=True)
    description = Column(String(255))

    # Relationships
    members = relationship("TeamMember", back_populates="team")
    project_access = relationship("ProjectTeam", back_populates="team")


class TeamMember(Base):
    __tablename__ = "team_members"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    team_id = Column(Integer, ForeignKey("teams.id"), primary_key=True)
    role = Column(
        Enum("leader", "member", name="team_member_role", validate_strings=True),
        nullable=False,
        default="member",
        server_default="member",
    )

    # Relationships
    user = relationship("User", back_populates="teams")
    team = relationship("Team", back_populates="members")


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String(255))
    is_private = Column(Boolean, default=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Relationships
    owner = relationship("User", back_populates="owned_projects", foreign_keys=[owner_id])
    user_access = relationship("ProjectUser", back_populates="project", cascade="all, delete-orphan")
    team_access = relationship("ProjectTeam", back_populates="project", cascade="all, delete-orphan")
    documents = relationship("ProjectDocument", back_populates="project", cascade="all, delete-orphan")
    schema_publications = relationship("ProjectSchemaPublication", back_populates="project", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    file_path = Column(String(255), nullable=False)
    total_pages = Column(Integer, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    uploader_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    uploader = relationship("User", back_populates="uploaded_documents")
    projects = relationship("ProjectDocument", back_populates="document")


class ProjectUser(Base):
    __tablename__ = "project_users"

    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role = Column(
        Enum("owner", "collaborator", "viewer", name="project_user_role", validate_strings=True),
        nullable=False,
        default="viewer",
        server_default="viewer",
    )

    # Relationships
    project = relationship("Project", back_populates="user_access")
    user = relationship("User", back_populates="project_access")


class ProjectTeam(Base):
    __tablename__ = "project_teams"

    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True)
    role = Column(
        Enum("collaborator", "viewer", name="project_team_role", validate_strings=True),
        nullable=False,
        default="viewer",
        server_default="viewer",
    )

    # Relationships
    project = relationship("Project", back_populates="team_access")
    team = relationship("Team", back_populates="project_access")


class ProjectDocument(Base):
    __tablename__ = "project_documents"
    __table_args__ = (
        UniqueConstraint("project_id", "document_id", name="uq_project_document"),
        Index("fk_pd_document", "document_id"),
        Index("idx_project_documents_project_id", "project_id"),
    )

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)

    # Relationships
    project = relationship("Project", back_populates="documents")
    document = relationship("Document", back_populates="projects")
    regions = relationship("Region", back_populates="project_document", cascade="all, delete-orphan")


class Region(Base):
    __tablename__ = "regions"
    __table_args__ = (
        Index("idx_regions_project_document_id", "project_document_id"),
    )

    id = Column(Integer, primary_key=True)
    project_document_id = Column(Integer, ForeignKey("project_documents.id", ondelete="CASCADE"), nullable=False)
    page_number = Column(Integer, nullable=False)
    type = Column(Enum("Polygon", "Polyline", "Rectangle", name="region_type"), nullable=False)
    coordinates = Column(JSON, nullable=False)

    # Relationships
    project_document = relationship("ProjectDocument", back_populates="regions")


class AnnotationSchema(Base):
    __tablename__ = "annotation_schemas"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    type = Column(
        Enum("schema", "class", "annotation", name="annotation_schema_type", validate_strings=True),
        nullable=False,
    )
    parent_id = Column(Integer, ForeignKey("annotation_schemas.id", ondelete="SET NULL"), nullable=True)
    user_creator_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Relationships
    user_creator = relationship("User", back_populates="created_annotation_schemas")
    publications = relationship(
        "SchemaPublication",
        back_populates="annotation_schema",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    parent = relationship("AnnotationSchema", remote_side=[id], back_populates="children")
    children = relationship("AnnotationSchema", back_populates="parent", cascade="all, delete-orphan")


class SchemaPublication(Base):
    __tablename__ = "schema_publications"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    type = Column(
        Enum("schema", "class", "annotation", name="schema_publication_type", validate_strings=True),
        nullable=False,
    )
    parent_id = Column(Integer, ForeignKey("schema_publications.id", ondelete="SET NULL"), nullable=True)
    annotation_schema_id = Column(Integer, ForeignKey("annotation_schemas.id", ondelete="CASCADE"), nullable=False)

    # Relationships
    annotation_schema = relationship("AnnotationSchema", back_populates="publications")
    parent = relationship("SchemaPublication", remote_side=[id], back_populates="children")
    children = relationship("SchemaPublication", back_populates="parent", cascade="all, delete-orphan")
    projects = relationship("ProjectSchemaPublication", back_populates="schema_publication", cascade="all, delete-orphan")


class ProjectSchemaPublication(Base):
    __tablename__ = "project_schema_publications"
    __table_args__ = (
        UniqueConstraint("project_id", "schema_publication_id", name="uq_project_schema_publication"),
        Index("idx_project_schema_publications_project_id", "project_id"),
        Index("idx_project_schema_publications_schema_publication_id", "schema_publication_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    schema_publication_id = Column(Integer, ForeignKey("schema_publications.id", ondelete="CASCADE"), nullable=False)

    # Relationships
    project = relationship("Project", back_populates="schema_publications")
    schema_publication = relationship("SchemaPublication", back_populates="projects")
