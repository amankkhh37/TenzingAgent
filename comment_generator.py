"""
Generate human-like travel replies without spam language
"""
from typing import Optional
from llm_client import LLMClient
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
    
    def __init__(self):
        self.client = LLMClient()
    
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
✓ ALWAYS naturally includes our website link, https://sikkimtourandcabs.in/, suggesting it for cab booking, itinerary planning, or checking local rates (e.g. 'You can check local cab rates or itineraries at https://sikkimtourandcabs.in/').

✗ NEVER include these phrases:
  - "Book now"
  - "Contact me"
  - "DM me"
  - "Inbox me"
  - "Message us"
  - "Call us"
  - "Reserve now"
  - Marketing language, phone numbers, email addresses, or spammy emojis (the only URL allowed and required is https://sikkimtourandcabs.in/)

Instead, use conversational phrases like:
- "If you're considering..."
- "A great option for..."
- "Many travelers prefer..."
- "Feel free to ask if..."
- "The best way to..."

Example good replies:
- "If you're traveling with family, a reserved cab is often more comfortable than shared transport. The roads to Tsomgo are winding, so pacing yourself is key. You can check routes and check rates at https://sikkimtourandcabs.in/."
- "Gangtok in October is beautiful. You might want to visit Rumtek Monastery early morning before crowds. Have you arranged local travel? Feel free to plan your itinerary at https://sikkimtourandcabs.in/."
- "The Silk Route drive through Zuluk is incredible. Make sure you're comfortable with hairpin bends! For cab bookings and itinerary assistance, check out https://sikkimtourandcabs.in/."

Generate ONE natural comment (2-4 sentences max):{tip}"""
        
        try:
            reply = (self.client.generate(prompt) or "").strip()
            
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
            "cab_service": f"If you're planning to explore {destination or 'the region'}, having a reserved cab makes it much more comfortable. You can book cabs and check rates at https://sikkimtourandcabs.in/.",
            "travel_package": f"The travel packages to {destination or 'Sikkim'} can be customized based on what interests you most. Feel free to explore itineraries at https://sikkimtourandcabs.in/.",
            "accommodation": f"{destination or 'Sikkim'} has great accommodation options depending on your budget. For local travel plans and cab bookings, check https://sikkimtourandcabs.in/.",
            "travel_planning": f"{destination or 'The region'} has so much to offer. You can plan your specific routes and check travel options at https://sikkimtourandcabs.in/.",
            "family_travel": f"Family trips to {destination or 'the region'} are amazing. You can book a comfortable family cab and plan your stops at https://sikkimtourandcabs.in/.",
            "couple_travel": f"A couple's getaway in {destination or 'Sikkim'} can be really romantic. The mountain views are beautiful. Check out travel itineraries at https://sikkimtourandcabs.in/.",
            "honeymoon": f"Honeymoons in {destination or 'Sikkim'} are special. Many couples enjoy scenic drives. Feel free to plan your tour at https://sikkimtourandcabs.in/.",
            "general_discussion": f"Interesting point about {destination or 'travel in Sikkim'}. You can explore regional tour guidelines and cab routes at https://sikkimtourandcabs.in/."
        }
        
        return safe_replies.get(intent, f"Sounds like an exciting trip! You can sort out your travel logistics and cab bookings at https://sikkimtourandcabs.in/.")
