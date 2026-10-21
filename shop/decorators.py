from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from .models import UserProfile


def role_required(*codes):
    def decorator(view):
        @login_required
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            profile = UserProfile.objects.filter(user=request.user).select_related('role').first()
            if profile is None or profile.role.code not in codes:
                messages.error(request, 'Недостаточно прав для этого раздела.')
                return redirect('home')
            return view(request, *args, **kwargs)

        return wrapped

    return decorator
