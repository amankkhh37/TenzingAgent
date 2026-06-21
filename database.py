"""
Database management and operations
"""
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Tuple
from models import Base, Lead, Group, Settings, DailyStats, FollowUp, AuditLog, GeneratedContent
from config import DATABASE_PATH
from logger import database_logger

# Database setup
engine = create_engine(f"sqlite:///{DATABASE_PATH}", echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine,expire_on_commit=False)

def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)
    database_logger.info(f"Database initialized at {DATABASE_PATH}")

def get_session() -> Session:
    """Get a new database session"""
    return SessionLocal()

class LeadDatabase:
    """Lead management operations"""
    
    @staticmethod
    def create_lead(lead_data: Dict) -> Optional[Lead]:
        """Create a new lead"""
        session = get_session()
        try:
            # Check for duplicate post_id
            existing = session.query(Lead).filter_by(post_id=lead_data.get('post_id')).first()
            if existing:
                database_logger.debug(f"Duplicate post found: {lead_data.get('post_id')}")
                return None
            
            lead = Lead(**lead_data)
            session.add(lead)
            session.commit()
            database_logger.info(f"Lead created: {lead.id} from {lead.author}")
            return lead
        except IntegrityError as e:
            session.rollback()
            database_logger.warning(f"Lead creation failed (duplicate): {e}")
            return None
        except Exception as e:
            session.rollback()
            database_logger.error(f"Error creating lead: {e}")
            return None
        finally:
            session.close()
    
    @staticmethod
    def get_lead_by_id(lead_id: int) -> Optional[Lead]:
        """Get lead by ID"""
        session = get_session()
        try:
            return session.query(Lead).filter_by(id=lead_id).first()
        finally:
            session.close()
    
    @staticmethod
    def get_lead_by_post_id(post_id: str) -> Optional[Lead]:
        """Check if post already exists"""
        session = get_session()
        try:
            return session.query(Lead).filter_by(post_id=post_id).first()
        finally:
            session.close()
    
    @staticmethod
    def update_lead(lead_id: int, **kwargs) -> bool:
        """Update lead"""
        session = get_session()
        try:
            lead = session.query(Lead).filter_by(id=lead_id).first()
            if not lead:
                return False
            
            for key, value in kwargs.items():
                if hasattr(lead, key):
                    setattr(lead, key, value)
            
            lead.updated_at = datetime.utcnow()
            session.commit()
            database_logger.info(f"Lead {lead_id} updated")
            return True
        except Exception as e:
            session.rollback()
            database_logger.error(f"Error updating lead: {e}")
            return False
        finally:
            session.close()
    
    @staticmethod
    def get_leads_by_status(status: str, limit: int = None) -> List[Lead]:
        """Get leads by status"""
        session = get_session()
        try:
            query = session.query(Lead).filter_by(status=status).order_by(Lead.lead_score.desc(), Lead.created_at.desc())
            if limit:
                query = query.limit(limit)
            return query.all()
        finally:
            session.close()
    
    @staticmethod
    def get_all_leads(limit: int = None, offset: int = 0) -> List[Lead]:
        """Get all leads with pagination"""
        session = get_session()
        try:
            query = session.query(Lead).order_by(Lead.created_at.desc()).offset(offset)
            if limit:
                query = query.limit(limit)
            return query.all()
        finally:
            session.close()
    
    @staticmethod
    def search_leads(search_term: str, field: str = "author") -> List[Lead]:
        """Search leads"""
        session = get_session()
        try:
            if field == "author":
                return session.query(Lead).filter(Lead.author.ilike(f"%{search_term}%")).all()
            elif field == "destination":
                return session.query(Lead).filter(Lead.destination.ilike(f"%{search_term}%")).all()
            elif field == "group_name":
                return session.query(Lead).filter(Lead.group_name.ilike(f"%{search_term}%")).all()
            elif field == "intent":
                return session.query(Lead).filter(Lead.intent.ilike(f"%{search_term}%")).all()
            else:
                return []
        finally:
            session.close()
    
    @staticmethod
    def count_leads(status: str = None) -> int:
        """Count leads by status"""
        session = get_session()
        try:
            query = session.query(func.count(Lead.id))
            if status:
                query = query.filter_by(status=status)
            return query.scalar()
        finally:
            session.close()
    
    @staticmethod
    def get_leads_by_date_range(start_date: date, end_date: date) -> List[Lead]:
        """Get leads within date range"""
        session = get_session()
        try:
            return session.query(Lead).filter(
                Lead.created_at >= start_date,
                Lead.created_at <= end_date
            ).order_by(Lead.created_at.desc()).all()
        finally:
            session.close()

class GroupDatabase:
    """Group management operations"""
    
    @staticmethod
    def create_or_update_group(group_name: str, group_url: str) -> Group:
        """Create or get group"""
        session = get_session()
        try:
            group = session.query(Group).filter_by(group_url=group_url).first()
            if not group:
                group = Group(group_name=group_name, group_url=group_url)
                session.add(group)
            session.commit()
            # Make transient to detach from session
            from sqlalchemy.orm import make_transient
            make_transient(group)
            return group
        except IntegrityError:
            session.rollback()
            group = session.query(Group).filter_by(group_url=group_url).first()
            if group:
                from sqlalchemy.orm import make_transient
                make_transient(group)
            return group
        except Exception as e:
            session.rollback()
            database_logger.error(f"Error creating/updating group: {e}")
            return None
        finally:
            session.close()
    
    @staticmethod
    def update_group_stats(group_id: int, posts_scanned: int = 0, leads_found: int = 0):
        """Update group statistics"""
        session = get_session()
        try:
            group = session.query(Group).filter_by(id=group_id).first()
            if group:
                group.posts_scanned += posts_scanned
                group.leads_found += leads_found
                group.last_scanned = datetime.utcnow()
                session.commit()
        except Exception as e:
            database_logger.error(f"Error updating group stats: {e}")
            session.rollback()
        finally:
            session.close()
    
    @staticmethod
    def get_all_groups() -> List[Group]:
        """Get all active groups"""
        from sqlalchemy.orm import make_transient
        session = get_session()
        try:
            groups = session.query(Group).filter_by(enabled=True).all()
            # Detach from session before closing
            for group in groups:
                make_transient(group)
            return groups
        except Exception as e:
            database_logger.error(f"Error fetching groups: {e}")
            return []
        finally:
            session.close()

class SettingsDatabase:
    """Settings management"""
    
    @staticmethod
    def get_setting(key: str, default: str = None) -> str:
        """Get setting by key"""
        session = get_session()
        try:
            setting = session.query(Settings).filter_by(key=key).first()
            return setting.value if setting else default
        finally:
            session.close()
    
    @staticmethod
    def set_setting(key: str, value: str):
        """Set or update setting"""
        session = get_session()
        try:
            setting = session.query(Settings).filter_by(key=key).first()
            if setting:
                setting.value = value
            else:
                setting = Settings(key=key, value=value)
                session.add(setting)
            session.commit()
        except Exception as e:
            database_logger.error(f"Error setting value: {e}")
            session.rollback()
        finally:
            session.close()

class AuditLogDatabase:
    """Audit logging"""
    
    @staticmethod
    def log_action(lead_id: int, action: str, details: str = None):
        """Log an action"""
        session = get_session()
        try:
            log = AuditLog(lead_id=lead_id, action=action, details=details)
            session.add(log)
            session.commit()
            database_logger.info(f"Logged action: {action} for lead {lead_id}")
        except Exception as e:
            database_logger.error(f"Error logging action: {e}")
            session.rollback()
        finally:
            session.close()
    
    @staticmethod
    def get_lead_history(lead_id: int) -> List[AuditLog]:
        """Get audit history for lead"""
        session = get_session()
        try:
            return session.query(AuditLog).filter_by(lead_id=lead_id).order_by(AuditLog.timestamp.desc()).all()
        finally:
            session.close()

class DailyStatsDatabase:
    """Daily statistics"""
    
    @staticmethod
    def get_or_create_today_stats() -> DailyStats:
        """Get or create today's stats"""
        session = get_session()
        try:
            today = date.today()
            stats = session.query(DailyStats).filter_by(date=today).first()
            if not stats:
                stats = DailyStats(date=today)
                session.add(stats)
                session.commit()
            return stats
        finally:
            session.close()
    
    @staticmethod
    def update_stats(**kwargs):
        """Update today's stats"""
        session = get_session()
        try:
            stats = DailyStatsDatabase.get_or_create_today_stats()
            for key, value in kwargs.items():
                if hasattr(stats, key):
                    setattr(stats, key, getattr(stats, key) + value if hasattr(stats, key) else value)
            session.commit()
        except Exception as e:
            database_logger.error(f"Error updating stats: {e}")
        finally:
            session.close()
    
    @staticmethod
    def get_stats_range(days: int = 30) -> List[DailyStats]:
        """Get stats for last N days"""
        session = get_session()
        try:
            start_date = date.today() - timedelta(days=days)
            return session.query(DailyStats).filter(
                DailyStats.date >= start_date
            ).order_by(DailyStats.date.desc()).all()
        finally:
            session.close()

class FollowUpDatabase:
    """Follow-up management"""
    
    @staticmethod
    def create_followup(lead_id: int, followup_date: date, note: str) -> Optional[FollowUp]:
        """Create follow-up"""
        session = get_session()
        try:
            followup = FollowUp(lead_id=lead_id, followup_date=followup_date, note=note)
            session.add(followup)
            session.commit()
            database_logger.info(f"Follow-up created for lead {lead_id}")
            return followup
        except Exception as e:
            database_logger.error(f"Error creating follow-up: {e}")
            session.rollback()
            return None
        finally:
            session.close()
    
    @staticmethod
    def get_upcoming_followups(days_ahead: int = 7) -> List[FollowUp]:
        """Get upcoming follow-ups"""
        session = get_session()
        try:
            today = date.today()
            future_date = today + timedelta(days=days_ahead)
            return session.query(FollowUp).filter(
                FollowUp.followup_date >= today,
                FollowUp.followup_date <= future_date,
                FollowUp.completed == False
            ).order_by(FollowUp.followup_date).all()
        finally:
            session.close()
