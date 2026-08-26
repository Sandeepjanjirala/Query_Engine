import json
import logging
from .llm_adapter import LLMAdapter

logger = logging.getLogger(__name__)

def _build_system_prompt() -> str:
    """Return a concise system prompt that tells the model to output a JSON command.
    The prompt lists supported operations and metric names.
    """
    # Dynamically fetch metric abbreviations from the project.
    try:
        from query_engine.glossary import ABBREVIATIONS
        metrics = ", ".join(sorted(ABBREVIATIONS.keys()))
    except Exception:
        metrics = ""
    prompt = (
        "You are an AI that translates a natural‑language analytics question into a JSON command. "
        "The command must contain at least an 'operation' field specifying the action (e.g., 'top_n', 'lookup', 'yoy_compare', 'threshold', 'room_ratio', 'group_aggregate'). "
        "Other optional fields are 'metric', 'n', 'direction', 'group_by', 'threshold', 'op', 'count_only', etc. "
        f"Supported metric abbreviations are: {metrics}. "
        "Return ONLY a valid JSON object, no explanations or extra text."
    )
    return prompt

def parse_question(question: str, adapter: LLMAdapter | None = None) -> dict:
    """Send the question to the LLM and parse the JSON response.
    Raises RuntimeError on parsing failure.
    """
    if adapter is None:
        adapter = LLMAdapter()
    system_prompt = _build_system_prompt()
    logger.debug("System prompt: %s", system_prompt)
    response = adapter.generate(system_prompt, question)
    logger.debug("LLM raw response: %s", response)
    try:
        command = json.loads(response)
    except Exception as e:
        raise RuntimeError(f"Failed to parse LLM response as JSON: {e}\nResponse was: {response}")
    return command
