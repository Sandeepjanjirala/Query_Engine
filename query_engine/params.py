"""
Natural-language parameter extraction.

Pure text -> parameter functions with no Django/pandas coupling. Each
function extracts dimensions needed across the 150-question set:
metric(s), level, type, year, N, sort direction, staff category,
group-by dimension, aggregation, threshold parameters, dimension
comparisons, room ratios, or named entities.
"""
from __future__ import annotations

import difflib
import re

from .glossary import LEVEL_TOKENS, STAFF_CATEGORY_TOKENS

NUMBER_WORDS = {
    'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6,
    'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11,
    'twelve': 12, 'fifteen': 15, 'twenty': 20,
}

_RANK_DESC_KEYWORDS = ('top', 'highest', 'higest', 'heighest', 'hightest', 'hight', 'most', 'largest', 'maximum', 'worst', 'best', 'max')
_RANK_ASC_KEYWORDS = ('bottom', 'lowest', 'least', 'smallest', 'minimum', 'min', 'fewest')
_RANK_KEYWORDS = _RANK_DESC_KEYWORDS + _RANK_ASC_KEYWORDS

_METRIC_KEYWORDS: list[tuple[tuple[str, ...], str]] = [
    (('surplus after salary', 'surplus', 'revenue minus salary', 'revenue after salary', 'net surplus'), 'SURPLUS'),
    (('salary-to-revenue ratio', 'salary-to-revenue percentage', 'salary vs revenue %', 'salary vs revenue', 'salary percentage', 'salary burden', 'percentage of revenue is spent on salary', 'percentage of revenue spent on salary', 'revenue spent on salary', 'spent on salary', 'sal_v_rev', 'tot_sal_v_rev'), 'SAL_V_REV'),
    (('cost per student', 'student cost', 'salary per student', 'cost per pupil', 'tot_cs', 'cs'), 'CS'),
    (('fee average', 'average fee', 'average student fee', 'weighted fee average', 'revenue per student', 'tot_fa', 'fa'), 'FA'),
    (('total employee salary cost', 'employee salary cost', 'employee cost', 'salary cost', 'salary', 'tot_sal', 'sal'), 'SAL'),
    (('total net revenue', 'net revenue', 'total revenue', 'revenue', 'income', 'earnings', 'tot_rev_n', 'rev_n'), 'REV_N'),
    ((
        'current year zero paid fee due', 'current year zero-paid fee due',
        'zero paid fee due', 'zero-paid fee due', 'cy zero paid fee due', 'cy zero-paid fee due',
        'zero-paid fee due balance', 'zero paid fee due balance',
        'zero-paid fee balance', 'zero paid fee balance',
        'zero-paid balance', 'zero paid balance',
        'zero-paid fee amount', 'zero paid fee amount',
        'zero-paid fee due amount', 'zero paid fee due amount',
        'zero-paid amount', 'zero paid amount',
        'cy_zp_fd',
    ), 'CY_ZP_FD'),
    (('fee paid but books not purchased', 'fee paid books not purchased', 'fp bn', 'cy_fp_bn'), 'CY_FP_BN'),
    (('fee not paid and books not purchased', 'fee not paid & books not purchased', 'fee not paid books not purchased', 'fn bn', 'cy_fn_bn'), 'CY_FN_BN'),
    (('last year fee due count', 'last year due count', '2024-25 fee due count', 'ly fee due count', 'ly_fdc'), 'LY_FDC'),
    ((
        'how many students have fee due', 'students have fee due', 'students with fee due',
        '2025-26 live student due count', '2025-26 due count', 'live student due count',
        'current year due count', 'cy due count', 'due count', 'fee due count', 'fee due student count', 'cy_a_fdc',
    ), 'CY_A_FDC'),
    (('last year fee due', '2024-25 fee due', 'ly fee due', 'ly_fd'), 'LY_FD'),
    (('2025-26 actual zero paid', 'actual zero paid count', 'actual zero paid', 'cy_a_zp'), 'CY_A_ZP'),
    ((
        'how many students have zero-paid', 'how many students have zero paid',
        'students have zero paid', 'students have zero-paid',
        'students with zero-paid fees', 'students with zero paid fees',
        'cy zero paid count', 'actual zero paid count', 'zero paid count',
        'zero-paid count', 'zero paid students', 'zero-paid students',
        'zero paid', 'zero-paid', 'cy_zp',
    ), 'CY_ZP'),
    ((
        '2025-26 live student fee due', 'live student fee due', 'current year fee due',
        'fee due balance', 'fee balance', 'fee due amount', 'fee amount', 'fee due', 'cy_a_fd',
    ), 'CY_A_FD'),
    (('net strength difference', 'nsd'), 'NSD'),
    (('strength difference', 'sd'), 'SD'),
    (('dropout percentage', 'dropouts percentage', 'drop out percentage',
      'dropout %', 'dropout percent', 'dpp', 'dropouts %', 'drop out %', 'doupouts percentage', 'droupouts percentage'), 'DPP'),
    (('dropout count', 'number of dropouts', 'total dropouts', 'total dropout', 'dropped out', 'dropouts', 'dropout', 'drop out', 'dp',
      'doupouts', 'droupout', 'drupouts', 'dopout', 'dopouts'), 'DP'),
    (('grant strength', 'gs'), 'GS'),
    (('teacher student ratio', 'teacher-student ratio', 'student teacher ratio', 'student-teacher ratio', 'teacher ratio', 'str', 'performance gap', 'staff-to-student performance gap', 'tot_str'), 'STR'),
    (('staff count', 'staff strength', 'no of staff', 'number of staff', 'total staff', 'staff', 'sc', 'tot_sc'), 'SC'),
    (('average strength per section', 'strength per section', 'students per section', 'student per section', 'sps', 'avg-sps', 'avg sps'), 'Avg-SPS'),
    (('number of sections', 'section count', 'sections', 'nos'), 'NOS'),
    (('occupied rooms', 'occupied room', 'occupied', 'noor'), 'NOOR'),
    (('vacant rooms', 'vacancy rooms', 'empty rooms', 'vacant room', 'empty room', 'vacancy', 'novr'), 'NOVR'),
    (('classrooms', 'class rooms', 'classroom', 'nocr'), 'NOCR'),
    (('room capacity', 'square feet', 'sq ft', 'arcs'), 'ARCS'),
    (('current-year strength', 'current year strength', 'current strength',
      'previous-year strength', 'previous year strength',
      'net strength', 'student strength', 'performance', 'overall performance', 'strength', 'ns', 'tot_ns'), 'NS'),
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
    'last year and current year', '2024-25 and 2025-26', '2024-25 vs 2025-26',
    'compare last year and current year', 'compare 2024-25 and 2025-26',
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

_YOY_IMPROVEMENT_KEYWORDS = (
    'improved', 'improvement', 'improving', 'improves', 'better',
)

_YOY_POSITIVE_KEYWORDS = (
    'increased', 'increase', 'increasing', 'increases',
    'higher dropout', 'higher strength',
    'growth', 'grow', 'gained', 'gain', 'positive', 'highest', 'top', 'best', 'most', 'largest',
)


def _word(token: str) -> re.Pattern:
    return re.compile(rf'\b{re.escape(token)}\b', re.IGNORECASE)


def extract_metric(question: str) -> str | None:
    """Canonical metric token (matches the METRIC segment of column names)."""
    q = question.lower()
    # Explicit disambiguation: zero-paid count vs zero-paid balance
    if any(k in q for k in ('zero-paid fee due count', 'zero paid fee due count', 'zero paid count', 'zero-paid count')):
        return 'CY_ZP'
    # Explicit disambiguation: "how many students have fee due" is student count (CY_A_FDC / LY_FDC), not currency amount
    if any(k in q for k in ('how many students', 'student count', 'number of students', 'students have', 'count of students')) and 'due' in q and not any(z in q for z in ('zero-paid', 'zero paid', 'books')):
        return 'LY_FDC' if any(y in q for y in ('last year', '2024-25', 'previous year', 'prior year')) else 'CY_A_FDC'
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
    has_cy = (
        any(p in q for p in ('current-year', 'current year', 'this year', 'present year'))
        or bool(re.search(r'\b(?:cy|cy-dpp|cy_dpp)\b', q))
    )
    has_ly = (
        any(p in q for p in ('previous-year', 'previous year', 'last year', 'past year', 'prior year', 'was the'))
        or bool(re.search(r'\b(?:ly|ly-dpp|ly_dpp)\b', q))
    )
    if has_cy and not has_ly:
        return 'CY'
    if has_ly and not has_cy:
        return 'LY'
    if has_cy and has_ly:
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


def extract_explicit_n(question: str) -> int | None:
    """
    Extracts an explicit rank limit N from the question (e.g. 'top 5', 'which 5', 'top 10', 'highest 3').
    Returns None if no explicit number was requested, indicating an unbounded query.
    """
    q = question.lower()
    match = re.search(r'\b(?:top|bottom|which|highest|lowest|best|worst)\s+(\d+)\b', q)
    if match:
        return int(match.group(1))
    match_branches = re.search(r'\b(\d+)\s+(?:branches|ris|agms|zones)\b', q)
    if match_branches:
        return int(match_branches.group(1))
    for word, value in NUMBER_WORDS.items():
        if re.search(rf'\b(?:top|bottom|which|highest|lowest|best|worst)\s+{word}\b', q):
            return value
        if re.search(rf'\b{word}\s+(?:branches|ris|agms|zones)\b', q):
            return value
    return None


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
    if 'compare' in q and (
        any(y in q for y in ('year', 'annual', 'current-year', 'previous-year', '2024-25', '2025-26', 'last year'))
        or bool(re.search(r'\b(?:cy|ly)\b', q))
    ):
        return True
    return False


def extract_yoy_direction(question: str) -> str:
    """Determine requested YoY direction."""
    q = question.lower()
    if any(phrase in q for phrase in _YOY_ABSOLUTE_PHRASES):
        return 'absolute'
    if any(_word(kw).search(q) for kw in _YOY_NEGATIVE_KEYWORDS):
        return 'negative'
    if any(_word(kw).search(q) for kw in _YOY_POSITIVE_KEYWORDS) or any(_word(kw).search(q) for kw in _YOY_IMPROVEMENT_KEYWORDS):
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
    if any(p in q for p in (
        'between pp, ps and hs', 'pp, ps and hs', 'pp, ps & hs',
        'school level', 'school levels', 'education level', 'education levels',
        'which school level', 'what school level', 'which level', 'what level',
        'by school level', 'by level', 'across school levels', 'across levels',
        'level-wise', 'level wise', 'level breakdown', 'level comparison',
    )):
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
    has_branch_dim = any(b in q for b in ('branch', 'branches'))

    # 1) Direct target questions for group hierarchies
    if any(k in q for k in ('which ris', 'which ri', 'what ri', 'what ris')):
        return 'ri'
    if any(k in q for k in ('which agms', 'which agm', 'what agm', 'what agms')):
        return 'agm'
    if any(k in q for k in ('which zones', 'which zone', 'what zone', 'what zones')):
        return 'zone'

    # 2) Explicit target prepositions ('by <dim>', 'per <dim>', 'across <dim>')
    if any(k in q for k in ('by ri', 'by ris', 'per ri', 'across ris', 'ri wise', 'ri-wise')):
        return 'ri'
    if any(k in q for k in ('by zone', 'by zones', 'per zone', 'across zones', 'zone wise', 'zone-wise')):
        return 'zone'
    if any(k in q for k in ('by agm', 'by agms', 'per agm', 'across agms', 'agm wise', 'agm-wise')):
        return 'agm'

    # 3) Education / Admission level
    if any(k in q for k in (
        'school level', 'school levels', 'education level', 'education levels',
        'which school level', 'what school level', 'by school level', 'by level',
        'across school levels', 'across levels', 'level-wise', 'level wise'
    )):
        return 'level'

    if any(k in q for k in ('branch type', 's_type', 'admission type', 'student type', 's type', 'by type', 'by branch type')):
        return 's_type'

    # 4) Standalone dimension keyword (only if not used in filter context like 'in', 'for', 'under', 'within', and not a branch query)
    if 'zone' in q and not has_branch_dim and not any(p in q for p in ('in ', 'for ', 'under ', 'within ')):
        return 'zone'

    if 'agm' in q and not has_branch_dim and not any(p in q for p in ('in ', 'for ', 'under ', 'within ')):
        return 'agm'

    if (_word('ri').search(q) or 'regional' in q or 'ris' in q) and not has_branch_dim and not any(p in q for p in ('in ', 'for ', 'under ', 'within ')):
        return 'ri'

    return None


def extract_operation(question: str) -> str:
    """
    Explicit operation detector returning canonical operation type:
      'total' | 'count' | 'group_by' | 'ranking' | 'highest_lowest' | 'comparison' | 'difference' | 'threshold' | 'percentage'
    """
    q = question.lower()
    if extract_threshold(q) is not None or any(t in q for t in ('greater than', 'more than', 'exceeding', 'above', 'below', 'less than', 'under', 'crore', 'lakh')):
        return 'threshold'
    if is_yoy_question(q) or 'compare' in q or 'versus' in q or ' vs ' in q:
        return 'comparison'
    if any(k in q for k in ('difference', 'change', 'gain', 'reduction')):
        return 'difference'
    if has_ranking_language(q) or any(k in q for k in ('top', 'bottom', 'rank', 'ranked')):
        return 'ranking'
    if any(k in q for k in ('highest', 'lowest', 'best', 'worst', 'most', 'least')):
        return 'highest_lowest'
    if extract_group_dimension(q) is not None or 'by branch' in q or 'branch-wise' in q:
        return 'group_by'
    if any(k in q for k in ('percentage', 'percent', '%', 'ratio')):
        return 'percentage'
    if any(k in q for k in ('count', 'number of', 'how many')):
        return 'count'
    return 'total'


def extract_aggregation(question: str, default: str = 'sum') -> str:
    q = question.lower()
    if any(p in q for p in ('average', 'avg', 'mean')):
        return 'mean'
    if any(p in q for p in ('how many branches', 'number of branches', 'count of branches', 'how many zones', 'how many ris', 'how many agms')):
        return 'count'
    return default


def normalize_entity_name(s: str) -> str:
    """Normalize text for entity matching: lowercase, strip honorifics, strip punctuation, collapse spaces, convert word numbers to digits."""
    if not s:
        return ""
    s = str(s).lower().strip()
    s = re.sub(r'^(mr\.|mr\s+|mrs\.|mrs\s+|dr\.|dr\s+)', '', s)
    s = re.sub(r'[._\-,]+', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    words = s.split()
    converted = [str(NUMBER_WORDS[w]) if w in NUMBER_WORDS else w for w in words]
    return ' '.join(converted)


_normalize_entity_string = normalize_entity_name


def resolve_single_entity(query_text: str, candidate_entities, entity_type: str = 'branch') -> str | None:
    """
    Resolves the intended entity from `query_text` against `candidate_entities`.
    Returns the exact canonical string from `candidate_entities` if matched, else None.
    
    Priority Matching:
    1. Exact normalized phrase match in query (longest match wins).
    2. High-confidence fuzzy match (>= 80%).
    3. Moderate-confidence fuzzy match (70-79%) if single clear winner.
    """
    candidates = [str(c).strip() for c in candidate_entities if c and str(c).strip()]
    if not candidates:
        return None

    norm_q = normalize_entity_name(query_text)
    if not norm_q:
        return None
    
    query_digits = set(re.findall(r'\b\d+\b', norm_q))

    # -------------------------------------------------------------
    # Step A: Exact / Word-Boundary Phrase Match (Longest Wins)
    # -------------------------------------------------------------
    exact_matches = []
    for raw_cand in candidates:
        norm_cand = normalize_entity_name(raw_cand)
        if not norm_cand:
            continue
        
        cand_digits = set(re.findall(r'\b\d+\b', norm_cand))
        if cand_digits and not cand_digits.issubset(query_digits):
            if cand_digits == {'1'}:
                cand_base = re.sub(r'\b1\b', '', norm_cand).strip()
                sibling_exists = any(normalize_entity_name(c) == cand_base for c in candidates)
                if not sibling_exists and re.search(r'\b' + re.escape(cand_base) + r'\b', norm_q):
                    exact_matches.append((raw_cand, cand_base, len(cand_base)))
            continue

        pattern = r'\b' + re.escape(norm_cand) + r'\b'
        if re.search(pattern, norm_q):
            exact_matches.append((raw_cand, norm_cand, len(norm_cand)))

    if exact_matches:
        exact_matches.sort(key=lambda x: x[2], reverse=True)
        return exact_matches[0][0]

    # For person names (RI / AGM), check strategy for token-set match or main-name token match
    if entity_type in ('ri', 'agm'):
        common_name_suffixes = {'rao', 'krishna', 'kumar', 'reddy', 'singh', 'sharma', 'mr', 'mrs', 'dr'}
        person_matches = []
        for raw_cand in candidates:
            norm_cand = normalize_entity_name(raw_cand)
            cand_digits = set(re.findall(r'\b\d+\b', norm_cand))
            if cand_digits and not cand_digits.issubset(query_digits):
                continue
            tokens = [t for t in norm_cand.split() if len(t) > 1]
            if tokens:
                if all(re.search(r'\b' + re.escape(t) + r'\b', norm_q) for t in tokens):
                    person_matches.append((raw_cand, 100, len(norm_cand)))
                elif any(len(t) >= 3 and t not in common_name_suffixes and re.search(r'\b' + re.escape(t) + r'\b', norm_q) for t in tokens):
                    person_matches.append((raw_cand, 80, len(norm_cand)))
        if person_matches:
            person_matches.sort(key=lambda x: (x[1], x[2]), reverse=True)
            return person_matches[0][0]

    # For branch names, check if distinctive branch token matches in question (e.g. 'Miyapur' -> 'MIYAPUR FUTURE PATHWAYS')
    if entity_type == 'branch':
        branch_matches = []
        for raw_cand in candidates:
            norm_cand = normalize_entity_name(raw_cand)
            cand_digits = set(re.findall(r'\b\d+\b', norm_cand))
            if cand_digits and not cand_digits.issubset(query_digits):
                continue
            tokens = [t for t in norm_cand.split() if len(t) >= 4]
            if tokens:
                if any(re.search(r'\b' + re.escape(t) + r'\b', norm_q) for t in tokens[:2]):
                    branch_matches.append((raw_cand, 90, len(norm_cand)))
        if branch_matches:
            branch_matches.sort(key=lambda x: (x[1], x[2]), reverse=True)
            return branch_matches[0][0]

    # -------------------------------------------------------------
    # Step B & C: Fuzzy Matching
    # -------------------------------------------------------------
    stopwords = {
        'statistics', 'statistic', 'stats', 'show', 'give', 'of', 'branch', 'branches',
        'ri', 'ris', 'agm', 'agms', 'zone', 'zones', 'the', 'analyze', 'analysis',
        'review', 'performance', 'summary', 'scorecard', 'report', 'details', 'for',
        'in', 'at', 'please', 'me', 'what', 'is', 'are', 'highest', 'lowest', 'top',
        'which', 'does', 'belong', 'to', 'how', 'many', 'much', 'percentage', 'count',
        'dropout', 'dropouts', 'drop', 'fee', 'due', 'dues', 'revenue', 'salary', 'str'
    }
    q_words = [w for w in norm_q.split() if w not in stopwords]
    clean_q = ' '.join(q_words).strip()
    
    if not clean_q:
        return None

    scores = []
    for raw_cand in candidates:
        norm_cand = normalize_entity_name(raw_cand)
        if not norm_cand:
            continue
        
        cand_digits = set(re.findall(r'\b\d+\b', norm_cand))
        if cand_digits and not cand_digits.issubset(query_digits):
            continue

        ratio = difflib.SequenceMatcher(None, clean_q, norm_cand).ratio()
        
        cand_tokens = norm_cand.split()
        if len(q_words) == 1:
            w = q_words[0]
            for ct in cand_tokens:
                token_ratio = difflib.SequenceMatcher(None, w, ct).ratio()
                if token_ratio > ratio:
                    ratio = token_ratio
        
        scores.append((raw_cand, ratio))

    scores.sort(key=lambda x: x[1], reverse=True)

    if not scores:
        return None

    best_cand, best_score = scores[0]
    second_score = scores[1][1] if len(scores) > 1 else 0.0

    if best_score >= 0.80:
        return best_cand

    if 0.70 <= best_score < 0.80:
        if (best_score - second_score) >= 0.10:
            return best_cand

    return None


def extract_known_values(question: str, values, entity_type: str = 'branch') -> list[str]:
    """Extract known entity names using exact normalized matching and tiered fuzzy matching."""
    res = resolve_single_entity(question, values, entity_type=entity_type)
    return [res] if res else []


def has_any(question: str, phrases) -> bool:
    q = question.lower()
    return any(p in q for p in phrases)


def extract_academic_segment(question: str) -> str | None:
    """Extract academic segment code (PP, LPS, UPS, HS, ACD, AD_AC, TOT) from question."""
    q = question.lower()
    if 'lower primary' in q or 'lps' in q:
        return 'LPS'
    if 'upper primary' in q or 'ups' in q:
        return 'UPS'
    if 'pre primary' in q or 'pre-primary' in q:
        return 'PP'
    if 'high school' in q or 'hs' in q:
        return 'HS'
    if 'activity' in q or 'admin' in q or 'ad_ac' in q:
        return 'AD_AC'
    if 'acd' in q:
        return 'ACD'
    if 'primary' in q:
        return 'PP'
    return None


def extract_target_metric(question: str, metric_param: str | None = None) -> str:
    """
    Detects the requested metric intent from the natural language question
    for output projection across Fee Due, Revenue vs Salary, and Branch Analytics.
    """
    q = question.lower()
    m = (metric_param or '').upper()

    # Fee Due target metrics - check YoY comparison and specific counts first
    if any(p in q for p in ('compare fee', 'fee yoy', 'fee change', 'fee comparison', 'fee due comparison', 'last year and current year fee', 'compare last year and current year', 'compare 2024-25 and 2025-26')):
        return 'fee_yoy'
    if any(p in q for p in ('paid but books not purchased', 'fee paid books not purchased', 'fp bn', 'cy_fp_bn')):
        return 'CY_FP_BN'
    if any(p in q for p in ('did not pay fee and did not purchase books', 'fee not paid and books not purchased', 'fee not paid & books not purchased', 'not paid and books not purchased', 'fn bn', 'cy_fn_bn')):
        return 'CY_FN_BN'
    if any(p in q for p in ('books not purchased', 'books not bought', 'books summary')):
        return 'books_summary'

    # Check zero-paid fee amount vs zero-paid count
    if any(p in q for p in ('zero-paid fee amount', 'zero paid fee amount', 'zero-paid fee due', 'zero paid fee due', 'zero-paid fee due amount', 'zero paid fee due amount', 'highest zero-paid fee amount', 'highest zero paid fee amount', 'highest zero-paid fee due', 'highest zero paid fee due', 'zero-paid fee due balance', 'zero paid fee due balance', 'cy_zp_fd')) and 'count' not in q:
        return 'CY_ZP_FD'
    if any(p in q for p in ('zero paid count', 'zero-paid count', 'zero paid fee count', 'zero paid fee due count', 'zero-paid fee due count', 'highest zero-paid count', 'highest zero paid count', 'cy_zp')) or ('zero paid' in q or 'zero-paid' in q):
        return 'CY_ZP'
    if any(p in q for p in ('actual zero paid count', 'actual zero paid', 'cy_a_zp')):
        return 'CY_A_ZP'
    if any(p in q for p in ('zero-paid fee amount', 'zero paid fee amount', 'zero paid fee due amount', 'highest zero-paid fee amount', 'highest zero paid fee amount', 'zero paid fee due', 'cy_zp_fd')):
        return 'CY_ZP_FD'

    # Due count vs Due fee amount
    if any(p in q for p in ('last year fee due count', 'last year due count', '2024-25 fee due count', '2024-25 due count', 'ly_fdc')):
        return 'LY_FDC'
    if any(p in q for p in ('2025-26 live student due count', '2025-26 due count', 'live student due count', 'current year due count', 'cy due count', 'due count', 'cy_a_fdc')):
        return 'CY_A_FDC'

    if any(p in q for p in ('last year fee due', 'last year 2024-25 fee due', '2024-25 fee due', '2024-25 fee', 'last year due', 'ly_fd')):
        return 'LY_FD'
    if any(p in q for p in ('2025-26 live student fee due', '2025-26 fee due', 'live student fee due', 'active fee due', 'current year fee due', 'cy_a_fd', 'cy_fd')):
        return 'CY_A_FD'

    # Revenue vs Salary target metrics
    if any(p in q for p in ('employee salary cost', 'employee salary', 'salary cost', 'total employee salary cost')):
        return 'total_salary'
    if any(p in q for p in ('student teacher ratio', 'student-teacher ratio', 'str', 'teacher ratio', 'student staff ratio')):
        return 'student_teacher_ratio'
    if any(p in q for p in ('cost per student', 'cost per pupil', 'salary per student', 'student cost')):
        return 'cost_per_student'
    if any(p in q for p in ('fee average', 'average fee', 'revenue per student')):
        return 'fee_average'
    if any(p in q for p in ('salary vs revenue', 'sal vs rev', 'salary ratio', 'salary burden', 'salary percentage', 'salary-to-revenue', 'percentage of revenue is spent on salary', 'percentage of revenue spent on salary', 'revenue spent on salary', 'spent on salary')):
        return 'salary_vs_revenue_pct'
    if any(p in q for p in ('surplus', 'net surplus', 'revenue minus salary', 'revenue after salary')):
        return 'surplus'
    if any(p in q for p in ('student count', 'total student', 'total students', 'number of students')):
        return 'total_students'
    if any(p in q for p in ('employee count', 'total employee', 'total employees', 'number of employees', 'staff count')):
        return 'total_employees'

    # Single-word metric checks
    if 'salary' in q and 'revenue' not in q:
        return 'total_salary'
    if 'revenue' in q and 'salary' not in q:
        return 'total_revenue'
    if 'students' in q and not any(k in q for k in ('cost', 'ratio', 'fee')):
        return 'total_students'
    if 'employees' in q and not any(k in q for k in ('cost', 'ratio', 'salary')):
        return 'total_employees'

    # Metric parameter fallback
    if m in ('LY_FD',):
        return 'LY_FD'
    if m in ('LY_FDC',):
        return 'LY_FDC'
    if m in ('CY_A_FD',):
        return 'CY_A_FD'
    if m in ('CY_A_FDC',):
        return 'CY_A_FDC'
    if m in ('CY_A_ZP',):
        return 'CY_A_ZP'
    if m in ('CY_ZP',):
        return 'CY_ZP'
    if m in ('CY_ZP_FD',):
        return 'CY_ZP_FD'
    if m in ('CY_FP_BN',):
        return 'CY_FP_BN'
    if m in ('CY_FN_BN',):
        return 'CY_FN_BN'
    if m in ('NS', 'TOT_NS', 'STUDENTS'):
        return 'total_students'
    if m in ('SC', 'TOT_SC', 'EMPLOYEES'):
        return 'total_employees'
    if m in ('SAL', 'TOT_SAL', 'SALARY'):
        return 'total_salary'
    if m in ('REV_N', 'TOT_REV_N', 'REVENUE'):
        return 'total_revenue'
    if m in ('SURPLUS', 'NET_SURPLUS'):
        return 'surplus'
    if m in ('CS', 'TOT_CS', 'COST_PER_STUDENT'):
        return 'cost_per_student'
    if m in ('FA', 'TOT_FA', 'FEE_AVERAGE'):
        return 'fee_average'
    if m in ('SAL_V_REV', 'TOT_SAL_V_REV', 'SALARY_VS_REVENUE'):
        return 'salary_vs_revenue_pct'
    if m in ('STR', 'TOT_STR', 'STUDENT_TEACHER_RATIO'):
        return 'student_teacher_ratio'

    if 'revenue' in q and 'salary' in q:
        return 'revenue_vs_salary'

    return 'summary'


def extract_compared_segments(question: str) -> list[str]:
    """Extract segment codes mentioned in comparison questions (e.g. PP, LPS, UPS, HS, ACD, AD_AC)."""
    q = question.lower()
    found = []
    if 'pre primary' in q or 'pre-primary' in q or 'pp' in q.split():
        found.append('PP')
    if 'lower primary' in q or 'lps' in q.split():
        found.append('LPS')
    if 'upper primary' in q or 'ups' in q.split():
        found.append('UPS')
    if 'high school' in q or 'hs' in q.split():
        found.append('HS')
    if 'activity' in q or 'admin' in q or 'ad_ac' in q:
        found.append('AD_AC')
    if 'acd' in q.split():
        found.append('ACD')
    return found


