from django.core.cache import cache
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from .errors import RouteError
from .serializers import RouteRequestSerializer, RouteResponseSerializer
from .service import plan_route
from .stations import station_index


class RouteView(APIView):
    @extend_schema(
        request=RouteRequestSerializer,
        responses={
            200: RouteResponseSerializer,
            400: OpenApiResponse(description="Invalid request"),
            422: OpenApiResponse(description="Location or fuel plan cannot be resolved"),
            502: OpenApiResponse(description="Malformed provider response"),
            503: OpenApiResponse(description="Data, key, or quota unavailable"),
            504: OpenApiResponse(description="Provider timeout"),
        },
    )
    def post(self, request) -> Response:
        serializer = RouteRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(plan_route(**serializer.validated_data))


@require_GET
def health(request: HttpRequest) -> JsonResponse:
    try:
        index = station_index()
        return JsonResponse({"status": "ok", "station_data_available": True, "stations": len(index.stations)})
    except RouteError:
        return JsonResponse({"status": "degraded", "station_data_available": False}, status=503)


@require_GET
def route_map(request: HttpRequest, route_id) -> HttpResponse:
    plan = cache.get(f"map:{route_id}")
    if plan is None:
        return JsonResponse(
            {"error": {"code": "map_expired", "message": "Map expired or missing. Submit the route again."}},
            status=404,
        )
    return render(request, "routes/map.html", {"plan": plan})
