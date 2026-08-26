from typing import Callable, Dict, Any

from query_engine.orchestrator import (
    run_rank_branches_by_metric,
    run_branch_metric_lookup,
    run_group_metric_aggregate,
    run_year_over_year_change_ranking,
    run_filter_by_threshold,
    run_calculate_room_ratio,
    run_branch_scorecard,
)


def route_command_to_handler(command: dict) -> Callable[[Dict[str, Any]], Dict[str, Any]] | None:
    """Translate a structured command into a callable handler that invokes the existing orchestrator.
    The returned handler accepts a ``context`` dict (currently unused) and returns the standard result dict
    with ``answer`` and ``data`` keys.
    """
    operation = command.get('operation')
    if not operation:
        return None

    # Helper to wrap orchestrator functions with the expected signature (params, context)
    def make_handler(fn, params: dict) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
        def handler(context: dict | None = None):
            return fn(params, context or {})
        return handler

    # ---- Top / Bottom N ranking ----
    if operation in {'top_n', 'bottom_n'}:
        params = {
            'metric': command.get('metric'),
            'n': command.get('n', 5),
            'ascending': operation == 'bottom_n',
        }
        return make_handler(run_rank_branches_by_metric, params)

    # ---- Lookup ----
    if operation == 'lookup':
        params = {
            'metrics': [command.get('metric')],
            'branches': command.get('branches'),
        }
        return make_handler(run_branch_metric_lookup, params)

    # ---- Group aggregate ----
    if operation == 'group_aggregate':
        params = {
            'metric': command.get('metric'),
            'group_dimension': command.get('group_by'),
            'agg': command.get('agg'),
            'n': command.get('n'),
            'ascending': command.get('ascending', False),
        }
        return make_handler(run_group_metric_aggregate, params)

    # ---- Year‑over‑Year comparison ----
    if operation == 'yoy_compare':
        params = {
            'metric': command.get('metric'),
            'direction': command.get('direction', 'positive'),
            'n': command.get('n', 5),
        }
        return make_handler(run_year_over_year_change_ranking, params)

    # ---- Threshold filter ----
    if operation == 'threshold':
        params = {
            'metric': command.get('metric'),
            'op': command.get('op', 'gt'),
            'threshold': command.get('threshold'),
            'count_only': command.get('count_only', False),
            'group_dimension': command.get('group_by'),
        }
        return make_handler(run_filter_by_threshold, params)

    # ---- Room ratio ----
    if operation == 'room_ratio':
        params = {
            'ratio_type': command.get('ratio_type'),
            'n': command.get('n'),
            'ascending': command.get('ascending'),
        }
        return make_handler(run_calculate_room_ratio, params)

    # ---- Scorecard (branch scorecard / snapshot) ----
    if operation == 'scorecard':
        params = {
            'branches': command.get('branches'),
        }
        return make_handler(run_branch_scorecard, params)

    # Unsupported operation
    return None
