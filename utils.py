from functools import wraps
from flask import abort
from flask_login import current_user, login_required

def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not getattr(current_user, "is_admin", False):
            abort(403)
        return view(*args, **kwargs)
    return wrapped

def role_required(*allowed_roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            role = (getattr(current_user, "role", "") or "").lower()
            if role not in [r.lower() for r in allowed_roles]:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator