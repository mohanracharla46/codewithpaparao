from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from app.services.supabase_service import SupabaseService
from app.services.analytics_service import AnalyticsService
from app.models.models import Profile

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        if not email or not password:
            flash('Please fill in all fields.', 'danger')
            return render_template('auth/login.html'), 400

        res, status_code = SupabaseService.login_user(email, password)
        
        if status_code == 200:
            user_data = res.get('user', {})
            profile = res.get('profile')
            
            # Store in session
            session['user_id'] = profile.id
            session['user_role'] = profile.role
            session['user_email'] = profile.email
            session['user_name'] = profile.full_name
            
            # Audit log
            AnalyticsService.log_activity(
                user_id=profile.id,
                action='login',
                details={'email': email},
                ip_address=request.remote_addr
            )
            
            flash(f'Welcome back, {profile.first_name or "User"}!', 'success')
            
            # Redirect to next url if present
            next_url = session.pop('next_url', None)
            if next_url:
                return redirect(next_url)
            return redirect(url_for('dashboard.index'))
        else:
            flash(res.get('error', 'Login failed. Please verify credentials.'), 'danger')

    return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        role = request.form.get('role', 'student') # default role selection in UI (students/admins)

        # Validate input
        if not first_name or not email or not password:
            flash('Required fields are missing.', 'danger')
            return render_template('auth/register.html'), 400

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/register.html'), 400

        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'danger')
            return render_template('auth/register.html'), 400
            
        # Restrict admin registrations to specific domains or mock controls
        # For our local demo we allow selection, but log it
        if role not in ['student', 'admin', 'super_admin']:
            role = 'student'

        res, status_code = SupabaseService.register_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            role=role
        )

        if status_code == 201:
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('auth.login'))
        else:
            flash(res.get('error', 'Registration failed. User may already exist.'), 'danger')

    return render_template('auth/register.html')

@auth_bp.route('/logout')
def logout():
    user_id = session.get('user_id')
    if user_id:
        AnalyticsService.log_activity(
            user_id=user_id,
            action='logout',
            ip_address=request.remote_addr
        )
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        if not email:
            flash('Please enter your email.', 'danger')
            return render_template('auth/reset_password.html'), 400

        # For mock, we simply print to console & display success
        flash('Password reset link has been sent to your email.', 'info')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html')
