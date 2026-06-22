"""
Shared LLM client with provider fallback support.
Supports Ollama and Azure OpenAI-compatible Responses API.
"""
from __future__ import annotations

from typing import Optional, Dict
import requests

from config import (
    LLM_PROVIDER,
    OLLAMA_ENDPOINT,
    OLLAMA_MODEL,
    OLLAMA_TIMEOUT,
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_API_VERSION,
    AZURE_OPENAI_DEPLOYMENT,
)
from logger import lead_scorer_logger


class LLMClient:
    """Unified text generation client with provider fallback."""

    def __init__(self):
        self.provider = (LLM_PROVIDER or "auto").lower()

    def _check_ollama_available(self) -> bool:
        try:
            tags_url = f"{OLLAMA_ENDPOINT.rstrip('/')}/api/tags"
            response = requests.get(tags_url, timeout=5)
            return response.status_code == 200
        except Exception:
            return False

    def _generate_ollama(self, prompt: str, expect_json: bool = False) -> Optional[str]:
        endpoint = f"{OLLAMA_ENDPOINT.rstrip('/')}/api/generate"
        payload: Dict = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
        }
        if expect_json:
            payload["format"] = "json"

        response = requests.post(endpoint, json=payload, timeout=OLLAMA_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        return (data.get("response") or "").strip()

    def _generate_azure(self, prompt: str) -> Optional[str]:
        if not AZURE_OPENAI_API_KEY:
            raise RuntimeError("AZURE_OPENAI_API_KEY is not configured")

        endpoint = f"{AZURE_OPENAI_ENDPOINT.rstrip('/')}/openai/v1/responses"
        headers = {
            "Authorization": f"Bearer {AZURE_OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": AZURE_OPENAI_DEPLOYMENT,
            "input": prompt,
        }

        # Some deployments require api-version as query parameter.
        params = {}
        if AZURE_OPENAI_API_VERSION:
            params["api-version"] = AZURE_OPENAI_API_VERSION

        response = requests.post(
            endpoint,
            headers=headers,
            json=payload,
            params=params,
            timeout=OLLAMA_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()

        # Responses API can return output_text directly.
        text = data.get("output_text")
        if text:
            return text.strip()

        # Fallback parse for structured output arrays.
        output = data.get("output", [])
        collected = []
        for item in output:
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    collected.append(content.get("text", ""))
        return "\n".join(t for t in collected if t).strip()

    def generate(self, prompt: str, expect_json: bool = False) -> Optional[str]:
        """Generate text using selected provider strategy."""
        provider = self.provider

        if provider == "ollama":
            return self._generate_ollama(prompt, expect_json=expect_json)

        if provider == "azure":
            return self._generate_azure(prompt)

        # auto: prefer local Ollama, fallback to Azure
        if self._check_ollama_available():
            try:
                lead_scorer_logger.info("LLM provider selected: ollama")
                return self._generate_ollama(prompt, expect_json=expect_json)
            except Exception as e:
                lead_scorer_logger.warning(f"Ollama generation failed, falling back to Azure: {e}")

        lead_scorer_logger.info("LLM provider selected: azure")
        return self._generate_azure(prompt)
