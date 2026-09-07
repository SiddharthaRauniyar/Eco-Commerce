"""View-level role guard for staff pages and future dashboard endpoints."""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def role_required(*roles: str):
    """Allow only a superuser or a member of one of the supplied role groups."""

    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            allowed = request.user.is_superuser or request.user.groups.filter(name__in=roles).exists()
            if not allowed:
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator
