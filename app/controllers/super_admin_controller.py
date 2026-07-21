from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, Response
from app import db
from app.middleware.auth import login_required, role_required
from app.models.models import Profile, SystemSetting, ActivityLog
from app.services.analytics_service import AnalyticsService
import json

super_admin_bp = Blueprint('super_admin', __name__)

# Protect all routes in this blueprint for Super Admins only
@super_admin_bp.before_request
@login_required
@role_required(['super_admin'])
def restrict_to_super_admin():
    pass

# --- MANAGE ADMINS & USERS ---
@super_admin_bp.route('/users', methods=['GET'])
def list_users():
    search_query = request.args.get('search', '').strip()
    role_filter = request.args.get('role', '').strip()
    
    query = Profile.query
    
    if search_query:
        query = query.filter(Profile.email.ilike(f"%{search_query}%") | 
                             Profile.first_name.ilike(f"%{search_query}%") | 
                             Profile.last_name.ilike(f"%{search_query}%"))
                             
    if role_filter:
        query = query.filter(Profile.role == role_filter)
        
    users = query.order_by(Profile.created_at.desc()).all()
    return render_template('super_admin/users.html', users=users, search=search_query, role_filter=role_filter)

@super_admin_bp.route('/users/role/<user_id>', methods=['POST'])
def change_role(user_id):
    profile = Profile.query.get_or_404(user_id)
    
    # Prevent self-demotion
    if profile.id == session['user_id']:
        flash('You cannot change your own role.', 'danger')
        return redirect(url_for('super_admin.list_users')), 400
        
    new_role = request.form.get('role')
    if new_role not in ['student', 'admin', 'super_admin']:
        flash('Invalid role choice.', 'danger')
        return redirect(url_for('super_admin.list_users')), 400
        
    old_role = profile.role
    profile.role = new_role
    db.session.commit()
    
    # Log activity
    AnalyticsService.log_activity(
        user_id=session['user_id'],
        action='change_user_role',
        details={'target_user': user_id, 'old_role': old_role, 'new_role': new_role},
        ip_address=request.remote_addr
    )
    
    flash(f"Role for {profile.email} changed to {new_role}.", 'success')
    return redirect(url_for('super_admin.list_users'))

@super_admin_bp.route('/users/status/<user_id>', methods=['POST'])
def toggle_status(user_id):
    profile = Profile.query.get_or_404(user_id)
    
    # Prevent self-suspension
    if profile.id == session['user_id']:
        flash('You cannot suspend your own account.', 'danger')
        return redirect(url_for('super_admin.list_users')), 400
        
    new_status = 'suspended' if profile.status == 'active' else 'active'
    profile.status = new_status
    db.session.commit()
    
    # Log activity
    AnalyticsService.log_activity(
        user_id=session['user_id'],
        action='toggle_user_status',
        details={'target_user': user_id, 'new_status': new_status},
        ip_address=request.remote_addr
    )
    
    flash(f"User {profile.email} status set to {new_status}.", 'success')
    return redirect(url_for('super_admin.list_users'))


# --- GLOBAL SITE CONFIGURATION ---
@super_admin_bp.route('/settings', methods=['GET', 'POST'])
def settings():
    site_info_setting = SystemSetting.query.filter_by(key='site_info').first()
    
    if not site_info_setting:
        site_info_setting = SystemSetting(
            key='site_info',
            value={
                'site_name': 'CodeWithPapaRao',
                'tagline': 'Premium SaaS Learning Portal',
                'contact_email': 'support@codewithpaparao.com',
                'registration_open': True
            }
        )
        db.session.add(site_info_setting)
        db.session.commit()
        
    site_info = site_info_setting.value
    
    if request.method == 'POST':
        site_name = request.form.get('site_name', 'CodeWithPapaRao').strip()
        tagline = request.form.get('tagline', '').strip()
        contact_email = request.form.get('contact_email', '').strip()
        registration_open = request.form.get('registration_open') == 'on'
        
        updated_value = {
            'site_name': site_name,
            'tagline': tagline,
            'contact_email': contact_email,
            'registration_open': registration_open
        }
        
        # We assign a copy or use flag_modified
        site_info_setting.value = updated_value
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(site_info_setting, "value")
        db.session.commit()
        
        # Log activity
        AnalyticsService.log_activity(
            user_id=session['user_id'],
            action='update_system_settings',
            details=updated_value,
            ip_address=request.remote_addr
        )
        
        flash('System settings updated successfully!', 'success')
        return redirect(url_for('super_admin.settings'))
        
    return render_template('super_admin/settings.html', site_info=site_info)


# --- SYSTEM AUDIT LOGS ---
@super_admin_bp.route('/logs', methods=['GET'])
def list_logs():
    search_query = request.args.get('search', '').strip()
    action_filter = request.args.get('action', '').strip()
    
    query = ActivityLog.query
    
    if search_query:
        query = query.join(Profile).filter(Profile.email.ilike(f"%{search_query}%"))
        
    if action_filter:
        query = query.filter(ActivityLog.action == action_filter)
        
    logs = query.order_by(ActivityLog.created_at.desc()).limit(100).all()
    
    # Get distinct action types for filter options
    actions = [row[0] for row in db.session.query(ActivityLog.action).distinct().all()]
    
    return render_template('super_admin/logs.html', logs=logs, search=search_query, actions=actions, action_filter=action_filter)


# --- DATABASE BACKUP (MOCK EXPORT) ---
@super_admin_bp.route('/backup', methods=['GET'])
def database_backup():
    # Fetch profiles, courses, settings to dump into JSON format
    profiles = Profile.query.all()
    logs = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(50).all()
    
    backup_data = {
        'timestamp': db.func.now().columns[0] if hasattr(db.func, 'now') else str(db.func.now()),
        'users_count': len(profiles),
        'users': [{'email': p.email, 'role': p.role, 'status': p.status} for p in profiles],
        'recent_logs': [{'user': l.user.email if l.user else 'System', 'action': l.action, 'time': str(l.created_at)} for l in logs]
    }
    
    # Log backup activity
    AnalyticsService.log_activity(
        user_id=session['user_id'],
        action='trigger_database_backup',
        ip_address=request.remote_addr
    )
    
    # Return as JSON file attachment
    json_dump = json.dumps(backup_data, indent=2)
    return Response(
        json_dump,
        mimetype="application/json",
        headers={"Content-disposition": "attachment; filename=lms_backup_metadata.json"}
    )
