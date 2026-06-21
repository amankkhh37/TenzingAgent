"""
SQLAlchemy ORM Models for Travel Lead CRM
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean, ForeignKey, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class Lead(Base):
    """Facebook travel lead model"""
    __tablename__ = "leads"
    
    id = Column(Integer, primary_key=True)
    post_id = Column(String(255), unique=True, nullable=False, index=True)
    author = Column(String(255), nullable=False, index=True)
    author_profile = Column(String(500))
    group_id = Column(Integer, ForeignKey("groups.id"))
    group_name = Column(String(255), nullable=False)
    post_text = Column(Text, nullable=False)
    post_url = Column(String(500), unique=True, nullable=False)
    
    # Extracted information
    destination = Column(String(255), index=True)
    travel_date = Column(String(100))
    group_size = Column(String(50))
    budget = Column(String(100))
    intent = Column(String(100), index=True)  # Need Cab, Package, Hotel, etc.
    
    # Lead scoring
    lead_score = Column(Integer, default=0, index=True)
    reason = Column(Text)
    suggested_reply = Column(Text)
    
    # Status
    status = Column(String(50), default="NEW", index=True)  # NEW, REVIEWING, APPROVED, REJECTED, POSTED, FOLLOW_UP, CLOSED
    contacted = Column(Boolean, default=False)
    notes = Column(Text)
    follow_up_date = Column(Date)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    followups = relationship("FollowUp", back_populates="lead", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="lead", cascade="all, delete-orphan")
    group = relationship("Group", back_populates="leads")
    
    def __repr__(self):
        return f"<Lead {self.id}: {self.author} - {self.destination}>"

class FollowUp(Base):
    """Follow-up tracking for leads"""
    __tablename__ = "followups"
    
    id = Column(Integer, primary_key=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False, index=True)
    followup_date = Column(Date, nullable=False, index=True)
    note = Column(Text, nullable=False)
    completed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    
    # Relationships
    lead = relationship("Lead", back_populates="followups")
    
    def __repr__(self):
        return f"<FollowUp {self.id}: Lead {self.lead_id} - {self.followup_date}>"

class AuditLog(Base):
    """Audit trail for all lead actions"""
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False, index=True)
    action = Column(String(100), nullable=False)  # CREATED, REVIEWED, APPROVED, REJECTED, POSTED, etc.
    details = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    lead = relationship("Lead", back_populates="audit_logs")
    
    def __repr__(self):
        return f"<AuditLog {self.id}: Lead {self.lead_id} - {self.action}>"

class Group(Base):
    """Facebook group tracking"""
    __tablename__ = "groups"
    
    id = Column(Integer, primary_key=True)
    group_name = Column(String(255), nullable=False, unique=True, index=True)
    group_url = Column(String(500), nullable=False, unique=True)
    posts_scanned = Column(Integer, default=0)
    leads_found = Column(Integer, default=0)
    last_scanned = Column(DateTime, index=True)
    last_post_id = Column(String(255))  # For resuming scans
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    leads = relationship("Lead", back_populates="group", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Group {self.group_name}: {self.posts_scanned} posts>"

class Settings(Base):
    """Application settings storage"""
    __tablename__ = "settings"
    
    id = Column(Integer, primary_key=True)
    key = Column(String(100), nullable=False, unique=True, index=True)
    value = Column(Text, nullable=False)
    
    def __repr__(self):
        return f"<Settings {self.key}: {self.value}>"

class DailyStats(Base):
    """Daily statistics tracking"""
    __tablename__ = "daily_stats"
    
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, unique=True, index=True)
    groups_scanned = Column(Integer, default=0)
    posts_read = Column(Integer, default=0)
    leads_found = Column(Integer, default=0)
    leads_high_value = Column(Integer, default=0)
    comments_posted = Column(Integer, default=0)
    approvals = Column(Integer, default=0)
    rejections = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<DailyStats {self.date}: {self.leads_found} leads>"

class GeneratedContent(Base):
    """Daily generated Facebook posts"""
    __tablename__ = "generated_content"
    
    id = Column(Integer, primary_key=True)
    content_text = Column(Text, nullable=False)
    topic = Column(String(100))  # Nathula, Tsomgo Lake, Gangtok, etc.
    status = Column(String(50), default="DRAFT")  # DRAFT, REVIEWED, POSTED
    posted_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<GeneratedContent {self.id}: {self.topic}>"
