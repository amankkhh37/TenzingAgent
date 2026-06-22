"""
Shared LLM client with provider fallback support.
Supports Ollama and Azure OpenAI chat completions.
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

    def _raise_for_status_with_body(self, response: requests.Response) -> None:
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            body = response.text[:1000] if response.text else ""
            raise requests.HTTPError(f"{e}; response body: {body}", response=response) from e

    def _generate_azure(self, prompt: str, expect_json: bool = False) -> Optional[str]:
        if not AZURE_OPENAI_API_KEY:
            raise RuntimeError("AZURE_OPENAI_API_KEY is not configured")
        if not AZURE_OPENAI_ENDPOINT:
            raise RuntimeError("AZURE_OPENAI_ENDPOINT is not configured")
        if not AZURE_OPENAI_DEPLOYMENT:
            raise RuntimeError("AZURE_OPENAI_DEPLOYMENT is not configured")

        endpoint = (
            f"{AZURE_OPENAI_ENDPOINT.rstrip('/')}/openai/deployments/"
            f"{AZURE_OPENAI_DEPLOYMENT}/chat/completions"
        )
        headers = {
            "api-key": AZURE_OPENAI_API_KEY,
            "Content-Type": "application/json",
        }
        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": "You are a concise assistant that returns valid JSON when requested.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }
        if expect_json:
            payload["response_format"] = {"type": "json_object"}

        response = requests.post(
            endpoint,
            headers=headers,
            json=payload,
            params={"api-version": AZURE_OPENAI_API_VERSION},
            timeout=OLLAMA_TIMEOUT,
        )
        self._raise_for_status_with_body(response)
        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            return None
        message = choices[0].get("message") or {}
        return (message.get("content") or "").strip()

    def generate(self, prompt: str, expect_json: bool = False) -> Optional[str]:
        """Generate text using selected provider strategy."""
        provider = self.provider

        if provider == "ollama":
            return self._generate_ollama(prompt, expect_json=expect_json)

        if provider == "azure":
            return self._generate_azure(prompt, expect_json=expect_json)

        # auto: prefer local Ollama, fallback to Azure
        if self._check_ollama_available():
            try:
                lead_scorer_logger.info("LLM provider selected: ollama")
                return self._generate_ollama(prompt, expect_json=expect_json)
            except Exception as e:
                lead_scorer_logger.warning(f"Ollama generation failed, falling back to Azure: {e}")

        lead_scorer_logger.info("LLM provider selected: azure")
        return self._generate_azure(prompt, expect_json=expect_json)
