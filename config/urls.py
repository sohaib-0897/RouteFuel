from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from config.frontend import frontend
from routes.views import RouteView, health, route_map

urlpatterns = [
    path("", frontend, name="frontend"),
    path("health/", health),
    path("api/v1/route/", RouteView.as_view()),
    path("api/v1/route/<uuid:route_id>/map/", route_map, name="route-map"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema")),
]
