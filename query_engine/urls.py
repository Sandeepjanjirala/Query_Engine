from django.urls import path

from .views import (
    FilterOptionsView,
    HealthView,
    QueryView,
    dashboard_view,
    full_dash_view,
)

urlpatterns = [
    path('query/', QueryView.as_view(), name='query'),
    path('filters/', FilterOptionsView.as_view(), name='filters'),
    path('health/', HealthView.as_view(), name='health'),
    path('dash', full_dash_view, name='full-dash'),
    path('dashboard', dashboard_view, name='dashboard'),
    path('', dashboard_view, name='root-dashboard'),
]
