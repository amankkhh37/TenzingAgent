"""
Daily content generation for Facebook posts
"""
from datetime import datetime, time
from typing import Optional
from config import CONTENT_GENERATION_HOUR
from database import get_session, GeneratedContent
from llm_client import LLMClient
from logger import lead_scorer_logger

class ContentGenerator:
    """Generate daily Facebook travel content"""
    
    TOPICS = [
        "Nathula Pass",
        "Tsomgo Lake",
        "Gangtok attractions",
        "Zuluk and Silk Route",
        "Darjeeling tea gardens",
        "NJP travel tips",
        "Family travel in Sikkim",
        "Honeymoon destinations",
        "Adventure activities",
        "Local cuisine",
        "Best time to visit",
        "Travel budget tips"
    ]
    
    def __init__(self):
        self.client = LLMClient()
    
    def generate_daily_content(self, topic: Optional[str] = None) -> Optional[str]:
        """
        Generate a daily Facebook post about travel to Sikkim/Darjeeling
        
        Returns:
            Suggested Facebook post content
        """
        if not topic:
            import random
            topic = random.choice(self.TOPICS)
        
        prompt = f"""Generate an engaging, informative Facebook post about traveling to Sikkim and Darjeeling, specifically about: {topic}

Requirements:
- 150-300 words
- Friendly, conversational tone
- Include practical travel tips
- Encourage comments and engagement
- No promotional language
- No "Book now" or "Contact us" calls to action
- Include relevant emojis (max 3)
- Suitable for a local travel business

Example topics to include:
- Best time to visit
- What to see/do
- Local tips
- Travel duration
- Budget suggestions
- Interesting facts

Generate a single post ready to share on Facebook:"""
        
        try:
            content = (self.client.generate(prompt) or "").strip()
            
            if content:
                # Save to database
                self._save_content(content, topic)
                return content
            
            return None
        
        except Exception as e:
            lead_scorer_logger.error(f"Error generating content: {e}")
            return None
    
    def _save_content(self, content: str, topic: str):
        """Save generated content to database"""
        session = get_session()
        try:
            generated = GeneratedContent(
                content_text=content,
                topic=topic,
                status="DRAFT"
            )
            session.add(generated)
            session.commit()
            lead_scorer_logger.info(f"Generated content saved for topic: {topic}")
        except Exception as e:
            lead_scorer_logger.error(f"Error saving generated content: {e}")
            session.rollback()
        finally:
            session.close()
    
    def should_generate(self) -> bool:
        """Check if it's time to generate content"""
        current_hour = datetime.now().hour
        return current_hour == CONTENT_GENERATION_HOUR
    
    def get_pending_content(self) -> list:
        """Get content awaiting review"""
        session = get_session()
        try:
            return session.query(GeneratedContent).filter_by(status="DRAFT").all()
        finally:
            session.close()
    
    def approve_content(self, content_id: int) -> bool:
        """Mark content as approved"""
        session = get_session()
        try:
            content = session.query(GeneratedContent).filter_by(id=content_id).first()
            if content:
                content.status = "REVIEWED"
                session.commit()
                return True
            return False
        except Exception as e:
            lead_scorer_logger.error(f"Error approving content: {e}")
            return False
        finally:
            session.close()
    
    def mark_posted(self, content_id: int) -> bool:
        """Mark content as posted"""
        session = get_session()
        try:
            content = session.query(GeneratedContent).filter_by(id=content_id).first()
            if content:
                content.status = "POSTED"
                content.posted_at = datetime.utcnow()
                session.commit()
                return True
            return False
        except Exception as e:
            lead_scorer_logger.error(f"Error marking content as posted: {e}")
            return False
        finally:
            session.close()

    def delete_content(self, content_id: int) -> bool:
        """Delete generated content"""
        session = get_session()
        try:
            content = session.query(GeneratedContent).filter_by(id=content_id).first()
            if content:
                session.delete(content)
                session.commit()
                return True
            return False
        except Exception as e:
            lead_scorer_logger.error(f"Error deleting content: {e}")
            session.rollback()
            return False
        finally:
            session.close()
