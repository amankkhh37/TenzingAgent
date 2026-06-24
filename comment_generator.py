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

Generate a very short, crisp, helpful, and to-the-point comment (strictly max 1-2 sentences) that:
✓ Sounds natural and human (like a local travel expert)
✓ Provides useful information or suggestions
✓ Shows local knowledge
✓ Encourages them to ask more questions
✓ Builds trust and credibility
✓ ALWAYS naturally includes our website link, https://sikkimtourandcabs.in/, suggesting it for cab booking, itinerary planning, or checking local rates (e.g. 'You can check local cab rates or itineraries at https://sikkimtourandcabs.in/').
✓ ALWAYS write the reply in the SAME language, script (e.g., Hinglish/Benglish Latin transliterations or native scripts like Devanagari/Bengali), and informal writing style/code-switching as the original Facebook post text.

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

Generate ONE natural comment (strictly 1-2 sentences max, short, crisp, and to the point):{tip}"""
        
        try:
            reply = (self.client.generate(prompt) or "").strip()
            
            # Clean up the response
            reply = reply.replace("\\n", "\n")
            
            # Verify it doesn't contain forbidden phrases
            forbidden = ["book now", "contact me", "dm me", "inbox me", "message us", "call us"]
            reply_lower = reply.lower()
            if any(phrase in reply_lower for phrase in forbidden):
                lead_scorer_logger.warning("Generated reply contains forbidden phrases, regenerating...")
                return self.generate_safe_reply(intent, destination, travel_date, post_text)
            
            return reply
        
        except Exception as e:
            lead_scorer_logger.error(f"Error generating reply: {e}")
            return self.generate_safe_reply(intent, destination, travel_date, post_text)
    
    def generate_safe_reply(self, intent: str, destination: str, travel_date: str, post_text: str = "") -> str:
        """Generate a safe, template-based reply if LLM fails, matching the script/language of the post."""
        
        # Detect script
        script = "en"
        if post_text:
            # Check for Devanagari characters (Hindi, Nepali, etc.)
            if any('\u0900' <= char <= '\u097F' for char in post_text):
                script = "hi"
            # Check for Bengali characters
            elif any('\u0980' <= char <= '\u09FF' for char in post_text):
                script = "bn"
        
        # Localized templates
        if script == "hi":
            safe_replies = {
                "cab_service": f"यदि आप {destination or 'इस क्षेत्र'} की यात्रा की योजना बना रहे हैं, तो रिज़र्व कैब होना बहुत आरामदायक रहता है। आप https://sikkimtourandcabs.in/ पर कैब बुक कर सकते हैं और दरें देख सकते हैं।",
                "travel_package": f"{destination or 'सिक्किम'} के लिए यात्रा पैकेज को आपकी पसंद के अनुसार अनुकूलित (customize) किया जा सकता है। यात्रा मार्गों और विवरण के लिए https://sikkimtourandcabs.in/ पर जाएँ।",
                "accommodation": f"{destination or 'सिक्किम'} में आपके बजट के अनुसार बेहतरीन ठहरने के विकल्प उपलब्ध हैं। लोकल यात्रा योजनाओं और कैब बुकिंग के लिए https://sikkimtourandcabs.in/ चेक करें।",
                "travel_planning": f"{destination or 'इस क्षेत्र'} में घूमने के लिए बहुत कुछ है। आप विशिष्ट रूट और यात्रा विकल्प https://sikkimtourandcabs.in/ पर देख सकते हैं।",
                "family_travel": f"परिवार के साथ {destination or 'इस क्षेत्र'} की यात्राएं शानदार होती हैं। आप https://sikkimtourandcabs.in/ पर एक आरामदायक पारिवारिक कैब बुक कर सकते हैं।",
                "couple_travel": f"{destination or 'सिक्किम'} में कपल्स के लिए घूमना बहुत ही रोमांटिक हो सकता है। सुंदर दृश्यों और यात्रा कार्यक्रमों के लिए https://sikkimtourandcabs.in/ चेक करें।",
                "honeymoon": f"{destination or 'सिक्किम'} में हनीमून मनाना बहुत ही खास होता है। सुंदर ड्राइव और यात्रा की योजना के लिए https://sikkimtourandcabs.in/ पर जाएँ।",
                "general_discussion": f"{destination or 'सिक्किम यात्रा'} के बारे में बहुत अच्छी जानकारी है। आप स्थानीय यात्रा दिशानिर्देशों और कैब मार्गों के बारे में https://sikkimtourandcabs.in/ पर जान सकते हैं।"
            }
            fallback = f"सिक्किम की यात्रा बहुत ही सुंदर और रोमांचक होगी! आप https://sikkimtourandcabs.in/ पर अपनी यात्रा और कैब बुकिंग की योजना बना सकते हैं।"
        elif script == "bn":
            safe_replies = {
                "cab_service": f"আপনি যদি {destination or 'এই অঞ্চল'} ভ্রমণের পরিকল্পনা করে থাকেন, তবে একটি সংরক্ষিত ক্যাব নেওয়া অনেক বেশি আরামদায়ক হবে। আপনি https://sikkimtourandcabs.in/ থেকে ক্যাব বুক করতে পারেন এবং রেট চেক করতে পারেন।",
                "travel_package": f"{destination or 'সিকিম'} ট্যুর প্যাকেজগুলি আপনার পছন্দ মতো কাস্টমাইজ করা সম্ভব। বিভিন্ন ট্যুর রুট দেখতে https://sikkimtourandcabs.in/ ভিজিট করুন।",
                "accommodation": f"{destination or 'সিকিম'} এ আপনার বাজেট অনুযায়ী থাকার অনেক ভালো অপশন রয়েছে। স্থানীয় ভ্রমণ পরিকল্পনা ও ক্যাব বুকিংয়ের জন্য https://sikkimtourandcabs.in/ দেখতে পারেন।",
                "travel_planning": f"{destination or 'এই অঞ্চল'} এ ঘুরে দেখার মতো অনেক সুন্দর জায়গা আছে। আপনার ভ্রমণের নির্দিষ্ট রুট ও বিবরণ দেখতে https://sikkimtourandcabs.in/ চেক করুন।",
                "family_travel": f"পরিবারের সাথে {destination or 'এই অঞ্চল'} ভ্রমণ সবসময় দারুণ অভিজ্ঞতার হয়। আরামদায়ক ফ্যামিলি ক্যাব বুক করার জন্য https://sikkimtourandcabs.in/ এ ভিজিট করুন।",
                "couple_travel": f"দম্পতিদের জন্য {destination or 'সিকিম'} ভ্রমণ খুবই রোমান্টিক হতে পারে। পাহাড়ের সুন্দর দৃশ্য ও ট্যুর প্ল্যান করতে https://sikkimtourandcabs.in/ ভিজিট করুন।",
                "honeymoon": f"{destination or 'সিকিম'} এ হানিমুন কাটানো খুবই বিশেষ অনুভূতির। সুন্দর ড্রাইভ ও রোমান্টিক ট্যুরের জন্য https://sikkimtourandcabs.in/ চেক করুন।",
                "general_discussion": f"{destination or 'সিকিম ভ্রমণ'} নিয়ে খুব সুন্দর আলোচনা। স্থানীয় ট্যুর নির্দেশিকা ও ক্যাব রুটের বিবরণ জানতে https://sikkimtourandcabs.in/ দেখুন।"
            }
            fallback = f"সিকিম ভ্রমণ দারুণ ও মনোরম হবে! ক্যাব বুকিং এবং ভ্রমণ পরিকল্পনার জন্য https://sikkimtourandcabs.in/ এ যোগাযোগ করুন।"
        else:
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
            fallback = f"Sounds like an exciting trip! You can sort out your travel logistics and cab bookings at https://sikkimtourandcabs.in/."
        
        return safe_replies.get(intent, fallback)
