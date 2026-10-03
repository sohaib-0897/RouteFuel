from rest_framework.exceptions import APIException
from rest_framework.views import exception_handler as drf_exception_handler


class RouteError(APIException):
    def __init__(self, message: str, code: str = "route_error", status: int = 422):
        self.status_code = status
        super().__init__(message, code)


def exception_handler(exc: Exception, context: dict):
    response = drf_exception_handler(exc, context)
    if response is not None and isinstance(exc, RouteError):
        response.data = {"error": {"code": exc.get_codes(), "message": str(exc.detail)}}
    return response
