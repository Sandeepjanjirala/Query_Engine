import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from speech.normalizer import normalize_speech_transcript
from query_engine.multi_stats import extract_requested_statistics, detect_entity_level_and_name
from query_engine.router import route_question

test_cases = [
    'RI Anitha dropout statistics',
    'RI Anitha dropouts statistics',
    'RI Anitha drop outs statistics',
    'RI Anitha fee due statistics',
    'RI Anitha feedue statistics',
    'RI Anitha fee-do statistics',
    'RI Anitha dropout fee due statistics',
    'RI Anitha drop outs feedue statistics',
    'RI Anitha revenue versus salary statistics',
    'RI Anitha revenue verse salary statistics',
    'RI Anitha dropout fee due revenue salary statistics',
    'Give Kakinada one statistics',
    'Give Kakinada 1 statistics',
    'Show Kakinada one dropout statistics',
    'Branch Amalapuram statistics',
    'Branch Amalapuram 2 statistics',
    'Branch Amalapuram two statistics',
    'Show top five branches by dropout percentage',
    'Show revenue versus salary for RI Anitha',
]

print(f"{'#':<3} | {'Spoken Input':<50} | {'Normalized':<50} | {'Function':<28}")
print('-' * 138)
for i, q in enumerate(test_cases, 1):
    raw, norm = normalize_speech_transcript(q)
    handler = route_question(norm)
    fn_name = handler.__name__ if handler else 'None'
    print(f"{i:<3} | {q:<50} | {norm:<50} | {fn_name:<28}")
