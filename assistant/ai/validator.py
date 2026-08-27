import logging
from query_engine.glossary import ABBREVIATIONS
from query_engine.metric_registry import get_default_metric_registry

logger = logging.getLogger(__name__)

SUPPORTED_OPERATIONS = {
    'top_n', 'bottom_n', 'lookup', 'group_aggregate', 'yoy_compare',
    'threshold', 'room_ratio', 'scorecard', 'filter', 'compare_dimensions'
}

def validate_command(command: dict) -> str | None:
    """Validate the structured command returned by the LLM.
    Returns an error message string if validation fails, otherwise None.
    """
    if not isinstance(command, dict):
        return "Command must be a JSON object."
    operation = command.get('operation')
    if not operation:
        return "Missing required field 'operation' in command."
    if operation not in SUPPORTED_OPERATIONS:
        return f"Unsupported operation '{operation}'."
    # Metric validation for operations that require a metric
    if operation in {'top_n', 'bottom_n', 'lookup', 'group_aggregate', 'yoy_compare', 'threshold', 'room_ratio', 'scorecard'}:
        metric = command.get('metric')
        if not metric:
            return "Missing required field 'metric' for the requested operation."
        if metric not in ABBREVIATIONS and get_default_metric_registry().get(metric) is None:
            return f"Metric '{metric}' is not recognized by the analytics engine."
    return None

