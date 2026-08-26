import os
import sys
import json
import django

# Add project root to PYTHONPATH (one level up from this script)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_root)

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from assistant.router_bridge import route_command_to_handler

# Define real questions with correct metric abbreviations
questions_and_commands = [
    (
        "Which are the top 5 branches by dropout percentage?",
        {"operation": "top_n", "metric": "DPP", "n": 5},
    ),
    (
        "Show the bottom 5 branches by dropout percentage.",
        {"operation": "bottom_n", "metric": "DPP", "n": 5},
    ),
    (
        "Give me the total staff count (SC) by zone.",
        {"operation": "group_aggregate", "metric": "SC", "group_by": "zone", "agg": "sum"},
    ),
    (
        "Compare year over year change for dropout percentage (DPP).",
        {"operation": "yoy_compare", "metric": "DPP", "direction": "positive", "n": 5},
    ),
    (
        "Lookup dropout percentage for branch 'Kakinada 6'.",
        {"operation": "lookup", "metric": "DPP", "branches": ["Kakinada 6"]},
    ),
]

for question, command in questions_and_commands:
    print("\n--- Question ---")
    print(question)
    print("Structured command:")
    print(json.dumps(command, indent=2))
    handler = route_command_to_handler(command)
    if handler is None:
        print("No handler found for command")
        continue
    result = handler({})
    answer = result.get('answer')
    if isinstance(answer, str):
        # Remove any non‑ASCII characters (e.g., arrows) that cause cp1252 encode errors
        answer = answer.encode('ascii', errors='ignore').decode('ascii')
    print("Answer:")
    print(answer)
    data = result.get('data')
    if isinstance(data, list) and data:
        print("Data sample (first 2 rows):")
        for row in data[:2]:
            print(row)
    else:
        print("Data:", data)
