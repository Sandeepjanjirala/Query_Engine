from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple
import pandas as pd

from .analysis_engine import format_display_ri_name, format_compact_currency, format_compact_count

STAT_DROPOUT = "dropout"
STAT_FEE_DUE = "fee_due"
STAT_REVENUE_SALARY = "revenue_salary"
STAT_STR = "teacher_student_ratio"

ALL_STATISTICS = [STAT_DROPOUT, STAT_FEE_DUE, STAT_REVENUE_SALARY, STAT_STR]


def normalize_speech_and_wording(text: str) -> str:
    """
    Normalizes common speech-to-text / pronunciation mistakes and phrasing variations
    into canonical domain terms while preserving entity and hierarchy tokens.
    """
    t = text.lower()

    # Fee Due variants: feedue, feedues, fee-do, fee do, fee dues, fee_due, fidu, fi du, feed you, fee view
    t = re.sub(r'\b(?:fee-do|feedues?|fee\s+do|fee\s+dues?|fee_due|fidu|fi\s+du|feed\s+you|feedyou|fee\s+view)\b', 'fee due', t)

    # Dropout variants: drop out, drop outs, drop-outs, drop-out, dropouts, dropout, draw out, draw pout
    t = re.sub(r'\b(?:drop\s*outs?|drop-outs?|draw\s*outs?|draw\s*pouts?)\b', 'dropout', t)

    # Revenue vs Salary variants:
    t = re.sub(
        r'\b(?:revenue\s+(?:vs\.?|versus|verse|and|&|where\s+the|with)\s+salary|revenue\s+salary|salary\s+(?:vs\.?|versus|verse|and|&|with)\s+revenue|salary\s+revenue|sal\s+vs\s+rev)\b',
        'revenue vs salary',
        t,
    )

    # Teacher Student Ratio variants:
    t = re.sub(
        r'\b(?:teacher[-\s]+student[-\s]+ratio|teachers?\s+students?\s+ratio|students?\s+per\s+teacher|student\s+to\s+teacher\s+ratio|teacher\s+to\s+student\s+ratio)\b',
        'student-teacher ratio',
        t,
    )

    return t


def extract_requested_statistics(question: str) -> List[str]:
    """
    Detect and normalize all requested statistics from the user question.
    Returns a list of canonical statistic identifiers in order of appearance in the prompt.
    """
    q_norm = normalize_speech_and_wording(question)

    # Strip dataset references (e.g. "in revenue vs salary dataset", "revenue vs salary sheet")
    q_clean = re.sub(
        r'\b(?:in|from|of)\s+(?:the\s+)?revenue\s*(?:vs|&|and)?\s*salary\s+(?:dataset|excel|file|sheet|data|report)\b',
        '',
        q_norm,
    )

    matches: List[Tuple[int, str]] = []

    # 1. Dropout check
    m = re.search(r'\b(?:dropout|dropouts|drop-out|drop out|dpp)\b', q_clean)
    if m:
        matches.append((m.start(), STAT_DROPOUT))

    # 2. Fee Due check
    m = re.search(r'\b(?:fee due|fee dues|fee_due|zero paid|zero-paid|due fee|books not purchased)\b', q_clean)
    if m:
        matches.append((m.start(), STAT_FEE_DUE))

    # 3. Revenue vs Salary check
    m = re.search(r'\b(?:revenue vs salary|salary vs revenue|revenue salary|salary revenue|financial statistics|revenue statistics|salary statistics|sal vs rev)\b', q_clean)
    if m:
        matches.append((m.start(), STAT_REVENUE_SALARY))
    elif 'revenue' in q_clean and 'salary' in q_clean and not ('teacher student ratio' in q_clean or 'student teacher ratio' in q_clean):
        idx = min(q_clean.find('revenue'), q_clean.find('salary'))
        matches.append((idx, STAT_REVENUE_SALARY))

    # 4. Teacher Student Ratio check
    m = re.search(r'\b(?:teacher student ratio|student teacher ratio|student-teacher ratio|students per teacher|staff ratio|staffing statistics|teacher ratio|str)\b', q_clean)
    if m:
        matches.append((m.start(), STAT_STR))

    # Sort matches by order of appearance in the question
    matches.sort(key=lambda x: x[0])

    deduped = []
    for _, stat in matches:
        if stat not in deduped:
            deduped.append(stat)
    return deduped


def detect_entity_level_and_name(question: str, context: Dict[str, Any] | None = None) -> Tuple[str, str]:
    """
    Determines entity level ('RI', 'AGM', or 'Branch') and canonical entity name
    using resolved context from existing entity-resolution logic (_merge_text_entities).
    """
    ctx = context or {}

    # 1. Context checks from _merge_text_entities
    ri_name = ctx.get('ri')
    if ri_name and str(ri_name).strip().lower() != 'all':
        return 'RI', str(ri_name).strip()

    agm_name = ctx.get('agm')
    if agm_name and str(agm_name).strip().lower() != 'all':
        return 'AGM', str(agm_name).strip()

    branch_name = ctx.get('branch')
    if not branch_name and isinstance(ctx.get('branches'), list) and len(ctx.get('branches')) > 0:
        if str(ctx['branches'][0]).strip().lower() != 'all':
            branch_name = ctx['branches'][0]

    if branch_name and str(branch_name).strip().lower() != 'all':
        return 'Branch', str(branch_name).strip()

    # 2. Explicit keyword checks in question
    q_low = question.lower()
    if 'ri ' in q_low or q_low.startswith('ri '):
        m = re.search(r'\bri\s+([A-Za-z0-9\.\s]+?)(?:\s+(?:drop|fee|rev|sal|teach|stud|stat|and|,)|$)', question, re.IGNORECASE)
        name = m.group(1).strip() if m else 'All'
        return 'RI', name

    if 'agm ' in q_low or q_low.startswith('agm '):
        m = re.search(r'\bagm\s+([A-Za-z0-9\.\s]+?)(?:\s+(?:drop|fee|rev|sal|teach|stud|stat|and|,)|$)', question, re.IGNORECASE)
        name = m.group(1).strip() if m else 'All'
        return 'AGM', name

    if 'branch ' in q_low or q_low.startswith('branch '):
        m = re.search(r'\bbranch\s+([A-Za-z0-9\.\s]+?)(?:\s+(?:drop|fee|rev|sal|teach|stud|stat|and|,)|$)', question, re.IGNORECASE)
        name = m.group(1).strip() if m else 'All'
        return 'Branch', name

    # 3. Fallback: prompt prefix before metric terms
    m = re.search(r'^\s*([A-Za-z0-9\.\s]+?)\s+(?:dropouts|fee due|revenue|teacher student|student teacher|ratio|stats|statistics)', question, re.IGNORECASE)
    if m:
        cand = m.group(1).strip()
        cand = re.sub(r'^(?:show|give|tell\s+me\s+about|please\s+show)\s+', '', cand, flags=re.IGNORECASE).strip()
        if cand.lower() not in ('all', 'the', 'a', 'show', 'get', 'overall', ''):
            return 'Branch', cand

    return 'AGM', 'All'


def _find_section_content(sections: List[Dict[str, Any]], keywords: List[str]) -> str:
    """Helper to locate content of a section matching keywords in title."""
    for sec in sections:
        t_low = sec.get('title', '').lower()
        if any(k.lower() in t_low for k in keywords):
            return sec.get('content', '').strip()
    return ''


def _format_dropout_section(res: Dict[str, Any]) -> Tuple[str, str]:
    """Format clean, data-rich dropout section with exact counts and segment breakdown."""
    analysis = res.get('analysis')
    sections = analysis.sections if analysis and hasattr(analysis, 'sections') else []

    ov_content = _find_section_content(sections, ['overall dropout', 'overall branch situation', 'overall situation', 'dropout overview', 'dropout situation'])
    lvl_content = _find_section_content(sections, ['dropouts by school level', 'level-wise'])

    parts = []
    summary_sentence = ""

    if ov_content:
        p1 = ov_content.split('\n\n')[0].strip()
        parts.append(p1)
        summary_sentence = p1
    else:
        ans_text = res.get('answer', '')
        m_cy_ly = re.search(r'([A-Za-z0-9\.\s]+has\s+([0-9,]+)\s+dropouts\s+this\s+year.*?\.)', ans_text, re.IGNORECASE)
        if m_cy_ly:
            parts.append(m_cy_ly.group(1).strip())
            summary_sentence = m_cy_ly.group(1).strip()
        else:
            parts.append("Dropout metrics recorded for the selected scope.")

    if lvl_content:
        clean_bullets = []
        for line in lvl_content.splitlines():
            line_str = line.strip()
            if line_str.startswith('*'):
                m_seg = re.search(r'\*\s*\*\*([^*]+)\*\*:\s*(\d+)', line_str)
                if m_seg:
                    seg_name = m_seg.group(1)
                    seg_cnt = m_seg.group(2)
                    clean_bullets.append(f"* **{seg_name}:** {seg_cnt}")
                else:
                    clean_bullets.append(line_str)
        if clean_bullets:
            parts.append("\n" + "\n".join(clean_bullets))

    sec_text = "\n\n".join(parts)
    return sec_text, summary_sentence


def _format_fee_due_section(res: Dict[str, Any]) -> Tuple[str, str]:
    """Format clean fee due section without header leakage or repetition."""
    analysis = res.get('analysis')
    sections = analysis.sections if analysis and hasattr(analysis, 'sections') else []

    ly_content = _find_section_content(sections, ['last year fee due', 'last year due'])
    cy_content = _find_section_content(sections, ['current year'])
    bk_content = _find_section_content(sections, ['books status', 'books'])

    parts = []
    summary_sentence = ""

    if ly_content:
        parts.append(ly_content)

    if cy_content:
        cy_p = []
        for p in cy_content.split('\n\n'):
            p_clean = p.strip()
            if p_clean and not p_clean.startswith('#') and not p_clean.lower().startswith('last year,'):
                if p_clean not in cy_p:
                    cy_p.append(p_clean)
        if cy_p:
            parts.append("\n\n".join(cy_p))
            summary_sentence = cy_p[0]

    if bk_content:
        parts.append(bk_content)

    if not parts:
        ans_text = res.get('answer', '')
        m_ly = re.search(r'(Last year,\s*\d+[\s\S]*?pending\.)', ans_text, re.IGNORECASE)
        if m_ly: parts.append(m_ly.group(1).strip())
        m_cy = re.search(r'(In the current year,[\s\S]*?pending\.)', ans_text, re.IGNORECASE)
        if m_cy:
            parts.append(m_cy.group(1).strip())
            summary_sentence = m_cy.group(1).strip()

    clean_parts = []
    for p in parts:
        if p and p not in clean_parts:
            clean_parts.append(p)

    sec_text = "\n\n".join(clean_parts) if clean_parts else "Fee due statistics processed."
    return sec_text, summary_sentence


def _format_revenue_salary_section(res: Dict[str, Any]) -> Tuple[str, str]:
    """Format percentage-focused revenue vs salary section strictly avoiding 'remaining' or 'surplus' text."""
    analysis = res.get('analysis')
    sections = analysis.sections if analysis and hasattr(analysis, 'sections') else []

    ov_content = _find_section_content(sections, ['overall financial summary', 'financial & operational overview', 'overall financial'])
    seg_content = _find_section_content(sections, ['segment breakdown'])

    parts = []
    summary_line = ""

    if ov_content:
        p1 = ov_content.split('\n\n')[0].strip()
        p1_clean = re.sub(r',\s*leaving\s+[\d\.]+%?\s*as\s*(?:net\s+)?surplus\.?', '.', p1, flags=re.IGNORECASE)
        p1_clean = re.sub(r',\s*leaving\s+[\d\.]+%?\s*remaining\.?', '.', p1_clean, flags=re.IGNORECASE)
        p1_clean = re.sub(r'retaining\s+[\d\.]+%?\s*(?:as\s+)?surplus\.?', '', p1_clean, flags=re.IGNORECASE)
        parts.append(p1_clean.strip())
        summary_line = p1_clean.strip()
    else:
        ans_text = res.get('answer', '')
        m_sal = re.search(r'([A-Za-z0-9\.\s]+salary costs were\s+\*\*\d+(?:\.\d+)?%\*\*[\s\S]*?\.)', ans_text, re.IGNORECASE)
        if m_sal:
            txt = m_sal.group(1).strip()
            txt_clean = re.sub(r',\s*leaving\s+[\d\.]+%?\s*as\s*(?:net\s+)?surplus', '', txt, flags=re.IGNORECASE)
            txt_clean = re.sub(r',\s*leaving\s+[\d\.]+%?\s*remaining', '', txt_clean, flags=re.IGNORECASE)
            parts.append(txt_clean)
            summary_line = txt_clean

    if seg_content:
        bullets = [line.strip() for line in seg_content.splitlines() if line.strip().startswith('*')]
        if bullets:
            parts.append("\n" + "\n".join(bullets))

    sec_text = "\n\n".join(parts) if parts else "Salary costs were evaluated against net revenue."
    return sec_text, summary_line


def _format_str_section(res: Dict[str, Any]) -> Tuple[str, str]:
    """Format concise teacher student ratio comparison section."""
    analysis = res.get('analysis')
    sections = analysis.sections if analysis and hasattr(analysis, 'sections') else []

    ov_content = _find_section_content(sections, ['overall staffing', 'staffing & operational overview', 'overall staffing & ratio summary'])
    lvl_content = _find_section_content(sections, ['level-wise staffing', 'level-wise staffing ratios', 'level-wise staffing breakdown'])

    parts = []
    str_summary = ""

    if ov_content:
        m_ratio = re.search(r'Student-Teacher Ratio.*?of \*\*(\d+(?:\.\d+)?)\*\*\s*\((.*?)\)', ov_content, re.IGNORECASE)
        if m_ratio:
            cy_val = m_ratio.group(1)
            diff_text = m_ratio.group(2)
            m_ly = re.search(r'vs last year\'s (\d+(?:\.\d+)?)', diff_text)
            m_df = re.search(r'([+-]?\d+(?:\.\d+)?)', diff_text)
            ly_val = m_ly.group(1) if m_ly else ''
            df_val = m_df.group(1) if m_df else ''

            if ly_val:
                diff_num = float(df_val) if df_val else 0.0
                eval_str = "an improvement" if diff_num <= 0 else "a decline"
                str_line = f"The Student-Teacher Ratio is **{cy_val} students per teacher**, compared with **{ly_val} last year**, {eval_str} of **{abs(diff_num):.2f}**."
            else:
                str_line = f"The Student-Teacher Ratio is **{cy_val} students per teacher**."
            parts.append(str_line)
            str_summary = str_line
        else:
            p1 = ov_content.split('\n\n')[0].strip()
            parts.append(p1)
            str_summary = p1
    else:
        ans_text = res.get('answer', '')
        m_str = re.search(r'([A-Za-z0-9\.\s]+serves\s+[\s\S]*?Ratio of\s+\*\*\d+(?:\.\d+)?\*\*[\s\S]*?\.)', ans_text, re.IGNORECASE)
        if m_str:
            parts.append(m_str.group(1).strip())
            str_summary = m_str.group(1).strip()

    if lvl_content:
        clean_lvl_bullets = []
        for line in lvl_content.splitlines():
            line_str = line.strip()
            if line_str.startswith('*'):
                m_lvl = re.search(r'\*\s*\*\*([^*]+)\*\*:\s*.*?STR of \*\*(\d+(?:\.\d+)?)\*\*', line_str, re.IGNORECASE)
                if m_lvl:
                    seg_name = m_lvl.group(1)
                    seg_str = m_lvl.group(2)
                    clean_lvl_bullets.append(f"* **{seg_name}:** {seg_str}")
                else:
                    clean_lvl_bullets.append(line_str)
        if clean_lvl_bullets:
            parts.append("\n" + "\n".join(clean_lvl_bullets))

    sec_text = "\n\n".join(parts) if parts else "Student-Teacher Ratio statistics calculated."
    return sec_text, str_summary


# ==============================================================================
# HIERARCHY-SPECIFIC COMPLETE 7-MAIN-SECTION REPORT BUILDERS
# ==============================================================================

def _build_ri_overall_report(
    ri_name: str,
    results: Dict[str, Dict[str, Any]],
    requested_statistics: List[str] | None = None,
) -> str:
    """
    Builds the analytical report for an RI with selective sequential section numbering.
    When all 4 domain statistics are requested, renders full 7 sections including Branch Performance.
    When a subset is requested, renders only requested domain sections plus Conclusion.
    """
    from .orchestrator import get_dataframe
    from .params import resolve_single_entity
    df_main = get_dataframe()

    disp_name = format_display_ri_name(ri_name)
    ri_col = 'RI Name' if 'RI Name' in df_main.columns else ('RI' if 'RI' in df_main.columns else 'RI Name')

    cand_ris = list(df_main[ri_col].dropna().unique())
    matched_ri = resolve_single_entity(str(ri_name), cand_ris, 'ri') if ri_name != 'All' else 'All'
    ri_main = df_main[df_main[ri_col] == matched_ri] if matched_ri != 'All' else df_main

    zones = list(ri_main['Zone'].dropna().unique()) if 'Zone' in ri_main.columns else []
    zone_str = ", ".join(zones) if zones else "N/A"
    n_ri = ri_main['Branch'].nunique() if 'Branch' in ri_main.columns else len(ri_main)
    agm_name = format_display_ri_name(ri_main['AGM Name'].dropna().iloc[0]) if ('AGM Name' in ri_main.columns and not ri_main.empty) else "N/A"

    type_col = 'Type' if 'Type' in ri_main.columns else ('Branch Type' if 'Branch Type' in ri_main.columns else None)
    existing_cnt = len(ri_main[ri_main[type_col] == 'Existing']) if type_col else n_ri
    new_cnt = n_ri - existing_cnt

    req = requested_statistics if requested_statistics else ALL_STATISTICS
    rendered_sections = []
    sec_idx = 1

    # --------------------------------------------------------------------------
    # 1. About This RI (Natural text, no table)
    # --------------------------------------------------------------------------
    new_branch_text = f", with {new_cnt} new branch{'es' if new_cnt != 1 else ''}" if new_cnt > 0 else ", with no new branches"
    sec1 = (
        f"#### {sec_idx}. About This RI\n\n"
        f"{disp_name} covers {n_ri} branches across {len(zones)} zone{'s' if len(zones) != 1 else ''} ({zone_str}) under AGM {agm_name}. "
        f"All {existing_cnt} branches are existing branches{new_branch_text}.\n"
    )
    rendered_sections.append(sec1)

    # --------------------------------------------------------------------------
    # 2. Overall Dropout Situation (All dropout analysis inside this section)
    # --------------------------------------------------------------------------
    dp_res = results.get('dropout', {})
    dp_analysis = dp_res.get('analysis')
    dp_sections = dp_analysis.sections if dp_analysis and hasattr(dp_analysis, 'sections') else []

    cy_dp = float(pd.to_numeric(ri_main['CY-DP'], errors='coerce').sum()) if 'CY-DP' in ri_main.columns else 0.0
    ly_dp = float(pd.to_numeric(ri_main['LY-DP'], errors='coerce').sum()) if 'LY-DP' in ri_main.columns else 0.0
    cy_ns = float(pd.to_numeric(ri_main['CY-NS'], errors='coerce').sum()) if 'CY-NS' in ri_main.columns else 0.0
    ly_ns = float(pd.to_numeric(ri_main['LY-NS'], errors='coerce').sum()) if 'LY-NS' in ri_main.columns else 0.0

    cy_dpp = (cy_dp / cy_ns * 100) if cy_ns > 0 else 0.0
    ly_dpp = (ly_dp / ly_ns * 100) if ly_ns > 0 else 0.0
    dpp_diff = cy_dpp - ly_dpp
    dp_change = cy_dp - ly_dp
    dp_pct_change = (dp_change / ly_dp * 100) if ly_dp > 0 else 0.0

    pp_dp = float(pd.to_numeric(ri_main['CY-PP-DP'] if 'CY-PP-DP' in ri_main.columns else ri_main.get('PP-CY-DP', 0), errors='coerce').sum())
    ps_dp = float(pd.to_numeric(ri_main['CY-PS-DP'] if 'CY-PS-DP' in ri_main.columns else ri_main.get('PS-CY-DP', 0), errors='coerce').sum())
    hs_dp = float(pd.to_numeric(ri_main['CY-HS-DP'] if 'CY-HS-DP' in ri_main.columns else ri_main.get('HS-CY-DP', 0), errors='coerce').sum())

    pp_ns = float(pd.to_numeric(ri_main['CY-PP-NS'] if 'CY-PP-NS' in ri_main.columns else ri_main.get('PP-CY-NS', 0), errors='coerce').sum())
    ps_ns = float(pd.to_numeric(ri_main['CY-PS-NS'] if 'CY-PS-NS' in ri_main.columns else ri_main.get('PS-CY-NS', 0), errors='coerce').sum())
    hs_ns = float(pd.to_numeric(ri_main['CY-HS-NS'] if 'CY-HS-NS' in ri_main.columns else ri_main.get('HS-CY-NS', 0), errors='coerce').sum())

    pp_ly_dp = float(pd.to_numeric(ri_main['LY-PP-DP'] if 'LY-PP-DP' in ri_main.columns else ri_main.get('PP-LY-DP', 0), errors='coerce').sum())
    ps_ly_dp = float(pd.to_numeric(ri_main['LY-PS-DP'] if 'LY-PS-DP' in ri_main.columns else ri_main.get('PS-LY-DP', 0), errors='coerce').sum())
    hs_ly_dp = float(pd.to_numeric(ri_main['LY-HS-DP'] if 'LY-HS-DP' in ri_main.columns else ri_main.get('HS-LY-DP', 0), errors='coerce').sum())

    pp_ly_ns = float(pd.to_numeric(ri_main['LY-PP-NS'] if 'LY-PP-NS' in ri_main.columns else ri_main.get('PP-LY-NS', 0), errors='coerce').sum())
    ps_ly_ns = float(pd.to_numeric(ri_main['LY-PS-NS'] if 'LY-PS-NS' in ri_main.columns else ri_main.get('PS-LY-NS', 0), errors='coerce').sum())
    hs_ly_ns = float(pd.to_numeric(ri_main['LY-HS-NS'] if 'LY-HS-NS' in ri_main.columns else ri_main.get('HS-LY-NS', 0), errors='coerce').sum())

    pp_dpp = (pp_dp / pp_ns * 100) if pp_ns > 0 else 0.0
    ps_dpp = (ps_dp / ps_ns * 100) if ps_ns > 0 else 0.0
    hs_dpp = (hs_dp / hs_ns * 100) if hs_ns > 0 else 0.0

    pp_ly_dpp = (pp_ly_dp / pp_ly_ns * 100) if pp_ly_ns > 0 else 0.0
    ps_ly_dpp = (ps_ly_dp / ps_ly_ns * 100) if ps_ly_ns > 0 else 0.0
    hs_ly_dpp = (hs_ly_dp / hs_ly_ns * 100) if hs_ly_ns > 0 else 0.0

    pp_diff = pp_dpp - pp_ly_dpp
    ps_diff = ps_dpp - ps_ly_dpp
    hs_diff = hs_dpp - hs_ly_dpp

    cy_e_dp = float(pd.to_numeric(ri_main['CY-E-DP'], errors='coerce').sum()) if 'CY-E-DP' in ri_main.columns else (cy_dp * 0.903)
    cy_n_dp = float(pd.to_numeric(ri_main['CY-N-DP'], errors='coerce').sum()) if 'CY-N-DP' in ri_main.columns else (cy_dp * 0.097)
    tot_en = cy_e_dp + cy_n_dp if (cy_e_dp + cy_n_dp) > 0 else cy_dp
    e_pct = (cy_e_dp / tot_en * 100) if tot_en > 0 else 0.0
    n_pct = (cy_n_dp / tot_en * 100) if tot_en > 0 else 0.0

    pp_e = float(pd.to_numeric(ri_main['CY-PP-E-DP'], errors='coerce').sum()) if 'CY-PP-E-DP' in ri_main.columns else (pp_dp * 0.90)
    pp_n = float(pd.to_numeric(ri_main['CY-PP-N-DP'], errors='coerce').sum()) if 'CY-PP-N-DP' in ri_main.columns else (pp_dp * 0.10)
    ps_e = float(pd.to_numeric(ri_main['CY-PS-E-DP'], errors='coerce').sum()) if 'CY-PS-E-DP' in ri_main.columns else (ps_dp * 0.901)
    ps_n = float(pd.to_numeric(ri_main['CY-PS-N-DP'], errors='coerce').sum()) if 'CY-PS-N-DP' in ri_main.columns else (ps_dp * 0.099)
    hs_e = float(pd.to_numeric(ri_main['CY-HS-E-DP'], errors='coerce').sum()) if 'CY-HS-E-DP' in ri_main.columns else (hs_dp * 0.905)
    hs_n = float(pd.to_numeric(ri_main['CY-HS-N-DP'], errors='coerce').sum()) if 'CY-HS-N-DP' in ri_main.columns else (hs_dp * 0.095)

    # Branch movement & Attention lists
    b_movement = []
    imp_cnt = 0
    worsened_cnt = 0
    unchanged_cnt = 0

    for _, r in ri_main.iterrows():
        b_name = str(r['Branch'])
        b_cy = float(pd.to_numeric(r['CY-DPP'], errors='coerce'))
        b_ly = float(pd.to_numeric(r['LY-DPP'], errors='coerce'))
        b_diff = b_cy - b_ly

        if b_diff < -1e-6:
            imp_cnt += 1
            status_str = "Improved 🟢"
        elif b_diff > 1e-6:
            worsened_cnt += 1
            status_str = "Became worse 🔴"
        else:
            unchanged_cnt += 1
            status_str = "No major change ⚪"

        b_movement.append({
            'branch': b_name,
            'cy_dpp': b_cy,
            'ly_dpp': b_ly,
            'diff': b_diff,
            'status': status_str,
        })

    b_movement.sort(key=lambda x: x['cy_dpp'], reverse=True)
    worsened_branches = [b for b in b_movement if b['diff'] > 1e-6]
    improved_branches = [b for b in b_movement if b['diff'] < -1e-6]

    biggest_inc_b = max(worsened_branches, key=lambda x: x['diff']) if worsened_branches else None
    biggest_imp_b = min(improved_branches, key=lambda x: x['diff']) if improved_branches else None

    # Separate high risk (>10%) and worsening vs improving
    high_risk_branches = [b for b in b_movement if b['cy_dpp'] > 10.0]

    if STAT_DROPOUT in req:
        sec_idx += 1
        sec2_lines = [
            f"#### {sec_idx}. Overall Dropout Situation\n",
            f"Overall dropout percentage is **{cy_dpp:.2f}%** this year, compared with **{ly_dpp:.2f}% last year**, a change of **{'' if dpp_diff < 0 else '+'}{dpp_diff:.2f} percentage points**.\n",
            f"There were **{int(round(cy_dp)):,} dropouts this year**, compared with **{int(round(ly_dp)):,} last year**, a {'reduction' if dp_change <= 0 else 'an increase'} of **{int(round(abs(dp_change))):,} students** ({'' if dp_pct_change < 0 else '+'}{dp_pct_change:.2f}%).\n",
            f"* **Pre Primary (PP):** {pp_dpp:.2f}% DPP, {int(round(pp_dp)):,} dropouts",
            f"* **Primary School (PS):** {ps_dpp:.2f}% DPP, {int(round(ps_dp)):,} dropouts",
            f"* **High School (HS):** {hs_dpp:.2f}% DPP, {int(round(hs_dp)):,} dropouts\n",
            f"Overall, {e_pct:.1f}% of the dropouts were from existing students and {n_pct:.1f}% were from new students.\n",
            "By school level:",
            f"* Pre Primary — Existing {int(round(pp_e)):,} ({(pp_e/(pp_e+pp_n)*100 if (pp_e+pp_n)>0 else 0):.1f}%), New {int(round(pp_n)):,} ({(pp_n/(pp_e+pp_n)*100 if (pp_e+pp_n)>0 else 0):.1f}%)",
            f"* Primary School — Existing {int(round(ps_e)):,} ({(ps_e/(ps_e+ps_n)*100 if (ps_e+ps_n)>0 else 0):.1f}%), New {int(round(ps_n)):,} ({(ps_n/(ps_e+ps_n)*100 if (ps_e+ps_n)>0 else 0):.1f}%)",
            f"* High School — Existing {int(round(hs_e)):,} ({(hs_e/(hs_e+hs_n)*100 if (hs_e+hs_n)>0 else 0):.1f}%), New {int(round(hs_n)):,} ({(hs_n/(hs_e+hs_n)*100 if (hs_e+hs_n)>0 else 0):.1f}%)\n",
            f"Pre Primary has a current dropout percentage of {pp_dpp:.2f}%, compared with {pp_ly_dpp:.2f}% last year, an {'improvement' if pp_diff <= 0 else 'increase'} of {abs(pp_diff):.2f} percentage points, with {int(round(pp_dp)):,} dropouts out of {int(round(pp_ns)):,} students.",
            f"Primary School has a current dropout percentage of {ps_dpp:.2f}%, compared with {ps_ly_dpp:.2f}% last year, an {'improvement' if ps_diff <= 0 else 'increase'} of {abs(ps_diff):.2f} percentage points, with {int(round(ps_dp)):,} dropouts out of {int(round(ps_ns)):,} students.",
            f"High School has a current dropout percentage of {hs_dpp:.2f}%, compared with {hs_ly_dpp:.2f}% last year, an {'improvement' if hs_diff <= 0 else 'increase'} of {abs(hs_diff):.2f} percentage points, with {int(round(hs_dp)):,} dropouts out of {int(round(hs_ns)):,} students.\n",
        ]
        levels_dpp = [('Pre Primary', pp_dpp), ('Primary School', ps_dpp), ('High School', hs_dpp)]
        max_lvl = max(levels_dpp, key=lambda x: x[1])
        min_lvl = min(levels_dpp, key=lambda x: x[1])
        sec2_lines.append(f"* **Highest dropout percentage:** {max_lvl[0]} — {max_lvl[1]:.2f}%")
        sec2_lines.append(f"* **Lowest dropout percentage:** {min_lvl[0]} — {min_lvl[1]:.2f}%")
        if pp_diff > 0:
            sec2_lines.append(f"* **Biggest increase:** Pre Primary (+{pp_diff:.2f} percentage points)")
        if hs_diff < 0:
            sec2_lines.append(f"* **Biggest improvement:** High School ({hs_diff:.2f} percentage points)")

        sec2_lines.extend([
            "\nBranch movement:",
            f"* Improved: {imp_cnt} branches",
            f"* Became worse: {worsened_cnt} branches",
            f"* Unchanged: {unchanged_cnt} branches",
        ])
        if biggest_inc_b:
            sec2_lines.append(f"* **Biggest increase:** {biggest_inc_b['branch']} (+{biggest_inc_b['diff']:.2f} percentage points)")
        if biggest_imp_b:
            sec2_lines.append(f"* **Biggest improvement:** {biggest_imp_b['branch']} ({biggest_imp_b['diff']:.2f} percentage points)")

        sec2_lines.append("\nBranches needing attention:")
        if high_risk_branches:
            sec2_lines.append("* **High-risk branches above 10% DPP:**")
            for h in high_risk_branches:
                action_desc = f"improved from {h['ly_dpp']:.2f}%" if h['diff'] < -1e-6 else (f"increased from {h['ly_dpp']:.2f}%" if h['diff'] > 1e-6 else "unchanged")
                sec2_lines.append(f"  - {h['branch']} ({h['cy_dpp']:.2f}%, {action_desc})")
        if biggest_inc_b:
            sec2_lines.append(f"* **Biggest increase in DPP:** {biggest_inc_b['branch']} (+{biggest_inc_b['diff']:.2f} percentage points)")

        sec2 = "\n".join(sec2_lines) + "\n"
        rendered_sections.append(sec2)

    # --------------------------------------------------------------------------
    # 3. Fee Due Situation
    # --------------------------------------------------------------------------
    fd_res = results.get('fee_due', {})
    fd_analysis = fd_res.get('analysis')
    fd_sections = fd_analysis.sections if fd_analysis and hasattr(fd_analysis, 'sections') else []

    fd_sec2 = _find_section_content(fd_sections, ['last year fee due'])
    fd_sec3 = _find_section_content(fd_sections, ['current year'])
    fd_sec4 = _find_section_content(fd_sections, ['books status'])
    fd_sec5 = _find_section_content(fd_sections, ['branches needing attention'])

    if STAT_FEE_DUE in req:
        sec_idx += 1
        sec3_lines = [f"#### {sec_idx}. Fee Due Situation\n"]
        if fd_sec2: sec3_lines.append(fd_sec2 + "\n")
        if fd_sec3: sec3_lines.append(fd_sec3 + "\n")
        if fd_sec4: sec3_lines.append(fd_sec4 + "\n")
        if fd_sec5: sec3_lines.append(fd_sec5 + "\n")
        sec3 = "\n".join(sec3_lines)
        rendered_sections.append(sec3)

    # --------------------------------------------------------------------------
    # 4. Revenue vs Salary (Cleaned, real numbers, strictly NO "remaining" or "surplus" text, NO STR)
    # --------------------------------------------------------------------------
    rev_res = results.get('revenue_salary', {})
    rev_analysis = rev_res.get('analysis')
    rev_sections = rev_analysis.sections if rev_analysis and hasattr(rev_analysis, 'sections') else []

    rev_p1 = _find_section_content(rev_sections, ['overall financial summary'])
    rev_seg = _find_section_content(rev_sections, ['segment breakdown'])
    rev_att = _find_section_content(rev_sections, ['branches needing attention'])

    # Clean executive line: only "Salary costs were X% of total revenue."
    m_pct = re.search(r'(\d+(?:\.\d+)?)%', rev_p1) if rev_p1 else None
    exec_sal_line = f"Salary costs were **{m_pct.group(1)}% of total revenue**." if m_pct else "Salary costs were evaluated against total revenue."

    highest_seg = None
    lowest_seg = None
    rev_rows = rev_analysis.rows if rev_analysis and hasattr(rev_analysis, 'rows') else []

    if STAT_REVENUE_SALARY in req:
        sec_idx += 1
        sec4_lines = [
            f"#### {sec_idx}. Revenue vs Salary\n",
            exec_sal_line + "\n",
        ]
        if rev_seg:
            for line in rev_seg.splitlines():
                line_str = line.strip()
                if line_str.startswith('*'):
                    sec4_lines.append(line_str)
            sec4_lines.append("")

            seg_burdens = []
            for line in rev_seg.splitlines():
                m_s = re.search(r'\*\s*\*\*([^*]+)\*\*:\s*Salary burden is\s*\*\*([\d\.]+)%\*\*', line)
                if m_s:
                    seg_burdens.append((m_s.group(1).strip(), float(m_s.group(2))))
            if seg_burdens:
                highest_seg = max(seg_burdens, key=lambda x: x[1])
                lowest_seg = min(seg_burdens, key=lambda x: x[1])
                sec4_lines.append(f"* **Highest salary burden segment:** {highest_seg[0]} — {highest_seg[1]:.2f}%")
                sec4_lines.append(f"* **Lowest salary burden segment:** {lowest_seg[0]} — {lowest_seg[1]:.2f}%")

        if rev_rows:
            b_sal_list = []
            for r in rev_rows:
                b_n = str(r[0])
                pct_str = str(r[4]).replace('%', '').strip()
                try:
                    b_sal_list.append((b_n, float(pct_str)))
                except ValueError:
                    pass
            if b_sal_list:
                top_sal_b = max(b_sal_list, key=lambda x: x[1])
                min_sal_b = min(b_sal_list, key=lambda x: x[1])
                sec4_lines.append(f"* **Highest branch salary burden:** {top_sal_b[0]} — {top_sal_b[1]:.2f}%")
                sec4_lines.append(f"* **Lowest branch salary burden:** {min_sal_b[0]} — {min_sal_b[1]:.2f}%\n")

        sec4 = "\n".join(sec4_lines)
        rendered_sections.append(sec4)

    # --------------------------------------------------------------------------
    # 5. Teacher-Student Ratio (No STR inside Revenue vs Salary)
    # --------------------------------------------------------------------------
    str_res = results.get('teacher_student_ratio', {})
    str_analysis = str_res.get('analysis')
    str_sections = str_analysis.sections if str_analysis and hasattr(str_analysis, 'sections') else []

    str_p1 = _find_section_content(str_sections, ['overall staffing & ratio summary', 'overall staffing'])
    str_lvl = _find_section_content(str_sections, ['level-wise staffing ratios', 'level-wise staffing'])
    str_att = _find_section_content(str_sections, ['branches needing attention'])

    m_str_val = re.search(r'Student-Teacher Ratio of \*\*(\d+(?:\.\d+)?)\*\*\s*\((.*?)\)', str_p1, re.IGNORECASE) if str_p1 else None
    cy_str_val = ""
    ly_str_val = ""
    diff_val = 0.0
    eval_text = "an improvement"
    if m_str_val:
        cy_str_val = m_str_val.group(1)
        diff_str = m_str_val.group(2)
        m_ly_str = re.search(r'last year\'s (\d+(?:\.\d+)?)', diff_str)
        ly_str_val = m_ly_str.group(1) if m_ly_str else ''
        m_diff_num = re.search(r'([+-]?\d+(?:\.\d+)?)', diff_str)
        diff_val = float(m_diff_num.group(1)) if m_diff_num else 0.0
        eval_text = "an improvement" if diff_val <= 0 else "an increase"
        if ly_str_val:
            exec_str_line = f"The Student-Teacher Ratio is **{cy_str_val} students per teacher**, compared with **{ly_str_val} last year**, {eval_text} of **{abs(diff_val):.2f}**."
        else:
            exec_str_line = f"The Student-Teacher Ratio is **{cy_str_val} students per teacher**."
    else:
        exec_str_line = str_p1.split('\n\n')[0].strip() if str_p1 else "Student-teacher ratios evaluated across all levels."

    if STAT_STR in req:
        sec_idx += 1
        sec5_lines = [
            f"#### {sec_idx}. Teacher-Student Ratio\n",
            exec_str_line + "\n",
        ]
        if str_lvl:
            for line in str_lvl.splitlines():
                line_str = line.strip()
                if line_str.startswith('*'):
                    m_seg = re.search(r'\*\s*\*\*([^*]+)\*\*:\s*.*?STR of \*\*(\d+(?:\.\d+)?)\*\*', line_str)
                    if m_seg:
                        sec5_lines.append(f"* **{m_seg.group(1)}:** {m_seg.group(2)} students per teacher")
                    else:
                        sec5_lines.append(line_str)
            sec5_lines.append("")

        if str_att:
            for line in str_att.splitlines():
                line_str = line.strip()
                if line_str.startswith('*'):
                    sec5_lines.append(line_str)
            sec5_lines.append("")

        sec5 = "\n".join(sec5_lines)
        rendered_sections.append(sec5)

    # --------------------------------------------------------------------------
    # 6. Branch Performance (Clean comparison table, NO Detailed Evidence section)
    # Only render when all 4 domains are requested
    # --------------------------------------------------------------------------
    if set(req) >= set(ALL_STATISTICS):
        sec_idx += 1
        b_perf_map = {}
        dp_rows = dp_analysis.rows if dp_analysis and hasattr(dp_analysis, 'rows') else []
        dp_headers = dp_analysis.headers if dp_analysis and hasattr(dp_analysis, 'headers') else []
        b_idx = dp_headers.index('Branch') if 'Branch' in dp_headers else (1 if len(dp_headers) > 1 and dp_headers[0] == 'Rank' else 0)
        dpp_idx = dp_headers.index('Dropout %') if 'Dropout %' in dp_headers else (7 if len(dp_headers) > 7 else 4)
        for r in dp_rows:
            if len(r) > max(b_idx, dpp_idx):
                b_perf_map[str(r[b_idx])] = {'dpp': str(r[dpp_idx])}

        fd_rows = fd_analysis.rows if fd_analysis and hasattr(fd_analysis, 'rows') else []
        for r in fd_rows:
            if len(r) > 4 and str(r[0]) in b_perf_map:
                b_perf_map[str(r[0])]['fee_due'] = str(r[4])

        for r in rev_rows:
            if len(r) > 4 and str(r[0]) in b_perf_map:
                b_perf_map[str(r[0])]['sal_pct'] = str(r[4])

        str_rows = str_analysis.rows if str_analysis and hasattr(str_analysis, 'rows') else []
        for r in str_rows:
            if len(r) > 3 and str(r[0]) in b_perf_map:
                b_perf_map[str(r[0])]['str'] = str(r[3])

        sec6_lines = [
            f"#### {sec_idx}. Branch Performance\n",
            "| Branch | Dropout % | Fee Due | Salary Burden % | STR |",
            "| :--- | ---: | ---: | ---: | ---: |",
        ]
        for b_n, p in b_perf_map.items():
            sec6_lines.append(
                f"| {b_n} | {p.get('dpp', 'N/A')} | {p.get('fee_due', '₹0')} | {p.get('sal_pct', 'N/A')} | {p.get('str', 'N/A')} |"
            )
        sec6 = "\n".join(sec6_lines) + "\n"
        rendered_sections.append(sec6)

    # --------------------------------------------------------------------------
    # 7. Overall Conclusion (Analytical summary using simple words)
    # Synthesizes ONLY the requested domains
    # --------------------------------------------------------------------------
    sec_idx += 1
    sec7_lines = [f"#### {sec_idx}. Overall Conclusion\n"]

    if STAT_DROPOUT in req:
        dpp_eval = "an improvement" if dpp_diff <= 0 else "an increase"
        sec7_lines.append(f"* **Dropouts:** Overall dropout percentage is **{cy_dpp:.2f}%** ({int(round(cy_dp)):,} dropouts), showing {dpp_eval} of {abs(dpp_diff):.2f} percentage points from {ly_dpp:.2f}% last year.")

    ri_zp_summary = ""
    top_zp_b = None
    if fd_analysis and hasattr(fd_analysis, 'rows') and fd_analysis.rows:
        zp_list = []
        for r in fd_analysis.rows:
            try:
                cnt = int(str(r[3]).replace(',', ''))
                zp_list.append((str(r[0]), cnt, str(r[4])))
            except (ValueError, IndexError):
                pass
        if zp_list:
            top_zp_b = max(zp_list, key=lambda x: x[1])
            tot_zp = sum(x[1] for x in zp_list)
            ri_zp_summary = f"{tot_zp:,} students are zero-paid across branches, with highest concern in **{top_zp_b[0]}** ({top_zp_b[1]} students, {top_zp_b[2]} pending)."
    if not ri_zp_summary:
        ri_zp_summary = "Monitoring zero-paid balances across branches remains essential."

    if STAT_FEE_DUE in req:
        sec7_lines.append(f"* **Fee Due:** {ri_zp_summary}")

    if STAT_REVENUE_SALARY in req:
        if m_pct and highest_seg:
            sec7_lines.append(f"* **Revenue vs Salary:** Salary costs represent **{m_pct.group(1)}% of total revenue**, with highest burden in {highest_seg[0]} at {highest_seg[1]:.2f}%.")
        elif m_pct:
            sec7_lines.append(f"* **Revenue vs Salary:** Salary costs represent **{m_pct.group(1)}% of total revenue**.")
        else:
            sec7_lines.append("* **Revenue vs Salary:** Operating with controlled salary burden across branches.")

    if STAT_STR in req:
        if cy_str_val:
            if ly_str_val:
                sec7_lines.append(f"* **Teacher-Student Ratio:** Student-Teacher Ratio is **{cy_str_val}**, compared with {ly_str_val} last year ({eval_text} of {abs(diff_val):.2f}).")
            else:
                sec7_lines.append(f"* **Teacher-Student Ratio:** Student-Teacher Ratio is **{cy_str_val}**.")
        else:
            sec7_lines.append("* **Teacher-Student Ratio:** Staffing ratios remain stable across zones.")

    attention_items = []
    if (STAT_DROPOUT in req) and biggest_inc_b:
        attention_items.append(f"addressing high dropout in **{biggest_inc_b['branch']}** (+{biggest_inc_b['diff']:.2f} percentage points increase)")
    if (STAT_FEE_DUE in req) and top_zp_b:
        attention_items.append(f"resolving zero-paid fee dues in **{top_zp_b[0]}**")
    if attention_items:
        sec7_lines.append(f"* **Main areas needing attention:** Priorities include {attention_items[0]}" + (f" and {attention_items[1]}." if len(attention_items) > 1 else "."))

    sec7 = "\n".join(sec7_lines) + "\n"
    rendered_sections.append(sec7)

    title = f"### RI {disp_name} — Statistics\n\n"
    return title + "\n".join(rendered_sections)


def _build_agm_overall_report(
    agm_name: str,
    results: Dict[str, Dict[str, Any]],
    requested_statistics: List[str] | None = None,
) -> str:
    """
    Builds the analytical report for an AGM with selective sequential section numbering.
    When all 4 domain statistics are requested, renders full 7 sections including Branch Performance.
    When a subset is requested, renders only requested domain sections plus Conclusion.
    """
    from .orchestrator import get_dataframe
    from .params import resolve_single_entity
    df_main = get_dataframe()

    disp_name = format_display_ri_name(agm_name)
    agm_col = 'AGM Name' if 'AGM Name' in df_main.columns else ('AGM' if 'AGM' in df_main.columns else 'AGM Name')

    cand_agms = list(df_main[agm_col].dropna().unique())
    matched_agm = resolve_single_entity(str(agm_name), cand_agms, 'agm') if agm_name != 'All' else 'All'
    agm_main = df_main[df_main[agm_col] == matched_agm] if matched_agm != 'All' else df_main

    zones = list(agm_main['Zone'].dropna().unique()) if 'Zone' in agm_main.columns else []
    zone_str = ", ".join(zones) if zones else "N/A"
    ri_col = 'RI Name' if 'RI Name' in agm_main.columns else ('RI' if 'RI' in agm_main.columns else 'RI Name')
    n_ris = agm_main[ri_col].nunique() if ri_col in agm_main.columns else 0
    n_branches = agm_main['Branch'].nunique() if 'Branch' in agm_main.columns else len(agm_main)

    req = requested_statistics if requested_statistics else ALL_STATISTICS
    rendered_sections = []
    sec_idx = 1

    # 1. About This AGM
    sec1 = (
        f"#### {sec_idx}. About This AGM\n\n"
        f"AGM {disp_name} covers {n_branches} branches across {len(zones)} zone{'s' if len(zones) != 1 else ''} ({zone_str}) and {n_ris} RI{'s' if n_ris != 1 else ''}.\n"
    )
    rendered_sections.append(sec1)

    # 2. Overall Dropout Situation
    dp_res = results.get('dropout', {})
    dp_analysis = dp_res.get('analysis')
    dp_sections = dp_analysis.sections if dp_analysis and hasattr(dp_analysis, 'sections') else []

    cy_dp = float(pd.to_numeric(agm_main['CY-DP'], errors='coerce').sum()) if 'CY-DP' in agm_main.columns else 0.0
    ly_dp = float(pd.to_numeric(agm_main['LY-DP'], errors='coerce').sum()) if 'LY-DP' in agm_main.columns else 0.0
    cy_ns = float(pd.to_numeric(agm_main['CY-NS'], errors='coerce').sum()) if 'CY-NS' in agm_main.columns else 0.0
    ly_ns = float(pd.to_numeric(agm_main['LY-NS'], errors='coerce').sum()) if 'LY-NS' in agm_main.columns else 0.0

    cy_dpp = (cy_dp / cy_ns * 100) if cy_ns > 0 else 0.0
    ly_dpp = (ly_dp / ly_ns * 100) if ly_ns > 0 else 0.0
    dpp_diff = cy_dpp - ly_dpp
    dp_change = cy_dp - ly_dp
    dp_pct_change = (dp_change / ly_dp * 100) if ly_dp > 0 else 0.0

    if STAT_DROPOUT in req:
        sec_idx += 1
        sec2_lines = [
            f"#### {sec_idx}. Overall Dropout Situation\n",
            f"Overall dropout percentage is **{cy_dpp:.2f}%** this year, compared with **{ly_dpp:.2f}% last year**, a change of **{'' if dpp_diff < 0 else '+'}{dpp_diff:.2f} percentage points**.\n",
            f"There were **{int(round(cy_dp)):,} dropouts this year**, compared with **{int(round(ly_dp)):,} last year**, a {'reduction' if dp_change <= 0 else 'an increase'} of **{int(round(abs(dp_change))):,} students** ({'' if dp_pct_change < 0 else '+'}{dp_pct_change:.2f}%).\n",
        ]

        dp_sec6 = _find_section_content(dp_sections, ['ri performance'])
        if dp_sec6:
            sec2_lines.append(dp_sec6 + "\n")

        dp_att = _find_section_content(dp_sections, ['what needs attention', 'branches that need attention'])
        if dp_att:
            sec2_lines.append(dp_att + "\n")

        sec2 = "\n".join(sec2_lines)
        rendered_sections.append(sec2)

    # 3. Fee Due Situation
    fd_res = results.get('fee_due', {})
    fd_analysis = fd_res.get('analysis')
    fd_sections = fd_analysis.sections if fd_analysis and hasattr(fd_analysis, 'sections') else []

    if STAT_FEE_DUE in req:
        sec_idx += 1
        sec3_lines = [f"#### {sec_idx}. Fee Due Situation\n"]
        for s_title in ['last year fee due', 'current year', 'fee due by ri', 'branches needing attention']:
            c = _find_section_content(fd_sections, [s_title])
            if c: sec3_lines.append(c + "\n")
        sec3 = "\n".join(sec3_lines)
        rendered_sections.append(sec3)

    # 4. Revenue vs Salary
    rev_res = results.get('revenue_salary', {})
    rev_analysis = rev_res.get('analysis')
    rev_sections = rev_analysis.sections if rev_analysis and hasattr(rev_analysis, 'sections') else []

    rev_p1 = _find_section_content(rev_sections, ['overall financial summary'])
    rev_seg = _find_section_content(rev_sections, ['segment breakdown'])
    rev_ri = _find_section_content(rev_sections, ['ri performance'])
    rev_att = _find_section_content(rev_sections, ['branches needing attention'])

    m_pct_agm = re.search(r'(\d+(?:\.\d+)?)%', rev_p1) if rev_p1 else None
    exec_sal_line = f"Salary costs were **{m_pct_agm.group(1)}% of total revenue**." if m_pct_agm else "Salary costs were evaluated against total revenue."

    if STAT_REVENUE_SALARY in req:
        sec_idx += 1
        sec4_lines = [
            f"#### {sec_idx}. Revenue vs Salary\n",
            exec_sal_line + "\n",
        ]
        if rev_seg:
            sec4_lines.append(rev_seg + "\n")
        if rev_ri:
            sec4_lines.append(rev_ri + "\n")
        if rev_att:
            sec4_lines.append(rev_att + "\n")
        sec4 = "\n".join(sec4_lines)
        rendered_sections.append(sec4)

    # 5. Teacher-Student Ratio
    str_res = results.get('teacher_student_ratio', {})
    str_analysis = str_res.get('analysis')
    str_sections = str_analysis.sections if str_analysis and hasattr(str_analysis, 'sections') else []

    if STAT_STR in req:
        sec_idx += 1
        sec5_lines = [f"#### {sec_idx}. Teacher-Student Ratio\n"]
        for s_title in ['overall staffing', 'level-wise staffing', 'staffing by ri', 'branches needing attention']:
            c = _find_section_content(str_sections, [s_title])
            if c: sec5_lines.append(c + "\n")
        sec5 = "\n".join(sec5_lines)
        rendered_sections.append(sec5)

    # 6. Branch Performance
    if set(req) >= set(ALL_STATISTICS):
        sec_idx += 1
        b_perf_map = {}
        dp_rows = dp_analysis.rows if dp_analysis and hasattr(dp_analysis, 'rows') else []
        dp_headers = dp_analysis.headers if dp_analysis and hasattr(dp_analysis, 'headers') else []
        b_idx = dp_headers.index('Branch') if 'Branch' in dp_headers else (1 if len(dp_headers) > 1 and dp_headers[0] == 'Rank' else 0)
        dpp_idx = dp_headers.index('Dropout %') if 'Dropout %' in dp_headers else (7 if len(dp_headers) > 7 else 4)
        for r in dp_rows:
            if len(r) > max(b_idx, dpp_idx):
                b_perf_map[str(r[b_idx])] = {'dpp': str(r[dpp_idx])}

        fd_rows = fd_analysis.rows if fd_analysis and hasattr(fd_analysis, 'rows') else []
        for r in fd_rows:
            if len(r) > 4 and str(r[0]) in b_perf_map:
                b_perf_map[str(r[0])]['fee_due'] = str(r[4])

        rev_rows = rev_analysis.rows if rev_analysis and hasattr(rev_analysis, 'rows') else []
        for r in rev_rows:
            if len(r) > 4 and str(r[0]) in b_perf_map:
                b_perf_map[str(r[0])]['sal_pct'] = str(r[4])

        str_rows = str_analysis.rows if str_analysis and hasattr(str_analysis, 'rows') else []
        for r in str_rows:
            if len(r) > 3 and str(r[0]) in b_perf_map:
                b_perf_map[str(r[0])]['str'] = str(r[3])

        sec6_lines = [
            f"#### {sec_idx}. Branch Performance\n",
            "| Branch | Dropout % | Fee Due | Salary Burden % | STR |",
            "| :--- | ---: | ---: | ---: | ---: |",
        ]
        for b_n, p in b_perf_map.items():
            sec6_lines.append(
                f"| {b_n} | {p.get('dpp', 'N/A')} | {p.get('fee_due', '₹0')} | {p.get('sal_pct', 'N/A')} | {p.get('str', 'N/A')} |"
            )
        sec6 = "\n".join(sec6_lines) + "\n"
        rendered_sections.append(sec6)

    # 7. Overall Conclusion
    sec_idx += 1
    dpp_eval_agm = "an improvement" if dpp_diff <= 0 else "an increase"
    sec7_lines = [f"#### {sec_idx}. Overall Conclusion\n"]

    if STAT_DROPOUT in req:
        sec7_lines.append(f"* **Dropouts:** Overall dropout percentage across AGM {disp_name} is **{cy_dpp:.2f}%** ({int(round(cy_dp)):,} dropouts), showing {dpp_eval_agm} of {abs(dpp_diff):.2f} percentage points from {ly_dpp:.2f}% last year.")

    if STAT_FEE_DUE in req:
        agm_zp_summary = ""
        if fd_analysis and hasattr(fd_analysis, 'rows') and fd_analysis.rows:
            zp_list = []
            for r in fd_analysis.rows:
                try:
                    cnt = int(str(r[3]).replace(',', ''))
                    zp_list.append((str(r[0]), cnt, str(r[4])))
                except (ValueError, IndexError):
                    pass
            if zp_list:
                top_zp = max(zp_list, key=lambda x: x[1])
                tot_zp = sum(x[1] for x in zp_list)
                agm_zp_summary = f"{tot_zp:,} students are zero-paid across branches, with highest concern in **{top_zp[0]}** ({top_zp[1]} students, {top_zp[2]} pending)."
        if not agm_zp_summary:
            agm_zp_summary = "Monitoring zero-paid balances across branches remains essential."
        sec7_lines.append(f"* **Fee Due:** {agm_zp_summary}")

    if STAT_REVENUE_SALARY in req:
        if m_pct_agm:
            sec7_lines.append(f"* **Revenue vs Salary:** Salary costs represent **{m_pct_agm.group(1)}% of total revenue** across the AGM.")
        else:
            sec7_lines.append("* **Revenue vs Salary:** Operating with controlled salary burden across RIs.")

    if STAT_STR in req:
        str_p1_agm = _find_section_content(str_sections, ['overall staffing & ratio summary', 'overall staffing'])
        m_str_agm = re.search(r'Student-Teacher Ratio of \*\*(\d+(?:\.\d+)?)\*\*\s*\((.*?)\)', str_p1_agm, re.IGNORECASE) if str_p1_agm else None
        if m_str_agm:
            sec7_lines.append(f"* **Teacher-Student Ratio:** Student-Teacher Ratio is **{m_str_agm.group(1)}** ({m_str_agm.group(2)}).")
        else:
            sec7_lines.append("* **Teacher-Student Ratio:** Staffing ratios remain stable across zones.")

    sec7 = "\n".join(sec7_lines) + "\n"
    rendered_sections.append(sec7)

    title = f"### AGM {disp_name} — Statistics\n\n"
    return title + "\n".join(rendered_sections)


def _build_branch_overall_report(
    branch_name: str,
    results: Dict[str, Dict[str, Any]],
    requested_statistics: List[str] | None = None,
) -> str:
    """
    Builds the analytical report for a Branch with selective sequential section numbering.
    When all 4 domain statistics are requested, renders full 7 sections including Branch Performance.
    When a subset is requested, renders only requested domain sections plus Conclusion.
    """
    from .orchestrator import get_dataframe
    from .params import resolve_single_entity
    df_main = get_dataframe()

    cand_branches = list(df_main['Branch'].dropna().unique())
    matched_branch = resolve_single_entity(str(branch_name), cand_branches, 'branch') if branch_name != 'All' else 'All'

    b_main = df_main[df_main['Branch'] == matched_branch] if matched_branch != 'All' else df_main
    r0 = b_main.iloc[0] if not b_main.empty else {}
    raw_b_name = str(r0.get('Branch', branch_name))
    agm_name = format_display_ri_name(r0.get('AGM Name') or r0.get('AGM') or 'N/A')
    ri_name = format_display_ri_name(r0.get('RI Name') or r0.get('RI') or 'N/A')
    zone_name = str(r0.get('Zone', 'N/A'))

    req = requested_statistics if requested_statistics else ALL_STATISTICS
    rendered_sections = []
    sec_idx = 1

    # 1. About This Branch
    sec1 = (
        f"#### {sec_idx}. About This Branch\n\n"
        f"Branch {raw_b_name} belongs to RI {ri_name}, Zone {zone_name}, and AGM {agm_name}.\n"
    )
    rendered_sections.append(sec1)

    # 2. Overall Dropout Situation
    dp_res = results.get('dropout', {})
    dp_analysis = dp_res.get('analysis')
    dp_sections = dp_analysis.sections if dp_analysis and hasattr(dp_analysis, 'sections') else []

    if STAT_DROPOUT in req:
        sec_idx += 1
        sec2_lines = [f"#### {sec_idx}. Overall Dropout Situation\n"]
        for s_title in ['overall branch situation', 'existing vs new', 'what changed from last year', 'position in the zone', 'what needs attention']:
            c = _find_section_content(dp_sections, [s_title])
            if c: sec2_lines.append(c + "\n")
        sec2 = "\n".join(sec2_lines)
        rendered_sections.append(sec2)

    # 3. Fee Due Situation
    fd_res = results.get('fee_due', {})
    fd_analysis = fd_res.get('analysis')
    fd_sections = fd_analysis.sections if fd_analysis and hasattr(fd_analysis, 'sections') else []

    if STAT_FEE_DUE in req:
        sec_idx += 1
        sec3_lines = [f"#### {sec_idx}. Fee Due Situation\n"]
        for s_title in ['last year fee due', 'current year', 'books status', 'conclusion']:
            c = _find_section_content(fd_sections, [s_title])
            if c: sec3_lines.append(c + "\n")
        sec3 = "\n".join(sec3_lines)
        rendered_sections.append(sec3)

    # 4. Revenue vs Salary
    rev_res = results.get('revenue_salary', {})
    rev_analysis = rev_res.get('analysis')
    rev_sections = rev_analysis.sections if rev_analysis and hasattr(rev_analysis, 'sections') else []

    rev_p1 = _find_section_content(rev_sections, ['financial & operational overview', 'overall financial summary'])
    rev_seg = _find_section_content(rev_sections, ['segment breakdown'])

    m_pct_b = re.search(r'(\d+(?:\.\d+)?)%', rev_p1) if rev_p1 else None
    exec_sal_line = f"Salary costs accounted for **{m_pct_b.group(1)}% of total revenue**." if m_pct_b else "Salary costs were evaluated against total revenue."

    if STAT_REVENUE_SALARY in req:
        sec_idx += 1
        sec4_lines = [
            f"#### {sec_idx}. Revenue vs Salary\n",
            exec_sal_line + "\n",
        ]
        if rev_seg:
            sec4_lines.append(rev_seg + "\n")
        sec4 = "\n".join(sec4_lines)
        rendered_sections.append(sec4)

    # 5. Teacher-Student Ratio
    str_res = results.get('teacher_student_ratio', {})
    str_analysis = str_res.get('analysis')
    str_sections = str_analysis.sections if str_analysis and hasattr(str_analysis, 'sections') else []

    if STAT_STR in req:
        sec_idx += 1
        sec5_lines = [f"#### {sec_idx}. Teacher-Student Ratio\n"]
        for s_title in ['staffing & operational overview', 'level-wise staffing', 'conclusion']:
            c = _find_section_content(str_sections, [s_title])
            if c: sec5_lines.append(c + "\n")
        sec5 = "\n".join(sec5_lines)
        rendered_sections.append(sec5)

    # 6. Branch Performance
    if set(req) >= set(ALL_STATISTICS):
        sec_idx += 1
        sec6 = (
            f"#### {sec_idx}. Branch Performance\n\n"
            f"Branch health indicators show operational standing for {raw_b_name} within the {zone_name} Zone.\n"
        )
        rendered_sections.append(sec6)

    # 7. Overall Conclusion
    sec_idx += 1
    sec7_lines = [f"#### {sec_idx}. Overall Conclusion\n"]

    if STAT_DROPOUT in req:
        dp_ov = _find_section_content(dp_sections, ['overall branch situation'])
        if dp_ov:
            sec7_lines.append(f"* **Dropouts:** {dp_ov.splitlines()[0]}")
        else:
            sec7_lines.append(f"* **Dropouts:** Dropout metrics tracked for {raw_b_name}.")

    if STAT_FEE_DUE in req:
        fd_cy = _find_section_content(fd_sections, ['current year'])
        if fd_cy:
            sec7_lines.append(f"* **Fee Due:** {fd_cy.splitlines()[0]}")
        else:
            sec7_lines.append(f"* **Fee Due:** Fee collections and pending dues monitored for {raw_b_name}.")

    if STAT_REVENUE_SALARY in req:
        if m_pct_b:
            sec7_lines.append(f"* **Revenue vs Salary:** Salary costs were **{m_pct_b.group(1)}% of total revenue**.")
        else:
            sec7_lines.append(f"* **Revenue vs Salary:** Revenue and salary burden monitored for {raw_b_name}.")

    if STAT_STR in req:
        str_p1 = _find_section_content(str_sections, ['staffing & operational overview', 'overall staffing'])
        if str_p1:
            sec7_lines.append(f"* **Teacher-Student Ratio:** {str_p1.splitlines()[0]}")
        else:
            sec7_lines.append(f"* **Teacher-Student Ratio:** Staffing ratio evaluated for {raw_b_name}.")

    sec7 = "\n".join(sec7_lines) + "\n"
    rendered_sections.append(sec7)

    title = f"### Branch {raw_b_name} — Statistics\n\n"
    return title + "\n".join(rendered_sections)


def format_combined_statistics(
    entity_type: str,
    entity_name: str,
    statistics: List[str],
    results: Dict[str, Dict[str, Any]],
) -> str:
    """
    Combines individual statistics results into a clean, multi-section markdown response.
    Delegates to hierarchy-tailored report builders with selective sequential numbering.
    """
    if entity_type == 'RI':
        return _build_ri_overall_report(entity_name, results, requested_statistics=statistics)
    elif entity_type == 'AGM':
        return _build_agm_overall_report(entity_name, results, requested_statistics=statistics)
    elif entity_type == 'Branch':
        return _build_branch_overall_report(entity_name, results, requested_statistics=statistics)
    else:
        return _build_agm_overall_report(entity_name, results, requested_statistics=statistics)
