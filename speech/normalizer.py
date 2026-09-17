"""
speech/normalizer.py

Implements domain speech normalization, phonetic handling, and entity-safe resolution
for raw Whisper transcripts. Keeps raw and normalized transcripts separate.
"""

import re
import difflib
from typing import Dict, Any, Tuple, Set, Optional


SPOKEN_DIGITS = {
    'one': '1',
    'two': '2',
    'three': '3',
    'four': '4',
    'five': '5',
    'six': '6',
    'seven': '7',
    'eight': '8',
    'nine': '9',
}


def normalize_acoustic_terms(text: str) -> str:
    """
    Standardizes speech recognition variations, phonetically similar words,
    and colloquial pronunciations into canonical analytical domain phrases.
    """
    cleaned = text

    # 1. Dropouts variations (e.g. drop outs, draw out, draw pout)
    cleaned = re.sub(
        r'\b(?:drop\s*outs|drop-outs|drop\s*out|drop-out|draw\s*outs?|draw\s*pouts?)\b',
        'dropout',
        cleaned,
        flags=re.IGNORECASE,
    )

    # 2. Fee Due variations (e.g. feedue, fidu, feed you, fee do, fee view)
    cleaned = re.sub(
        r'\b(?:fee\s*dues?|fee-dues?|feedue|feedues|fee-do|fee\s+do|due\s+fee|fidu|fi\s+du|feed\s+you|feedyou|fee\s+view)\b',
        'fee due',
        cleaned,
        flags=re.IGNORECASE,
    )

    # 3. Revenue vs Salary variations (e.g. revenue and salary, revenue with salary, sal vs rev)
    cleaned = re.sub(
        r'\b(?:revenue\s*(?:versus|verse|vs\.?|and|&|where\s+the|with)?\s*salary|salary\s*(?:versus|verse|vs\.?|and|&|where\s+the|with)?\s*revenue|sal\s*vs\s*rev)\b',
        'revenue vs salary',
        cleaned,
        flags=re.IGNORECASE,
    )

    # 4. Student Teacher Ratio variations
    cleaned = re.sub(
        r'\b(?:teacher\s*(?:to\s*|-)?\s*student\s*ratio|student\s*(?:to\s*|-)?\s*teacher\s*ratio|s\.?t\.?r\.?)\b',
        'student teacher ratio',
        cleaned,
        flags=re.IGNORECASE,
    )

    # 5. Pre Primary / Primary / High School
    cleaned = re.sub(r'\b(?:pre-primary|pre\s+primary)\b', 'Pre Primary', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\b(?:primary\s+school)\b', 'Primary School', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\b(?:high\s+school)\b', 'High School', cleaned, flags=re.IGNORECASE)

    return cleaned


def normalize_branch_numbers(text: str) -> str:
    """
    Converts spoken number words into digits when attached to branch names
    (e.g. 'Kakinada one' -> 'Kakinada 1', 'Amalapuram two' -> 'Amalapuram 2',
    'Ameerpet two' -> 'Ameerpet 2').
    Does not modify ordinary standalone numbers (e.g. 'top five branches').
    """
    known_numbered_bases = {
        'kakinada', 'amalapuram', 'bobbili', 'tanuku', 'rajahmundry',
        'eluru', 'gajuwaka', 'ameerpet', 'kukatpally', 'kompally', 'miyapur',
        'madhapur', 'kondapur', 'nizampet', 'attapur'
    }

    try:
        from .vocabulary import get_dataset_entities
        for ent in get_dataset_entities():
            parts = ent.split()
            if len(parts) > 1 and parts[-1].isdigit():
                known_numbered_bases.add(" ".join(parts[:-1]).lower())
            elif parts:
                known_numbered_bases.add(ent.lower())
    except Exception:
        pass

    for word, digit in SPOKEN_DIGITS.items():
        for base in known_numbered_bases:
            pattern = rf'\b({re.escape(base)})\s+{word}\b'
            text = re.sub(pattern, rf'\1 {digit}', text, flags=re.IGNORECASE)

    return text


KNOWN_CANONICAL_NAMES = {
    'anitha': 'Anitha',
    'suresh': 'Suresh',
    'ahmedali': 'Ahmedali',
    'kakinada': 'Kakinada',
    'amalapuram': 'Amalapuram',
    'bobbili': 'Bobbili',
    'tanuku': 'Tanuku',
    'kismatpur': 'Kismatpur',
    'gachibowli': 'Gachibowli',
    'nallagandla': 'Nallagandla',
    'tolichowki': 'Tolichowki',
    'suchitra': 'Suchitra',
    'kompally': 'Kompally',
    'miyapur': 'Miyapur',
}


def normalize_entity_names(text: str) -> str:
    """
    Harmonizes capitalization of common roles and known executive/branch names,
    resolving common Whisper phonetic splits, mergers, and accents.
    """
    # Fix direct Whisper contractions / concatenated outputs (e.g. "RIONita" -> "RI Anitha")
    text = re.sub(r'\b(?:rionita|r\.?i\.?\s*onita)\b', 'RI Anitha', text, flags=re.IGNORECASE)

    # Strip commas or colons after role prefixes (e.g. "RI, Unita" -> "RI Unita", "AGM, Suresh" -> "AGM Suresh")
    text = re.sub(r'\b(RI|AGM|Branch|Zone)\s*[,:]\s*', r'\1 ', text, flags=re.IGNORECASE)
    text = re.sub(r'\bbranche\b', 'Branch', text, flags=re.IGNORECASE)

    # Fix run-together "Show" contractions from fast speech
    text = re.sub(r'\bshowtop\b', 'Show top', text, flags=re.IGNORECASE)
    text = re.sub(r'\bshokakinada\b', 'Show Kakinada', text, flags=re.IGNORECASE)

    # Prefix acoustic variations ("All right Anita" / "Are I Anita" -> "RI Anitha")
    text = re.sub(r'\b(?:are\s+i|all\s+right)\s+([a-zA-Z]+)', r'RI \1', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(?:a\s+gm|a\.?g\.?m\.?)\s+([a-zA-Z]+)', r'AGM \1', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(?:r\.?i\.?)\s+([a-zA-Z]+)', r'RI \1', text, flags=re.IGNORECASE)
    text = re.sub(r'\ba\s+gm\b', 'AGM', text, flags=re.IGNORECASE)

    # Common Whisper phonetic variations for Indian executive & branch names
    text = re.sub(r'\b(?:unita|anita|aneetha|anite)\b', 'Anitha', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(?:sureesh|sooresh|shuresh)\b', 'Suresh', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(?:ahmed\s*ali)\b', 'Ahmedali', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(?:kaki\s*nada|cocky\s*nada|cockinada)\b', 'Kakinada', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(?:bobby\s*lee|bobili)\b', 'Bobbili', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(?:amulapuram|amlapuram)\b', 'Amalapuram', text, flags=re.IGNORECASE)

    for lower, proper in KNOWN_CANONICAL_NAMES.items():
        text = re.sub(rf'\b{lower}\b', proper, text, flags=re.IGNORECASE)

    return text


def apply_fuzzy_entity_matching(text: str) -> str:
    """
    Safe phonetic / fuzzy matching for residual unrecognized words
    against known dataset branch, RI, and AGM entities (similarity >= 0.82).
    Protects multi-word expressions and numbered branches.
    """
    stopwords = {
        'show', 'give', 'tell', 'me', 'the', 'of', 'in', 'for', 'at', 'by', 'and', 'or',
        'dropout', 'dropouts', 'fee', 'due', 'statistics', 'stats', 'report', 'review',
        'revenue', 'salary', 'ratio', 'str', 'primary', 'school', 'branch', 'branches',
        'ri', 'agm', 'zone', 'top', 'bottom', 'highest', 'lowest', 'zero', 'paid'
    }

    try:
        from .vocabulary import get_dataset_entities
        known_entities = list(get_dataset_entities())
    except Exception:
        return text

    protected_words = stopwords.union({k.lower() for k in KNOWN_CANONICAL_NAMES.keys()})
    protected_words.update({'anitha', 'suresh', 'ahmedali', 'kakinada', 'amalapuram', 'bobbili', 'tanuku'})

    words = text.split()
    modified = False

    for i, w in enumerate(words):
        w_clean = re.sub(r'[^a-zA-Z0-9]', '', w)
        if len(w_clean) < 4 or w_clean.lower() in protected_words or w_clean.isdigit():
            continue

        # Check if word already matches an entity or known name
        if any(w_clean.lower() == e.lower() for e in known_entities):
            continue

        # Find closest match
        best_cand = None
        best_ratio = 0.0
        for cand in known_entities:
            # Strip initial prefixes (e.g. "Y.Anitha" -> "Anitha")
            cleaned_cand = re.sub(r'^[A-Za-z]\.\s*', '', cand).strip()
            cand_tokens = cleaned_cand.split()
            target = cand_tokens[0] if cand_tokens else cleaned_cand
            if target.lower() in protected_words:
                continue

            ratio = difflib.SequenceMatcher(None, w_clean.lower(), target.lower()).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_cand = target

        if best_ratio >= 0.82 and best_cand:
            words[i] = best_cand
            modified = True

    return " ".join(words) if modified else text


def normalize_speech_transcript(raw_text: str) -> Tuple[str, str]:
    """
    Main normalization pipeline. Takes raw Whisper output and applies:
    1. Acoustic and domain term normalization
    2. Entity names, role prefixes, and contraction resolution
    3. Spoken branch number normalization ('one' -> '1')
    4. High-confidence fuzzy entity matching
    5. Clean formatting

    Returns (raw_transcript, normalized_transcript).
    """
    if not raw_text:
        return "", ""

    raw = raw_text.strip()

    # Step 1: Normalize acoustic phrases (dropout, fee due, rev vs sal, str)
    step1 = normalize_acoustic_terms(raw)

    # Step 2: Normalize entity names and prefixes
    step2 = normalize_entity_names(step1)

    # Step 3: Normalize branch numbers (e.g. Kakinada one -> Kakinada 1)
    step3 = normalize_branch_numbers(step2)

    # Step 4: High-confidence fuzzy entity matching for residual slips
    step4 = apply_fuzzy_entity_matching(step3)

    # Clean redundant whitespace
    normalized = re.sub(r'\s+', ' ', step4).strip()

    # Always strip trailing punctuation (. ? ! ,) so downstream routers receive clean tokens
    normalized = normalized.rstrip('.?!, ').strip()

    return raw, normalized

