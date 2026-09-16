"""
speech/vocabulary.py

Maintains business terminology and dynamically extracts entity vocabulary
from the active dataset as the primary source for Whisper initial_prompt biasing.
"""

from typing import List, Set

BASE_HIERARCHIES = ['AGM', 'RI', 'Zone', 'Branch']

BASE_DOMAINS = [
    'Dropout',
    'Dropouts',
    'Fee Due',
    'Fee Dues',
    'Zero Paid',
    'Books Not Purchased',
    'Revenue',
    'Salary',
    'Revenue vs Salary',
    'Salary Burden',
    'Student Teacher Ratio',
    'Teacher Student Ratio',
    'STR',
]

BASE_LEVELS = [
    'Pre Primary',
    'Primary School',
    'High School',
    'PP',
    'PS',
    'HS',
]

BASE_TERMS = [
    'Current Year',
    'Last Year',
    'CY',
    'LY',
    'Existing',
    'New',
    'Sections',
    'Students',
    'Staff',
]

# Minimal seed names for fallback if dataset is not yet loaded
SEED_EXECUTIVE_NAMES = [
    'Anitha',
    'Suresh',
    'Ahmedali',
    'K. Srinivasa Rao',
]


def get_dataset_entities() -> Set[str]:
    """
    Primary entity extraction: extracts all known branches, AGM names,
    RI names, and Zones directly from the active Excel dataset.
    """
    entities: Set[str] = set()
    try:
        from query_engine.orchestrator import get_dataframe
        df = get_dataframe()
        for col in ['Branch', 'RI Name', 'RI', 'AGM Name', 'AGM', 'Zone']:
            if col in df.columns:
                vals = df[col].dropna().unique()
                for v in vals:
                    clean = str(v).strip()
                    if clean and clean != 'All':
                        entities.add(clean)
    except Exception:
        pass

    if not entities:
        entities.update(SEED_EXECUTIVE_NAMES)

    return entities


def build_initial_prompt() -> str:
    """
    Builds a concise contextual recognition hint (~150-200 tokens) for faster-whisper.
    Whisper uses this prompt to condition its autoregressive language model decoder,
    dramatically increasing recognition accuracy for Indian executive names, branch numbers,
    and multi-domain executive queries (avoiding phonetic splits like 'RIONita' or 'FIDU').
    Note: This is NOT model training; entity resolution remains authoritative.
    """
    dataset_entities = sorted(list(get_dataset_entities()))
    branch_candidates = [
        e for e in dataset_entities
        if e not in SEED_EXECUTIVE_NAMES and not any(h in e for h in ['AGM', 'RI', 'Zone'])
    ]
    top_branches = branch_candidates[:12]

    prompt = (
        "Executive dashboard queries: RI Anitha, AGM Suresh, Ahmedali, K. Srinivasa Rao. "
        "Branches: Kakinada 1, Amalapuram 2, Bobbili, Tanuku"
    )
    if top_branches:
        prompt += ", " + ", ".join(top_branches[:8])
    prompt += ". "
    prompt += "Metrics: Dropout statistics, Fee Due statistics, Revenue vs Salary, Student Teacher Ratio STR, Zero Paid, Books Not Purchased, overall report."
    return prompt

