from functools import wraps
from flask import session, redirect, url_for, flash, request, abort
from app.models.models import Profile

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            # Save the attempted URL to redirect back after login
            session['next_url'] = request.url
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
            
        # Verify user still exists and is active
        profile = Profile.query.get(session['user_id'])
        if not profile:
            session.clear()
            flash('Your account was not found.', 'danger')
            return redirect(url_for('auth.login'))
            
        if profile.status == 'suspended':
            session.clear()
            flash('Your account has been suspended. Please contact support.', 'danger')
            return redirect(url_for('auth.login'))
            
        return f(*args, **kwargs)
    return decorated_function

def role_required(allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please log in first.', 'warning')
                return redirect(url_for('auth.login'))
                
            profile = Profile.query.get(session['user_id'])
            if not profile or profile.role not in allowed_roles:
                flash('You do not have permission to access this page.', 'danger')
                # Redirect to standard dashboard instead of showing ugly 403
                return redirect(url_for('dashboard.index'))
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator
