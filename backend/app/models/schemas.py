from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Float, Date, func
from sqlalchemy.orm import relationship
from app.database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    role = Column(String(50), default="read_only_manager")  # admin, document_administrator, roster_manager, read_only_manager
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    uploaded_documents = relationship("Document", back_populates="uploader")
    created_shifts = relationship("Shift", foreign_keys="[Shift.created_by]", back_populates="creator")
    approved_shifts = relationship("Shift", foreign_keys="[Shift.approved_by]", back_populates="approver")
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
    embedding = Column(Text, nullable=True)  # JSON-serialized list of floats (for portability)
    metadata_json = Column(Text, nullable=True)  # JSON-serialized metadata dictionary

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
    assignments = relationship("Assignment", back_populates="employee")
    roster_candidates = relationship("RosterCandidate", back_populates="employee")


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


class Shift(Base):
    __tablename__ = "shifts"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    route_or_station = Column(String(255), nullable=False)
    starts_at = Column(DateTime, nullable=False)
    ends_at = Column(DateTime, nullable=False)
    status = Column(String(50), default="draft")  # draft, approved, cancelled
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)

    # Relationships
    creator = relationship("User", foreign_keys=[created_by], back_populates="created_shifts")
    approver = relationship("User", foreign_keys=[approved_by], back_populates="approved_shifts")
    requirements = relationship("ShiftRequirement", back_populates="shift", cascade="all, delete-orphan")
    roster_runs = relationship("RosterRun", back_populates="shift", cascade="all, delete-orphan")
    assignments = relationship("Assignment", back_populates="shift", cascade="all, delete-orphan")


class ShiftRequirement(Base):
    __tablename__ = "shift_requirements"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    shift_id = Column(Integer, ForeignKey("shifts.id"), nullable=False)
    role = Column(String(100), nullable=False)
    qualification_id = Column(Integer, ForeignKey("qualifications.id"), nullable=True)
    headcount = Column(Integer, default=1)

    # Relationships
    shift = relationship("Shift", back_populates="requirements")
    assignments = relationship("Assignment", back_populates="requirement")
    roster_candidates = relationship("RosterCandidate", back_populates="requirement")


class RosterRun(Base):
    __tablename__ = "roster_runs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    shift_id = Column(Integer, ForeignKey("shifts.id"), nullable=False)
    status = Column(String(50), default="pending")  # pending, complete, partial, failed
    parameters_json = Column(Text, nullable=True)  # JSON-serialized run parameters
    generated_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    generated_at = Column(DateTime, server_default=func.now())

    # Relationships
    shift = relationship("Shift", back_populates="roster_runs")
    candidates = relationship("RosterCandidate", back_populates="roster_run", cascade="all, delete-orphan")


class RosterCandidate(Base):
    __tablename__ = "roster_candidates"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    roster_run_id = Column(Integer, ForeignKey("roster_runs.id"), nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    requirement_id = Column(Integer, ForeignKey("shift_requirements.id"), nullable=False)
    eligible = Column(Boolean, default=True)
    score = Column(Float, default=0.0)
    reasons_json = Column(Text, nullable=True)  # JSON-serialized eligibility details

    # Relationships
    roster_run = relationship("RosterRun", back_populates="candidates")
    employee = relationship("Employee", back_populates="roster_candidates")
    requirement = relationship("ShiftRequirement", back_populates="roster_candidates")


class Assignment(Base):
    __tablename__ = "assignments"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    shift_id = Column(Integer, ForeignKey("shifts.id"), nullable=False)
    requirement_id = Column(Integer, ForeignKey("shift_requirements.id"), nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    source = Column(String(50), default="system")  # system, manual
    override_reason = Column(Text, nullable=True)
    status = Column(String(50), default="active")  # active, archived

    # Relationships
    shift = relationship("Shift", back_populates="assignments")
    requirement = relationship("ShiftRequirement", back_populates="assignments")
    employee = relationship("Employee", back_populates="assignments")


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
    action = Column(String(255), nullable=False)  # login, upload_document, generate_roster, etc.
    entity_type = Column(String(100), nullable=True)  # document, employee, shift, etc.
    entity_id = Column(String(100), nullable=True)
    details_json = Column(Text, nullable=True)  # JSON-serialized details
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    actor = relationship("User", back_populates="audit_events")
