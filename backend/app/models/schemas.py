from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    Float,
    Date,
    Table,
    func
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import TSVECTOR
from pgvector.sqlalchemy import Vector
from app.database import Base
# Many-to-many relationship between users and security groups
user_security_groups = Table(
    "user_security_groups",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "security_group_id",
        Integer,
        ForeignKey("security_groups.id", ondelete="CASCADE"),
        primary_key=True
    ),
)

# Many-to-many relationship between documents and security groups
document_security_groups = Table(
    "document_security_groups",
    Base.metadata,
    Column("document_id", Integer, ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "security_group_id",
        Integer,
        ForeignKey("security_groups.id", ondelete="CASCADE"),
        primary_key=True
    ),
)

class SecurityGroup(Base):
    __tablename__ = "security_groups"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, index=True, nullable=False)
    description = Column(String(255), nullable=True)

    # Relationships
    users = relationship("User", secondary=user_security_groups, back_populates="security_groups")
    documents = relationship("Document", secondary=document_security_groups, back_populates="security_groups")

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    role = Column(String(50), default="read_only")  # admin, document_admin, read_only
    department = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    uploaded_documents = relationship("Document", back_populates="uploader")
    audit_events = relationship("AuditEvent", back_populates="actor")
    security_groups = relationship("SecurityGroup", secondary=user_security_groups, back_populates="users")


class Document(Base):
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    family_key = Column(String(255), nullable=True)
    version = Column(String(50), nullable=False)
    category = Column(String(100), nullable=False)
    department = Column(String(100), nullable=False)
    effective_date = Column(DateTime, nullable=True)
    status = Column(String(50), default="processing")  # processing, indexed, failed, active, archived
    file_url = Column(String(500), nullable=True)
    checksum = Column(String(255), unique=True, nullable=False)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    uploader = relationship("User", back_populates="uploaded_documents")
    pages = relationship("DocumentPage", back_populates="document", cascade="all, delete-orphan")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")
    referenced_rules = relationship("Rule", back_populates="source_document")
    security_groups = relationship("SecurityGroup", secondary=document_security_groups, back_populates="documents")


class DocumentPage(Base):
    __tablename__ = "document_pages"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    page_number = Column(Integer, nullable=False)
    extracted_text = Column(Text, nullable=False)
    extraction_method = Column(String(50), default="native")  # native, ocr

    # Relationships
    document = relationship("Document", back_populates="pages")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    page_start = Column(Integer, nullable=False)
    page_end = Column(Integer, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(384), nullable=True)  # 384-dimensional dense vector (MiniLM-L12-v2)
    search_vector = Column(TSVECTOR, nullable=True)  # PostgreSQL full-text search vector
    metadata_json = Column(Text, nullable=True)  # JSON-serialized metadata: {"source_format": "pdf"|"docx", "is_full_document_citation": bool}
    
    # New fields for PoC specifications
    section = Column(String(255), nullable=True)
    security_group = Column(String(100), nullable=True, default="default")
    content_hash = Column(String(64), nullable=True, index=True)

    # Relationships
    document = relationship("Document", back_populates="chunks")


class RdaQuery(Base):
    __tablename__ = "rda_queries"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String(36), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    query_text = Column(Text, nullable=False)
    results_count = Column(Integer, nullable=False, default=0)
    duration_ms = Column(Integer, nullable=False, default=0)
    confidence = Column(String(50), nullable=True)
    model_name = Column(String(100), nullable=True)
    citation_count = Column(Integer, nullable=True, default=0)
    abstained = Column(Boolean, nullable=True, default=False)
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    user = relationship("User")


class Employee(Base):
    __tablename__ = "employees"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_number = Column(String(100), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(String(100), nullable=False)
    department = Column(String(100), nullable=False)
    station = Column(String(100), nullable=False)
    status = Column(String(50), default="active")
    weekly_hours = Column(Integer, default=0)
    last_shift_end = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    qualifications = relationship("EmployeeQualification", back_populates="employee", cascade="all, delete-orphan")
    availabilities = relationship("Availability", back_populates="employee", cascade="all, delete-orphan")
    leave_requests = relationship("LeaveRequest", back_populates="employee", cascade="all, delete-orphan")

class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User")
    messages = relationship("ConversationMessage", back_populates="conversation", cascade="all, delete-orphan")


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    role = Column(String(50), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    confidence = Column(String(50), nullable=True)
    citations = Column(Text, nullable=True)  # JSON-serialized citations array
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")


class Qualification(Base):
    __tablename__ = "qualifications"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Relationships
    employees = relationship("EmployeeQualification", back_populates="qualification", cascade="all, delete-orphan")


class EmployeeQualification(Base):
    __tablename__ = "employee_qualifications"
    
    employee_id = Column(Integer, ForeignKey("employees.id"), primary_key=True)
    qualification_id = Column(Integer, ForeignKey("qualifications.id"), primary_key=True)
    issued_at = Column(Date, nullable=False)
    expires_at = Column(Date, nullable=False)
    status = Column(String(50), default="valid")

    # Relationships
    employee = relationship("Employee", back_populates="qualifications")
    qualification = relationship("Qualification", back_populates="employees")


class Availability(Base):
    __tablename__ = "availability"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    start_at = Column(DateTime, nullable=False)
    end_at = Column(DateTime, nullable=False)
    type = Column(String(50), default="available")  # available, unavailable
    notes = Column(Text, nullable=True)

    # Relationships
    employee = relationship("Employee", back_populates="availabilities")


class LeaveRequest(Base):
    __tablename__ = "leave_requests"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    start_at = Column(DateTime, nullable=False)
    end_at = Column(DateTime, nullable=False)
    status = Column(String(50), default="approved")  # pending, approved, rejected
    leave_type = Column(String(100), nullable=False)  # annual, sick, etc.

    # Relationships
    employee = relationship("Employee", back_populates="leave_requests")


class Rule(Base):
    __tablename__ = "rules"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(100), unique=True, nullable=False)  # R-001, R-002, etc.
    name = Column(String(255), nullable=False)
    rule_type = Column(String(50), default="hard")  # hard, soft
    parameter_json = Column(Text, nullable=True)  # JSON-serialized rule parameters
    source_document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    source_page = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)

    # Relationships
    source_document = relationship("Document", back_populates="referenced_rules")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(255), nullable=False)  # login, upload_document, search, etc.
    entity_type = Column(String(100), nullable=True)  # document, user, etc.
    entity_id = Column(String(100), nullable=True)
    details_json = Column(Text, nullable=True)  # JSON-serialized details
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    actor = relationship("User", back_populates="audit_events")

