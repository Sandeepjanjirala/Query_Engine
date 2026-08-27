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
            "stream": False,
            "format": "json",
        }
        try:
            logger.debug("Sending request to Ollama: %s", payload)
            resp = requests.post(self.api_url, json=payload, timeout=30)
            resp.raise_for_status()
            
            raw_text = resp.text.strip()
            logger.debug("Ollama response status: %s, raw text: %s", resp.status_code, raw_text)

            # Try single JSON parse
            try:
                data = json.loads(raw_text)
                return data.get("message", {}).get("content", "").strip()
            except json.JSONDecodeError:
                # Fallback for NDJSON streaming if returned unexpectedly
                chunks = []
                for line in raw_text.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        line_data = json.loads(line)
                        content = line_data.get("message", {}).get("content", "")
                        if content:
                            chunks.append(content)
                    except json.JSONDecodeError:
                        continue
                if chunks:
                    return "".join(chunks).strip()
                raise
        except Exception as exc:
            raise RuntimeError(f"LLM request failed: {exc}")
