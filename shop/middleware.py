from django.conf import settings


class TrustPreviewOriginMiddleware:
    """Учебный сервер: доверять Origin текущего просмотра, чтобы формы входа работали."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.DEBUG:
            origin = request.META.get('HTTP_ORIGIN')
            if origin and origin not in settings.CSRF_TRUSTED_ORIGINS:
                settings.CSRF_TRUSTED_ORIGINS.append(origin)
        return self.get_response(request)
