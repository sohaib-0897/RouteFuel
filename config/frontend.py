"""Serve the compiled RouteFuel shell; API and fallback map stay independent."""

from django.conf import settings
from django.http import FileResponse, HttpResponse
from django.views.decorators.http import require_GET


@require_GET
def frontend(request):
    index = settings.FRONTEND_DIST / "index.html"
    if not index.is_file():
        return HttpResponse(
            "RouteFuel frontend is not built. Run npm ci && npm run build in frontend/. "
            "The API remains available at /api/docs/.",
            status=503,
            content_type="text/plain",
        )
    response = FileResponse(index.open("rb"), content_type="text/html")
    response["Cache-Control"] = "no-cache"
    return response
