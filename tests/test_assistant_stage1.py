import json
import logging
import unittest
from unittest import mock
from django.test import Client
from django.urls import reverse

# Import modules to be patched
from assistant.ai import llm_adapter as llm_mod

class DummyLLMAdapter:
    def __init__(self, model: str = "dummy"):
        self.model = model
        self.responses = {}

    def set_response(self, question: str, response_json: str):
        self.responses[question] = response_json

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        return self.responses.get(user_prompt, "")

class AssistantStage1Tests(unittest.TestCase):
    def setUp(self):
        self.client = Client()
        self.dummy_adapter = DummyLLMAdapter()
        # Map questions to expected JSON commands
        self.dummy_adapter.set_response(
            "Which are the top 5 branches by dropout percentage?",
            json.dumps({"operation": "top_n", "metric": "DPP", "n": 5})
        )
        self.dummy_adapter.set_response(
            "Show the bottom 3 branches by vacancy rate.",
            json.dumps({"operation": "bottom_n", "metric": "vacancy_rate", "n": 3})
        )
        self.dummy_adapter.set_response(
            "What is the dropout percentage for branch ABC?",
            json.dumps({"operation": "lookup", "metric": "DPP", "branches": ["ABC"]})
        )
        self.dummy_adapter.set_response(
            "Give me the total staff count by zone.",
            json.dumps({"operation": "group_aggregate", "metric": "staff_count", "group_by": "zone", "agg": "sum"})
        )
        self.dummy_adapter.set_response(
            "Compare year over year change for DPP.",
            json.dumps({"operation": "yoy_compare", "metric": "DPP", "direction": "positive", "n": 5})
        )

    def _patch_llm_adapter(self):
        """Patch LLMAdapter to return our dummy adapter."""
        return mock.patch("assistant.ai.command_parser.LLMAdapter", lambda *args, **kwargs: self.dummy_adapter)


    def test_parse_question_success(self):
        with self._patch_llm_adapter():
            from assistant.ai.command_parser import parse_question
            cmd = parse_question("Which are the top 5 branches by dropout percentage?")
            self.assertIsInstance(cmd, dict)
            self.assertEqual(cmd["operation"], "top_n")
            self.assertEqual(cmd["metric"], "DPP")
            self.assertEqual(cmd["n"], 5)

    def test_validator_unknown_metric(self):
        with self._patch_llm_adapter():
            from assistant.ai.command_parser import parse_question
            from assistant.ai.validator import validate_command
            self.dummy_adapter.set_response(
                "Show unknown metric",
                json.dumps({"operation": "top_n", "metric": "UNKNOWN", "n": 5})
            )
            cmd = parse_question("Show unknown metric")
            err = validate_command(cmd)
            self.assertIsNotNone(err)
            self.assertIn("Metric 'UNKNOWN' is not recognized", err)

    def test_assistant_integration_questions(self):
        questions = [
            "Which are the top 5 branches by dropout percentage?",
            "Show the bottom 3 branches by vacancy rate.",
            "What is the dropout percentage for branch ABC?",
            "Give me the total staff count by zone.",
            "Compare year over year change for DPP.",
        ]
        with self._patch_llm_adapter():
            for q in questions:
                response = self.client.post(reverse('assistant'), {"question": q})
                self.assertEqual(response.status_code, 200)
                content = response.content.decode()
                self.assertTrue("Structured Command" in content or "Answer" in content)
                self.assertNotIn("error", content.lower())

    def test_assistant_invalid_json_handling(self):
        bad_adapter = DummyLLMAdapter()
        bad_adapter.set_response("Bad question", "not a json")
        with mock.patch("assistant.ai.command_parser.LLMAdapter", lambda *args, **kwargs: bad_adapter):
            response = self.client.post(reverse('assistant'), {"question": "Bad question"})
            self.assertEqual(response.status_code, 200)
            content = response.content.decode()
            self.assertIn("Failed to parse LLM response as JSON", content)


if __name__ == "__main__":
    unittest.main()
