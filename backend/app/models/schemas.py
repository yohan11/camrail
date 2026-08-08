from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Float, Date, func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import TSVECTOR
from pgvector.sqlalchemy import Vector
from app.database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    role = Column(String(50), default="read_only")  # admin, document_admin, read_only
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    uploaded_documents = relationship("Document", back_populates="uploader")
    audit_events = relationship("AuditEvent", back_populates="actor")


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

    # Relationships
    document = relationship("Document", back_populates="chunks")


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

