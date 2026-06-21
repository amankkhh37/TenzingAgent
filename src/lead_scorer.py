import json
import logging
import requests
from typing import Dict, Optional
from src.utils import retry

logger = logging.getLogger(__name__)

class LeadScorer:
    def __init__(self, model: str = "qwen3:8b", endpoint: str = "http://localhost:11434"):
        self.model = model
        self.endpoint = f"{endpoint}/api/generate"

    @retry(max_attempts=3, delay=2)
    def analyze_post(self, post_text: str) -> Optional[Dict]:
        prompt = f"""
        Analyze the following Facebook post for a travel agent lead.
        Extract the following information in JSON format:
        - intent: What the user wants (e.g., booking a flight, looking for a hotel, planning a honeymoon).
        - destination: The location they are interested in.
        - lead_score: A score from 0 to 100 based on how likely they are to be a good lead (high intent, specific details).
        - reason: Why you gave this lead score.
        - suggested_reply: A professional and helpful reply to the post as a travel agent.

        Post Text:
        "{post_text}"

        Output JSON only.
        """

        try:
            response = requests.post(
                self.endpoint,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json"
                },
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            return json.loads(result.get("response", "{}"))
        except Exception as e:
            logger.error(f"Error analyzing post with Ollama: {e}")
            return None
