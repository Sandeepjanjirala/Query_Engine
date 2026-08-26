import requests
import json
import logging

logger = logging.getLogger(__name__)

class LLMAdapter:
    """Simple Ollama client wrapper.
    The default model is 'llama3.1:8b' but can be overridden via the constructor.
    """

    def __init__(self, model: str = "llama3.1:8b") -> None:
        self.model = model
        self.api_url = "http://localhost:11434/api/chat"

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Send prompts to Ollama and return the assistant's response content.
        Raises RuntimeError on request failure.
        """
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "options": {"temperature": 0.0},
        }
        try:
            logger.debug("Sending request to Ollama: %s", payload)
            resp = requests.post(self.api_url, json=payload, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            # Ollama returns a dict with a 'message' key containing the response.
            return data.get("message", {}).get("content", "").strip()
        except Exception as exc:
            raise RuntimeError(f"LLM request failed: {exc}")
