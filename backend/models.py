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
    role = Column(String(50), default="member")

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
    role = Column(String(50), default="collaborator")

    # Relationships
    project = relationship("Project", back_populates="user_access")
    user = relationship("User", back_populates="project_access")


class ProjectTeam(Base):
    __tablename__ = "project_teams"

    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True)
    role = Column(String(50), default="collaborator")

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
