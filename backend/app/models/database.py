from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, JSON, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

from config.settings import settings

Base = declarative_base()

class UFDRReport(Base):
    __tablename__ = "ufdr_reports"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String, nullable=False)
    device_info = Column(JSON)
    extraction_date = Column(DateTime)
    case_number = Column(String)
    investigator = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    processed = Column(Boolean, default=False)
    
    # Relationships
    chat_records = relationship("ChatRecord", back_populates="ufdr_report")
    call_records = relationship("CallRecord", back_populates="ufdr_report")
    media_files = relationship("MediaFile", back_populates="ufdr_report")
    contacts = relationship("Contact", back_populates="ufdr_report")

class ChatRecord(Base):
    __tablename__ = "chat_records"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ufdr_report_id = Column(UUID(as_uuid=True), ForeignKey("ufdr_reports.id"))
    app_name = Column(String)  # WhatsApp, Telegram, etc.
    sender_number = Column(String)
    receiver_number = Column(String)
    message_content = Column(Text)
    timestamp = Column(DateTime)
    message_type = Column(String)  # text, image, video, audio, document
    is_deleted = Column(Boolean, default=False)
    metadata_ = Column("metadata", JSON)
    
    ufdr_report = relationship("UFDRReport", back_populates="chat_records")

class CallRecord(Base):
    __tablename__ = "call_records"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ufdr_report_id = Column(UUID(as_uuid=True), ForeignKey("ufdr_reports.id"))
    caller_number = Column(String)
    receiver_number = Column(String)
    call_type = Column(String)  # incoming, outgoing, missed
    duration = Column(Integer)  # in seconds
    timestamp = Column(DateTime)
    metadata_ = Column("metadata", JSON)
    
    ufdr_report = relationship("UFDRReport", back_populates="call_records")

class MediaFile(Base):
    __tablename__ = "media_files"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ufdr_report_id = Column(UUID(as_uuid=True), ForeignKey("ufdr_reports.id"))
    filename = Column(String)
    file_path = Column(String)
    file_type = Column(String)  # image, video, audio, document
    file_size = Column(Integer)
    created_date = Column(DateTime)
    modified_date = Column(DateTime)
    hash_md5 = Column(String)
    hash_sha256 = Column(String)
    metadata_ = Column("metadata", JSON)
    
    ufdr_report = relationship("UFDRReport", back_populates="media_files")

class Contact(Base):
    __tablename__ = "contacts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ufdr_report_id = Column(UUID(as_uuid=True), ForeignKey("ufdr_reports.id"))
    name = Column(String)
    phone_numbers = Column(JSON)  # List of phone numbers
    email_addresses = Column(JSON)  # List of email addresses
    metadata_ = Column("metadata", JSON)
    
    ufdr_report = relationship("UFDRReport", back_populates="contacts")

class Investigation(Base):
    __tablename__ = "investigations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_number = Column(String, unique=True, nullable=False)
    title = Column(String)
    description = Column(Text)
    investigator = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="active")  # active, closed, pending

# Database setup
engine = create_engine(settings.postgres_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_tables():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()