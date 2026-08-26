from django.urls import include, path

urlpatterns = [
    path('api/', include('query_engine.urls')),
    path('', include('query_engine.urls')),
    path('assistant/', include('assistant.urls')),
]
