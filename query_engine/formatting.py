from __future__ import annotations

from .glossary import ABBREVIATIONS

_EXTRA_LABELS = {
    'Avg-SPS': 'Average Students Per Section',
    'occupancy_rate': 'Room Occupancy Percentage',
    'vacancy_rate': 'Room Vacancy Percentage',
}


def _metric_label(metric: str) -> str:
    return ABBREVIATIONS.get(metric) or _EXTRA_LABELS.get(metric, metric)


def format_top_5_dropout(results: list[dict]) -> str:
    if not results:
        return 'No branch dropout data is available.'

    lines = ['Top 5 branches with the highest dropout percentage:']
    for item in results:
        lines.append(f"{item['rank']}. {item['branch']} — {item['dropout_percentage']:.2f}%")
    return '\n'.join(lines)


def format_ranked_branches(results: list[dict], metric: str, ascending: bool) -> str:
    if not results:
        return f'No data is available for {_metric_label(metric)} with the current filters.'
    heading = 'lowest' if ascending else 'highest'
    lines = [f'Branches ranked by {_metric_label(metric)} ({heading} first):']
    for item in results:
        lines.append(f"{item['rank']}. {item['branch']} — {item['value']:.2f}")
    return '\n'.join(lines)


def format_branch_lookup(results: list[dict], columns: list[str]) -> str:
    if not results:
        return 'No matching branch data found for the current filters.'
    lines = []
    for entry in results:
        parts = [f"{_metric_label(col)}: {entry.get(col)}" for col in columns]
        lines.append(f"{entry['branch']} — " + ', '.join(parts))
    return '\n'.join(lines)


def format_group_aggregate(results: list[dict], metric: str, group_dimension: str, agg: str) -> str:
    if not results:
        return f'No data is available to aggregate {_metric_label(metric)} by {group_dimension}.'
    verb = {'sum': 'Total', 'mean': 'Average', 'count': 'Count of'}.get(agg, 'Total')
    lines = [f'{verb} {_metric_label(metric)} by {group_dimension}:']
    for item in results:
        lines.append(f"{item['group']} — {item['value']:.2f}")
    return '\n'.join(lines)


def format_year_over_year(results: list[dict], metric: str) -> str:
    if not results:
        return f'No year-over-year data is available for {_metric_label(metric)}.'
    lines = [f'Branches ranked by change in {_metric_label(metric)} (current year vs last year):']
    for item in results:
        sign = '+' if item['change'] >= 0 else ''
        lines.append(
            f"{item['rank']}. {item['branch']} — LY {item['last_year']:.2f} → "
            f"CY {item['current_year']:.2f} ({sign}{item['change']:.2f})"
        )
    return '\n'.join(lines)


def format_staff_summary(results: list[dict], columns: list[str]) -> str:
    if not results:
        return 'No staff data is available for the current filters.'
    lines = ['Staff count summary:']
    for entry in results:
        parts = [f"{_metric_label(col)}: {entry.get(col)}" for col in columns]
        lines.append(f"{entry['branch']} — " + ', '.join(parts))
    return '\n'.join(lines)


def format_room_snapshot(results: list[dict], columns: list[str]) -> str:
    if not results:
        return 'No room utilization data is available for the current filters.'
    lines = ['Room utilization snapshot:']
    for entry in results:
        parts = [f"{_metric_label(col)}: {entry.get(col)}" for col in columns]
        lines.append(f"{entry['branch']} — " + ', '.join(parts))
    return '\n'.join(lines)


def format_sections_sps_snapshot(results: list[dict], columns: list[str]) -> str:
    if not results:
        return 'No sections/students-per-section data is available for the current filters.'
    lines = ['Sections & students-per-section snapshot:']
    for entry in results:
        parts = [f"{_metric_label(col)}: {entry.get(col)}" for col in columns]
        lines.append(f"{entry['branch']} — " + ', '.join(parts))
    return '\n'.join(lines)


def format_strength_difference(results: list[dict], metric: str) -> str:
    if not results:
        return f'No data is available for {_metric_label(metric)}.'
    lines = [f'Branches ranked by {_metric_label(metric)}:']
    for item in results:
        lines.append(f"{item['rank']}. {item['branch']} — {item['value']:.2f}")
    return '\n'.join(lines)


def format_branch_scorecard(entry: dict | None, branch: str) -> str:
    if not entry:
        return f'No data is available for branch "{branch}" with the current filters.'
    lines = [f"Scorecard for {entry['branch']}:"]
    for key, value in entry.items():
        if key == 'branch':
            continue
        lines.append(f"{_metric_label(key)}: {value}")
    return '\n'.join(lines)


def format_threshold_result(res: dict, metric: str) -> str:
    count = res['count']
    op_symbol = {'>': 'above', 'gt': 'above', '>=': 'at least', 'gte': 'at least',
                 '<': 'below', 'lt': 'below', '<=': 'at most', 'lte': 'at most'}.get(res['op'], res['op'])
    target_entity = f"{res['group_column'].upper()}s" if res.get('group_column') else 'branches'

    if res.get('count_only'):
        return f"{count} {target_entity} have {_metric_label(metric)} {op_symbol} {res['threshold']}."

    if count == 0:
        return f"No {target_entity} found with {_metric_label(metric)} {op_symbol} {res['threshold']}."

    lines = [f"{count} {target_entity} with {_metric_label(metric)} {op_symbol} {res['threshold']}:"]
    for item in res['records']:
        name = item.get('group') or item.get('branch')
        lines.append(f"- {name} — {item['value']:.2f}")
    return '\n'.join(lines)


def format_dimension_comparison(res: dict, metric: str, dimension_type: str) -> str:
    if res.get('comparison_type') == 'yoy_breakdown':
        lines = [f"{_metric_label(metric)} CY vs LY by {dimension_type}:"]
        for item in res['data']:
            sign = '+' if item['change'] >= 0 else ''
            lines.append(
                f"- {item['category']} — LY {item['last_year']:.2f} → CY {item['current_year']:.2f} ({sign}{item['change']:.2f})"
            )
        if res.get('winner'):
            w = res['winner']
            lines.append(f"Top change: {w['category']} ({w['change']:+.2f})")
        return '\n'.join(lines)

    if res.get('comparison_type') == 'grouped':
        lines = [f"{_metric_label(metric)} comparison by {res['group_column']}:"]
        for row in res['data']:
            parts = [f"{k}: {v}" for k, v in row.items() if k != 'group']
            lines.append(f"{row['group']} — " + ', '.join(parts))
        return '\n'.join(lines)

    lines = [f"{_metric_label(metric)} comparison across {dimension_type}:"]
    for item in res['data']:
        lines.append(f"- {item['category']} — {item['value']:.2f}")
    if res.get('winner'):
        w = res['winner']
        lines.append(f"Selected category: {w['category']} ({w['value']:.2f})")
    return '\n'.join(lines)


def format_room_ratio(results: list[dict], ratio_type: str, ascending: bool | None) -> str:
    if not results:
        return f'No {ratio_type} data available for branches.'
    heading = 'Room Occupancy Percentage' if ratio_type == 'occupancy' else 'Room Vacancy Percentage'
    lines = [f'Branches ranked by {heading}:']
    for item in results:
        lines.append(f"{item['rank']}. {item['branch']} — {item['percentage']:.2f}% (Occupied: {item['noor']}, Vacant: {item['novr']}, Total: {item['nocr']})")
    return '\n'.join(lines)


def format_scope_total(val: float, metric: str) -> str:
    return f"Total {_metric_label(metric)} in current scope: {val:.2f}"
