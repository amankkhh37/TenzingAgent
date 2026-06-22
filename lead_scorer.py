"""
Lead scoring using configurable LLM provider.
"""
import json
from typing import Optional, Dict
from llm_client import LLMClient
from logger import lead_scorer_logger

class LeadScorer:
    """Score and classify travel leads using Qwen3 model"""
    
    CLASSIFICATION_LABELS = [
        "Need Cab",
        "Need Package",
        "Need Hotel",
        "Need Itinerary",
        "Family Trip",
        "Couple Trip",
        "Group Tour",
        "Honeymoon",
        "General Discussion",
        "Not A Lead"
    ]
    
    def __init__(self):
        self.client = LLMClient()
    
    def verify_connection(self) -> bool:
        """Verify at least one configured LLM backend can be reached."""
        try:
            return self.client.generate("Reply with OK.") is not None
        except Exception as e:
            lead_scorer_logger.error(f"Cannot connect to configured LLM provider: {e}")
            return False
    
    def analyze_post(self, post_text: str, author: str = "") -> Optional[Dict]:
        """
        Analyze a Facebook post and extract travel lead information
        
        Returns:
            {
                "intent": "",
                "destination": "",
                "travel_date": "",
                "group_size": "",
                "budget": "",
                "lead_score": 0,
                "classification": "",
                "reason": "",
                "suggested_reply": ""
            }
        """
        
        prompt = f"""Analyze this Facebook post from a travel perspective. Extract information and score it as a potential lead for a travel company (Sikkim Tours & Cabs).Sikkim Tours & Cabs only plans for Tours in Sikkim, Siliguri, Darjeeling, Kalimpong areas.

POST AUTHOR: {author}
POST TEXT:
{post_text}

Classify the post into ONE of these categories:
- Need Cab: User is looking for transportation/cab services
- Need Package: User is looking for travel packages or tour plans
- Need Hotel: User is looking for accommodation
- Need Itinerary: User is asking for travel suggestions/itinerary
- Family Trip: Mentions traveling with family
- Couple Trip: Mentions traveling as a couple
- Group Tour: Mentions group travel
- Honeymoon: Mentions honeymoon or newly married
- General Discussion: Tourism discussion but not a lead
- Not A Lead: Not travel-related

Extract these fields (use "Not mentioned" if not found):
- destination: Where they want to go (be specific)
- travel_date: When they plan to travel
- group_size: How many people (family/couple/group size)
- budget: Their budget range if mentioned

Score the lead (0-10):
- 10: Ready to book (specific dates, location, urgent)
- 8: Planning travel soon (clear intent, timeframe)
- 5: General planning (interested but no specifics)
- 0: Not a lead (not travel-related)

Provide a score and brief reason.

Generate a helpful, human-like reply that:
- Provides value without being salesy
- Avoids "Book now", "Contact me", "DM me", "Inbox me"
- Sounds like a friendly local travel expert
- Encourages conversation
- Shows local knowledge

Return as JSON:
{{
  "classification": "One of the categories",
  "destination": "extracted destination",
  "travel_date": "extracted travel date",
  "group_size": "extracted group size",
  "budget": "extracted budget",
  "lead_score": 0-10,
  "reason": "why this score",
  "suggested_reply": "helpful response"
}}"""
        
        try:
            lead_scorer_logger.debug(f"Analyzing post from {author}")
            
            result_text = self.client.generate(prompt, expect_json=True)
            if not result_text:
                return None
            
            # Parse the JSON response
            try:
                analysis = json.loads(result_text)
                
                # Ensure all required fields exist
                analysis.setdefault("classification", "Not A Lead")
                analysis.setdefault("destination", "Not mentioned")
                analysis.setdefault("travel_date", "Not mentioned")
                analysis.setdefault("group_size", "Not mentioned")
                analysis.setdefault("budget", "Not mentioned")
                analysis.setdefault("lead_score", 0)
                analysis.setdefault("reason", "Unable to determine")
                analysis.setdefault("suggested_reply", "")
                
                # Ensure score is valid
                analysis["lead_score"] = max(0, min(10, int(analysis.get("lead_score", 0))))
                
                lead_scorer_logger.info(f"Post analyzed: score={analysis['lead_score']}, intent={analysis.get('classification')}")
                return analysis
                
            except json.JSONDecodeError as e:
                lead_scorer_logger.warning(f"Failed to parse JSON response: {e}")
                return None
        
        except Exception as e:
            lead_scorer_logger.error(f"Error analyzing post: {e}")
            return None
    
    def map_classification_to_intent(self, classification: str) -> str:
        """Map classification to intent field"""
        mapping = {
            "Need Cab": "cab_service",
            "Need Package": "travel_package",
            "Need Hotel": "accommodation",
            "Need Itinerary": "travel_planning",
            "Family Trip": "family_travel",
            "Couple Trip": "couple_travel",
            "Group Tour": "group_tour",
            "Honeymoon": "honeymoon",
            "General Discussion": "general_discussion",
            "Not A Lead": "not_a_lead"
        }
        return mapping.get(classification, "other")
