"""
Analytics and reporting
"""
from datetime import datetime, date, timedelta
from typing import List, Dict, Tuple
from collections import defaultdict
from sqlalchemy import func
from database import (
    get_session, Lead, DailyStats, Group, AuditLog,
    LeadDatabase, DailyStatsDatabase
)

class Analytics:
    """Analytics and statistics"""
    
    @staticmethod
    def get_total_leads() -> int:
        """Total leads count"""
        return LeadDatabase.count_leads()
    
    @staticmethod
    def get_today_leads() -> int:
        """Leads created today"""
        session = get_session()
        try:
            today_start = datetime.combine(date.today(), datetime.min.time())
            return session.query(func.count(Lead.id)).filter(
                Lead.created_at >= today_start
            ).scalar()
        finally:
            session.close()
    
    @staticmethod
    def get_leads_by_status() -> Dict[str, int]:
        """Count leads by status"""
        statuses = ["NEW", "REVIEWING", "APPROVED", "REJECTED", "POSTED", "FOLLOW_UP", "CLOSED"]
        return {status: LeadDatabase.count_leads(status) for status in statuses}
    
    @staticmethod
    def get_high_value_leads() -> int:
        """High value leads (score >= 8)"""
        session = get_session()
        try:
            return session.query(func.count(Lead.id)).filter(Lead.lead_score >= 8).scalar()
        finally:
            session.close()
    
    @staticmethod
    def get_top_destinations(limit: int = 5) -> List[Tuple[str, int]]:
        """Top destinations by lead count"""
        session = get_session()
        try:
            results = session.query(
                Lead.destination,
                func.count(Lead.id).label('count')
            ).filter(
                Lead.destination.isnot(None),
                Lead.destination != "Not mentioned"
            ).group_by(Lead.destination).order_by(func.count(Lead.id).desc()).limit(limit).all()
            return results
        finally:
            session.close()
    
    @staticmethod
    def get_top_groups(limit: int = 5) -> List[Tuple[str, int]]:
        """Top groups by lead count"""
        session = get_session()
        try:
            results = session.query(
                Lead.group_name,
                func.count(Lead.id).label('count')
            ).group_by(Lead.group_name).order_by(func.count(Lead.id).desc()).limit(limit).all()
            return results
        finally:
            session.close()
    
    @staticmethod
    def get_most_common_intent() -> List[Tuple[str, int]]:
        """Most common lead intent"""
        session = get_session()
        try:
            results = session.query(
                Lead.intent,
                func.count(Lead.id).label('count')
            ).filter(Lead.intent.isnot(None)).group_by(Lead.intent).order_by(func.count(Lead.id).desc()).all()
            return results
        finally:
            session.close()
    
    @staticmethod
    def get_conversion_rate() -> float:
        """Conversion rate: posted leads / total leads"""
        total = LeadDatabase.count_leads()
        if total == 0:
            return 0.0
        posted = LeadDatabase.count_leads("POSTED")
        return (posted / total) * 100
    
    @staticmethod
    def get_leads_by_date_chart(days: int = 30) -> Dict[str, int]:
        """Leads by day for chart"""
        stats = DailyStatsDatabase.get_stats_range(days)
        return {str(stat.date): stat.leads_found for stat in stats}
    
    @staticmethod
    def get_leads_by_destination_chart() -> Dict[str, int]:
        """Leads by destination for chart"""
        results = Analytics.get_top_destinations(limit=20)
        return {dest: count for dest, count in results}
    
    @staticmethod
    def get_leads_by_group_chart() -> Dict[str, int]:
        """Leads by group for chart"""
        results = Analytics.get_top_groups(limit=20)
        return {group: count for group, count in results}
    
    @staticmethod
    def get_lead_score_distribution() -> Dict[str, int]:
        """Distribution of lead scores"""
        session = get_session()
        try:
            distribution = {
                "10": 0,
                "8-9": 0,
                "5-7": 0,
                "1-4": 0,
                "0": 0
            }
            
            query = session.query(Lead.lead_score, func.count(Lead.id)).group_by(Lead.lead_score).all()
            
            for score, count in query:
                if score == 10:
                    distribution["10"] += count
                elif score >= 8:
                    distribution["8-9"] += count
                elif score >= 5:
                    distribution["5-7"] += count
                elif score >= 1:
                    distribution["1-4"] += count
                else:
                    distribution["0"] += count
            
            return distribution
        finally:
            session.close()
    
    @staticmethod
    def get_group_performance() -> List[Dict]:
        """Performance metrics per group"""
        session = get_session()
        try:
            groups = session.query(Group).all()
            performance = []
            
            for group in groups:
                total_leads = session.query(func.count(Lead.id)).filter_by(group_id=group.id).scalar()
                posted_leads = session.query(func.count(Lead.id)).filter(
                    Lead.group_id == group.id,
                    Lead.status == "POSTED"
                ).scalar()
                high_value = session.query(func.count(Lead.id)).filter(
                    Lead.group_id == group.id,
                    Lead.lead_score >= 8
                ).scalar()
                
                if total_leads > 0:
                    performance.append({
                        "group_name": group.group_name,
                        "total_leads": total_leads,
                        "posted_leads": posted_leads,
                        "high_value_leads": high_value,
                        "conversion_rate": round((posted_leads / total_leads) * 100, 1),
                        "quality_score": round((high_value / total_leads) * 100, 1)
                    })
            
            return sorted(performance, key=lambda x: x["conversion_rate"], reverse=True)
        finally:
            session.close()
    
    @staticmethod
    def get_today_stats() -> Dict:
        """Get today's statistics"""
        session = get_session()
        try:
            today = date.today()
            stats = session.query(DailyStats).filter_by(date=today).first()
            
            if stats:
                return {
                    "groups_scanned": stats.groups_scanned,
                    "posts_read": stats.posts_read,
                    "leads_found": stats.leads_found,
                    "leads_high_value": stats.leads_high_value,
                    "comments_posted": stats.comments_posted,
                    "approvals": stats.approvals,
                    "rejections": stats.rejections
                }
            else:
                return {
                    "groups_scanned": 0,
                    "posts_read": 0,
                    "leads_found": 0,
                    "leads_high_value": 0,
                    "comments_posted": 0,
                    "approvals": 0,
                    "rejections": 0
                }
        finally:
            session.close()
    
    @staticmethod
    def get_week_summary() -> Dict:
        """Get last 7 days summary"""
        stats = DailyStatsDatabase.get_stats_range(days=7)
        
        summary = {
            "total_groups": sum(s.groups_scanned for s in stats),
            "total_posts": sum(s.posts_read for s in stats),
            "total_leads": sum(s.leads_found for s in stats),
            "total_high_value": sum(s.leads_high_value for s in stats),
            "total_posted": sum(s.comments_posted for s in stats),
            "avg_daily_leads": len(stats) and sum(s.leads_found for s in stats) / len(stats) or 0
        }
        
        return summary
