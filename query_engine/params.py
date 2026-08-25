"""
Natural-language parameter extraction.

Pure text -> parameter functions with no Django/pandas coupling. Each
function extracts dimensions needed across the 150-question set:
metric(s), level, type, year, N, sort direction, staff category,
group-by dimension, aggregation, threshold parameters, dimension
comparisons, room ratios, or named entities.
"""
from __future__ import annotations

import re

from .glossary import LEVEL_TOKENS, STAFF_CATEGORY_TOKENS

NUMBER_WORDS = {
    'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6,
    'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11,
    'twelve': 12, 'fifteen': 15, 'twenty': 20,
}

_RANK_DESC_KEYWORDS = ('top', 'highest', 'most', 'largest', 'maximum', 'worst', 'best', 'max')
_RANK_ASC_KEYWORDS = ('bottom', 'lowest', 'least', 'smallest', 'minimum', 'min', 'fewest')
_RANK_KEYWORDS = _RANK_DESC_KEYWORDS + _RANK_ASC_KEYWORDS

_METRIC_KEYWORDS: list[tuple[tuple[str, ...], str]] = [
    (('net strength difference', 'nsd'), 'NSD'),
    (('strength difference', 'sd'), 'SD'),
    (('dropout percentage', 'dropouts percentage', 'drop out percentage',
      'dropout %', 'dropout percent', 'dpp', 'dropouts %', 'drop out %'), 'DPP'),
    (('dropout count', 'number of dropouts', 'total dropouts', 'total dropout', 'dropped out', 'dropouts', 'dropout', 'drop out', 'dp'), 'DP'),
    (('grant strength', 'gs'), 'GS'),
    (('student teacher ratio', 'student-teacher ratio', 'teacher ratio', 'str', 'performance gap', 'staff-to-student performance gap'), 'STR'),
    (('staff count', 'staff strength', 'no of staff', 'number of staff', 'total staff', 'staff', 'sc'), 'SC'),
    (('average strength per section', 'strength per section', 'students per section', 'student per section', 'sps', 'avg-sps', 'avg sps'), 'Avg-SPS'),
    (('number of sections', 'section count', 'sections', 'nos'), 'NOS'),
    (('occupied rooms', 'occupied room', 'occupied', 'noor'), 'NOOR'),
    (('vacant rooms', 'vacancy rooms', 'empty rooms', 'vacant room', 'empty room', 'vacancy', 'novr'), 'NOVR'),
    (('classrooms', 'class rooms', 'classroom', 'nocr'), 'NOCR'),
    (('room capacity', 'square feet', 'sq ft', 'arcs'), 'ARCS'),
    (('current-year strength', 'current year strength', 'current strength',
      'previous-year strength', 'previous year strength',
      'net strength', 'student strength', 'performance', 'overall performance', 'strength', 'ns'), 'NS'),
]

_LEVEL_PHRASES = {
    'pre primary': 'PP', 'pre-primary': 'PP',
    'primary school': 'PS',
    'high school': 'HS',
}

_STAFF_CATEGORY_PHRASES = {
    'activity staff': 'AC',
    'administration staff': 'AD',
    'admin staff': 'AD',
}

_YOY_EXPLICIT_PHRASES = (
    'compared with last year', 'compared to last year', 'compared with ly', 'compared to ly',
    'current year vs previous year', 'current year vs last year', 'current year versus last year',
    'current year versus previous year', 'current-year and previous-year', 'current year and previous year',
    'current year and last year', 'current-year and last-year', 'cy vs ly', 'cy versus ly', 'cy vs. ly',
    'year over year', 'year-over-year', 'yoy', 'year on year', 'y-o-y',
    'vs last year', 'versus last year', 'from last year', 'over last year', 'since last year',
    'change from last year', 'gain from last year', 'drop from last year',
    'from ly to cy', 'than last year', 'than ly',
)

_YOY_CHANGE_WORDS = (
    'improved', 'improvement', 'improving', 'improves',
    'increased', 'increase', 'increasing', 'increases', 'growth', 'grown', 'gained', 'gain',
    'declined', 'decline', 'declining', 'declines',
    'decreased', 'decrease', 'decreasing', 'decreases',
    'reduced', 'reduction', 'lost',
    'dropped', 'dropping',
    'changed', 'change', 'changes',
)

_YOY_ABSOLUTE_PHRASES = (
    'biggest change', 'largest change', 'most change', 'changed most',
    'highest change', 'maximum change', 'biggest difference', 'largest difference',
    'changed the most', 'biggest increase or decrease',
)

_YOY_NEGATIVE_KEYWORDS = (
    'declined', 'decline', 'declining', 'declines',
    'decreased', 'decrease', 'decreasing', 'decreases',
    'reduced', 'reduction', 'reduced their', 'lost strength', 'lost',
    'dropped', 'drop', 'dropping', 'negative', 'worst', 'lowest', 'bottom', 'least', 'loss',
)

_YOY_POSITIVE_KEYWORDS = (
    'improved', 'improvement', 'improving', 'improves',
    'increased', 'increase', 'increasing', 'increases',
    'higher dropout', 'higher strength',
    'growth', 'grow', 'gained', 'gain', 'positive', 'highest', 'top', 'best', 'most', 'largest',
)


def _word(token: str) -> re.Pattern:
    return re.compile(rf'\b{re.escape(token)}\b', re.IGNORECASE)


def extract_metric(question: str) -> str | None:
    """Canonical metric token (matches the METRIC segment of column names)."""
    q = question.lower()
    for keywords, metric in _METRIC_KEYWORDS:
        for kw in keywords:
            if len(kw) <= 4:
                if _word(kw).search(q):
                    return metric
            elif kw in q:
                return metric
    return None


def extract_multiple_metrics(question: str) -> list[str] | None:
    """Detect compound metric requests for a branch (e.g. dropout and strength details)."""
    q = question.lower()
    if 'dropout and strength' in q:
        return ['CY-DPP', 'CY-DP', 'CY-NS', 'CY-GS']
    if 'room and section' in q:
        return ['NOCR', 'NOOR', 'NOVR', 'NOS', 'Avg-SPS']
    if 'current and previous-year' in q or 'current and previous year' in q or 'current and ly' in q:
        return ['CY-NS', 'LY-NS', 'CY-DPP', 'LY-DPP', 'CY-GS', 'LY-GS', 'CY-SC', 'LY-SC']
    return None


def extract_level(question: str) -> str | None:
    """PP / PS / HS, or None if unspecified."""
    q = question.lower()
    for phrase, level in _LEVEL_PHRASES.items():
        if phrase in q:
            return level
    for token in LEVEL_TOKENS:
        if _word(token).search(q):
            return token
    return None


def extract_staff_category(question: str) -> str | None:
    """AC / AD staff category, or None if not mentioned."""
    q = question.lower()
    for phrase, category in _STAFF_CATEGORY_PHRASES.items():
        if phrase in q:
            return category
    for token in STAFF_CATEGORY_TOKENS:
        if _word(token).search(q):
            return token
    return None


def extract_type(question: str) -> str | None:
    """E (existing) / N (new) admission type."""
    q = question.lower()
    if 'existing' in q:
        return 'E'
    if 'new' in q:
        return 'N'
    return None


def extract_year(question: str) -> str | None:
    """CY / LY, or None if unspecified."""
    q = question.lower()
    if any(p in q for p in ('previous-year', 'previous year', 'last year', 'was the', 'ly')):
        return 'LY'
    if any(p in q for p in ('current-year', 'current year', 'current', 'this year', 'cy')):
        return 'CY'
    return None


def extract_n(question: str, default: int = 5) -> int:
    q = question.lower()
    match = re.search(r'\b(?:top|bottom)\s+(\d+)\b', q)
    if match:
        return int(match.group(1))
    match_which = re.search(r'\b(?:which)\s+(\d+)\b', q)
    if match_which:
        return int(match_which.group(1))
    for word, value in NUMBER_WORDS.items():
        if re.search(rf'\b(?:top|bottom|which)\s+{word}\b', q):
            return value
    return default


def extract_direction(question: str, default: str = 'desc') -> str:
    """'asc' or 'desc' -- sort direction implied by ranking language."""
    q = question.lower()
    if any(_word(kw).search(q) for kw in _RANK_ASC_KEYWORDS):
        return 'asc'
    if any(_word(kw).search(q) for kw in _RANK_DESC_KEYWORDS):
        return 'desc'
    return default


def is_yoy_question(question: str) -> bool:
    """True if question asks for year-over-year / CY vs LY comparison."""
    q = question.lower()
    if any(phrase in q for phrase in _YOY_EXPLICIT_PHRASES):
        return True
    if 'dropped out' in q or 'drop out' in q:
        return any(phrase in q for phrase in _YOY_EXPLICIT_PHRASES)
    if any(_word(w).search(q) for w in _YOY_CHANGE_WORDS):
        return True
    if 'compare' in q and any(y in q for y in ('year', 'cy', 'ly', 'annual', 'current-year', 'previous-year')):
        return True
    return False


def extract_yoy_direction(question: str) -> str:
    """Determine requested YoY direction."""
    q = question.lower()
    if any(phrase in q for phrase in _YOY_ABSOLUTE_PHRASES):
        return 'absolute'
    if any(_word(kw).search(q) for kw in _YOY_NEGATIVE_KEYWORDS):
        return 'negative'
    if any(_word(kw).search(q) for kw in _YOY_POSITIVE_KEYWORDS):
        return 'positive'
    return 'compare'


def extract_threshold(question: str) -> tuple[str, float, bool] | None:
    """Extract threshold condition (op, value, count_only)."""
    q = question.lower()
    count_only = 'how many' in q

    patterns = [
        (r'\b(?:above|greater than|more than|higher than|over)\s+(\d+(?:\.\d+)?)\s*(?:%|percent)?\b', 'gt'),
        (r'\b(?:below|less than|fewer than|under)\s+(\d+(?:\.\d+)?)\s*(?:%|percent)?\b', 'lt'),
        (r'\b(?:at least)\s+(\d+(?:\.\d+)?)\s*(?:%|percent)?\b', 'gte'),
        (r'\b(?:at most)\s+(\d+(?:\.\d+)?)\s*(?:%|percent)?\b', 'lte'),
        (r'\b(?:is|are)\s+(?:above|greater than|higher than)\s+(\d+(?:\.\d+)?)\s*(?:%|percent)?\b', 'gt'),
        (r'\b(?:is|are)\s+(?:below|less than|lower than)\s+(\d+(?:\.\d+)?)\s*(?:%|percent)?\b', 'lt'),
    ]
    for pat, op in patterns:
        m = re.search(pat, q)
        if m:
            return op, float(m.group(1)), count_only
    return None


def is_level_comparison(question: str) -> bool:
    """True if question compares education levels PP, PS and HS."""
    q = question.lower()
    if 'between pp, ps and hs' in q or 'pp, ps and hs' in q or 'pp, ps & hs' in q:
        return True
    if 'which category' in q and not ('existing' in q or 'new' in q):
        return True
    if 'pp' in q and 'ps' in q and 'hs' in q:
        return True
    return False


def is_type_comparison(question: str) -> bool:
    """True if question compares admission types Existing vs New (E vs N) or queries existing/new."""
    q = question.lower()
    if 'existing and new' in q or 'existing vs new' in q or 'existing or new' in q:
        return True
    if 'existing' in q or 'new student' in q or 'new students' in q:
        return True
    return False


def is_room_comparison(question: str) -> bool:
    """True if question compares occupied and empty rooms."""
    q = question.lower()
    return 'occupied and empty' in q or 'occupied vs empty' in q


def is_room_ratio_query(question: str) -> tuple[str, bool, bool] | None:
    """Returns (ratio_type, is_ranking, ascending) for occupancy/vacancy percentage queries."""
    q = question.lower()
    if 'occupancy percentage' in q or 'room occupancy percentage' in q or 'room occupancy' in q:
        is_ranking = any(w in q for w in ('highest', 'lowest', 'top', 'bottom'))
        asc = True if any(w in q for w in ('lowest', 'bottom')) else False
        return 'occupancy', is_ranking, asc
    if 'vacancy percentage' in q or 'vacant percentage' in q or 'room vacancy' in q:
        is_ranking = any(w in q for w in ('highest', 'lowest', 'top', 'bottom'))
        asc = True if any(w in q for w in ('lowest', 'bottom')) else False
        return 'vacancy', is_ranking, asc
    return None


def is_scope_total_query(question: str) -> bool:
    """True if question asks for total occupied/vacant rooms in current scope."""
    q = question.lower()
    return 'in the current scope' in q or 'in current scope' in q


def has_ranking_language(question: str) -> bool:
    q = question.lower()
    return any(_word(kw).search(q) for kw in _RANK_KEYWORDS) or 'fewest' in q


def extract_group_dimension(question: str) -> str | None:
    q = question.lower()
    if 'zone' in q:
        return 'zone'
    if 'agm' in q:
        return 'agm'
    if _word('ri').search(q) or 'ri name' in q or 'regional' in q or 'ris' in q:
        return 'ri'
    return None


def extract_aggregation(question: str, default: str = 'sum') -> str:
    q = question.lower()
    if any(p in q for p in ('average', 'avg', 'mean')):
        return 'mean'
    if any(p in q for p in ('count', 'how many branches', 'number of branches')):
        return 'count'
    return default


def extract_known_values(question: str, values) -> list[str]:
    """Extract known entity names matching case-insensitively with word boundaries."""
    q = question.lower()
    found = []
    seen = set()
    for value in sorted({str(v) for v in values if v and str(v).strip()}, key=len, reverse=True):
        needle = value.strip().lower()
        if not needle or needle in seen:
            continue
        if re.search(rf'\b{re.escape(needle)}\b', q):
            found.append(value)
            seen.add(needle)
    return found


def has_any(question: str, phrases) -> bool:
    q = question.lower()
    return any(p in q for p in phrases)
