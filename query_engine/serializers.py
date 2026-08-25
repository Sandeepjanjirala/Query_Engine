from rest_framework import serializers


class FilterContextSerializer(serializers.Serializer):
    """
    Optional AGM / RI / Branch scope forwarded by branch_dashboard
    alongside the question, reflecting whatever the dashboard's own
    filter dropdowns are currently set to.

    This is part of making the /api/query/ contract extensible for the
    future 100+ pre-functions: any handler that needs to scope its answer
    to the caller's current filter selection can accept this dict, while
    handlers that don't care about it (like the current single
    pre-function) simply ignore it. Every field defaults to "no filter"
    so a caller that omits `filters` entirely -- including every existing
    test and any future caller that doesn't need filter scoping -- keeps
    working unchanged.
    """

    agm = serializers.CharField(required=False, allow_blank=True, default="All")
    ri = serializers.CharField(required=False, allow_blank=True, default="All")
    zone = serializers.CharField(required=False, allow_blank=True, default="All")
    branches = serializers.ListField(
        child=serializers.CharField(allow_blank=True),
        required=False,
        default=list,
    )


class QuerySerializer(serializers.Serializer):
    question = serializers.CharField(required=True, allow_blank=False, trim_whitespace=True)
    filters = FilterContextSerializer(required=False)
