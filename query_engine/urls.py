from django.urls import path

from .views import HealthView, QueryView

urlpatterns = [
    path('query/', QueryView.as_view(), name='query'),
    path('health/', HealthView.as_view(), name='health'),
    path('', HealthView.as_view(), name='root-health'),
]
