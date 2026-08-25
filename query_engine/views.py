from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .router import route_question
from .serializers import QuerySerializer


class QueryView(APIView):
    def post(self, request):
        serializer = QuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question = serializer.validated_data['question']

        # `filters` is only present in validated_data when the caller sent
        # a "filters" object at all (nested serializers don't materialize
        # field defaults when their key is absent from the input). Normalize
        # to the same All/empty defaults either way, so every pre-function
        # handler can rely on a complete context dict being passed in --
        # whether or not this particular request included one.
        filters = serializer.validated_data.get('filters') or {}
        context = {
            'agm': filters.get('agm') or 'All',
            'ri': filters.get('ri') or 'All',
            'zone': filters.get('zone') or 'All',
            'branches': filters.get('branches') or ['All'],
        }

        handler = route_question(question)
        if handler is None:
            return Response({
                'success': False,
                'answer': 'This query is not supported yet. Currently supported: top 5 branches with the highest dropout percentage.',
                'function': None,
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = handler(context)
        except (FileNotFoundError, ValueError) as exc:
            return Response({
                'success': False,
                'answer': str(exc),
                'function': None,
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            'success': True,
            'answer': result['answer'],
            'function': result['function'],
            'data': result['data'],
        })


class HealthView(APIView):
    def get(self, request):
        return Response({'success': True, 'service': 'branch-query-engine'})
