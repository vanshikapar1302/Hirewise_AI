from functools import wraps
from flask import abort, redirect, url_for, request
from flask_login import current_user

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('admin.login', next=request.url))
        if not current_user.is_admin:
            # Authenticated but not an admin -> Forbidden
            abort(403)
        return f(*args, **kwargs)
    return decorated_function
