"""
Generate human-like travel replies without spam language
"""
import requests
import json
from typing import Optional
from config import OLLAMA_ENDPOINT, OLLAMA_MODEL, OLLAMA_TIMEOUT
from logger import lead_scorer_logger

class CommentGenerator:
    """Generate helpful, human-like replies to travel posts"""
    
    TRAVEL_TIPS = {
        "Sikkim": "Sikkim has been named Asia's cleanest state. The best time to visit is October to May.",
        "Gangtok": "Gangtok is the capital of Sikkim. Visit Rumtek Monastery, Tsomgo Lake, and Kanyam for stunning views.",
        "Darjeeling": "Known for its tea gardens and the toy train. The best views are from Tiger Hill at sunrise.",
        "Nathula": "Nathula Pass is at 14,100 feet. It connects India and Tibet. A must-visit for adventure seekers.",
        "Tsomgo Lake": "Glacial lake at 12,400 feet with stunning mountain views. Open April to October.",
        "Zuluk": "Ancient Silk Route town with hairpin bends and panoramic views. Best visited from May to October.",
        "NJP": "New Jalpaiguri is the main railway junction for reaching Darjeeling and Sikkim."
    }
    
    def __init__(self, endpoint: str = OLLAMA_ENDPOINT, model: str = OLLAMA_MODEL, timeout: int = OLLAMA_TIMEOUT):
        self.endpoint = f"{endpoint}/api/generate"
        self.model = model
        self.timeout = timeout
    
    def generate_reply(
        self,
        post_text: str,
        intent: str,
        destination: str,
        travel_date: str,
        group_size: str,
        budget: str
    ) -> Optional[str]:
        """
        Generate a human-like reply to a travel post
        
        STRICT RULES:
        - Never use: "Book now", "Contact me", "DM me", "Inbox me"
        - Provide genuine value
        - Sound like a friendly local
        - Encourage conversation
        - Show local knowledge
        """
        
        # Get relevant tip if destination mentioned
        tip = ""
        for location, knowledge in self.TRAVEL_TIPS.items():
            if location.lower() in (destination or "").lower():
                tip = f"\n\nQuick tip: {knowledge}"
                break
        
        prompt = f"""You are a friendly, knowledgeable travel guide for Sikkim Tours & Cabs.

Someone posted on Facebook:
"{post_text}"

Their travel details (extracted from post):
- Intent: {intent}
- Destination: {destination}
- Travel Date: {travel_date}
- Group Size: {group_size}
- Budget: {budget}

Generate a SHORT, helpful comment that:
✓ Sounds natural and human (like a local travel expert)
✓ Provides useful information or suggestions
✓ Shows local knowledge
✓ Encourages them to ask more questions
✓ Builds trust and credibility

✗ NEVER include these phrases:
  - "Book now"
  - "Contact me"
  - "DM me"
  - "Inbox me"
  - "Message us"
  - "Call us"
  - "Reserve now"
  - Marketing language or emojis

Instead, use conversational phrases like:
- "If you're considering..."
- "A great option for..."
- "Many travelers prefer..."
- "Feel free to ask if..."
- "The best way to..."

Example good replies:
- "If you're traveling with family, a reserved cab is often more comfortable than shared transport. The roads to Tsomgo are winding though, so pace yourself."
- "Gangtok in October is beautiful. You might want to visit Rumtek Monastery early morning before crowds. Have you arranged local travel?"
- "The Silk Route drive through Zuluk is incredible. Make sure you're comfortable with hairpin bends!"

Generate ONE natural comment (2-4 sentences max):{tip}"""
        
        try:
            response = requests.post(
                self.endpoint,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=self.timeout
            )
            
            response.raise_for_status()
            result = response.json()
            reply = result.get("response", "").strip()
            
            # Clean up the response
            reply = reply.replace("\\n", "\n")
            
            # Verify it doesn't contain forbidden phrases
            forbidden = ["book now", "contact me", "dm me", "inbox me", "message us", "call us"]
            reply_lower = reply.lower()
            if any(phrase in reply_lower for phrase in forbidden):
                lead_scorer_logger.warning("Generated reply contains forbidden phrases, regenerating...")
                return self.generate_safe_reply(intent, destination, travel_date)
            
            return reply
        
        except Exception as e:
            lead_scorer_logger.error(f"Error generating reply: {e}")
            return self.generate_safe_reply(intent, destination, travel_date)
    
    def generate_safe_reply(self, intent: str, destination: str, travel_date: str) -> str:
        """Generate a safe, template-based reply if LLM fails"""
        
        safe_replies = {
            "cab_service": f"If you're planning to explore {destination or 'the region'}, having a reserved cab makes it much more comfortable. The roads can be winding, so you'd be in good hands.",
            "travel_package": f"The travel packages to {destination or 'Sikkim'} can be customized based on what interests you most. Have you thought about which attractions are must-visits?",
            "accommodation": f"{destination or 'Sikkim'} has great accommodation options depending on your budget and preferences. What kind of experience are you looking for?",
            "travel_planning": f"{destination or 'The region'} has so much to offer. The best time to visit depends on what you want to see. Feel free to ask for specific route suggestions.",
            "family_travel": f"Family trips to {destination or 'the region'} are amazing. You'll want comfortable transport and family-friendly stops along the way.",
            "couple_travel": f"A couple's getaway in {destination or 'Sikkim'} can be really romantic. The mountain views are especially beautiful at sunrise.",
            "honeymoon": f"Honeymoons in {destination or 'Sikkim'} are special. Many couples enjoy the scenic drives and peaceful mountain retreats.",
            "general_discussion": f"Interesting point about {destination or 'travel in Sikkim'}. The local culture and natural beauty really stand out."
        }
        
        return safe_replies.get(intent, f"Sounds like an exciting trip! Have you sorted out your travel logistics for {destination or 'the region'}?")
