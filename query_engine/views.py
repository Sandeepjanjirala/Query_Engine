from django.shortcuts import render
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .filters import apply_filter_context
from .glossary import AGM_COLUMN, BRANCH_COLUMN, RI_COLUMN, ZONE_COLUMN
from .query_planner import get_prepared_dataframe
from .router import route_question
from .serializers import QuerySerializer


class QueryView(APIView):
    def post(self, request):
        serializer = QuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question = serializer.validated_data['question']

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
                'answer': 'This query is not supported yet. Could you please try again.',
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


class FilterOptionsView(APIView):
    def get(self, request):
        agm = request.query_params.get('agm') or 'All'
        ri = request.query_params.get('ri') or 'All'
        zone = request.query_params.get('zone') or 'All'

        try:
            df = get_prepared_dataframe([], context={})
        except Exception:
            return Response({
                'agms': ['All'], 'ris': ['All'], 'zones': ['All'], 'branches': ['All']
            })

        # All unique AGMs
        agms = ['All']
        if AGM_COLUMN in df.columns:
            all_agms = df[AGM_COLUMN].dropna().unique()
            agms.extend(sorted([str(a).strip() for a in all_agms if str(a).strip()]))

        # RIs under selected AGM
        df_agm = apply_filter_context(df, {'agm': agm, 'ri': 'All', 'zone': 'All', 'branches': ['All']})
        ris = ['All']
        if RI_COLUMN in df_agm.columns:
            all_ris = df_agm[RI_COLUMN].dropna().unique()
            ris.extend(sorted([str(r).strip() for r in all_ris if str(r).strip()]))

        # Zones under selected AGM + RI
        df_ri = apply_filter_context(df, {'agm': agm, 'ri': ri, 'zone': 'All', 'branches': ['All']})
        zones = ['All']
        if ZONE_COLUMN in df_ri.columns:
            all_zones = df_ri[ZONE_COLUMN].dropna().unique()
            zones.extend(sorted([str(z).strip() for z in all_zones if str(z).strip()]))

        # Branches under selected AGM + RI + Zone
        df_zone = apply_filter_context(df, {'agm': agm, 'ri': ri, 'zone': zone, 'branches': ['All']})
        branches = ['All']
        if BRANCH_COLUMN in df_zone.columns:
            all_b = df_zone[BRANCH_COLUMN].dropna().unique()
            branches.extend(sorted([str(b).strip() for b in all_b if str(b).strip()]))

        return Response({
            'agms': agms,
            'ris': ris,
            'zones': zones,
            'branches': branches
        })


class HealthView(APIView):
    def get(self, request):
        return Response({'success': True, 'service': 'branch-query-engine'})


def dashboard_view(request):
    return render(request, 'query_engine/index.html')


def full_dash_view(request):
    return render(request, 'query_engine/full_dash.html')
