import os
import logging
from flask import Flask, session, g, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from config import config_by_name

db = SQLAlchemy()
csrf = CSRFProtect()

def create_app(config_name='development'):
    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])
    
    # Initialize extensions
    db.init_app(app)
    csrf.init_app(app)
    
    # Configure logging
    if not app.debug:
        logging.basicConfig(level=logging.INFO,
                            format='%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]')
    
    # Context processor to inject system settings & current user profile
    @app.context_processor
    def inject_global_data():
        from app.models.models import SystemSetting, Profile
        site_name = "codewithpaparao"
        
        # Safe query
        try:
            site_info = SystemSetting.query.filter_by(key='site_info').first()
            if site_info and isinstance(site_info.value, dict):
                site_name = site_info.value.get('site_name', 'codewithpaparao')
        except Exception:
            pass
            
        # Get current user profile
        current_profile = None
        if 'user_id' in session:
            try:
                current_profile = Profile.query.get(session['user_id'])
            except Exception:
                pass
                
        return dict(
            site_name=site_name,
            current_profile=current_profile
        )

    # Register blueprints
    from app.controllers.auth_controller import auth_bp
    from app.controllers.dashboard_controller import dashboard_bp
    from app.controllers.course_controller import course_bp
    from app.controllers.admin_controller import admin_bp
    from app.controllers.super_admin_controller import super_admin_bp
    from app.controllers.student_controller import student_bp
    
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    app.register_blueprint(course_bp, url_prefix='/courses')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(super_admin_bp, url_prefix='/super-admin')
    app.register_blueprint(student_bp, url_prefix='/student')
    
    # Render landing home page
    @app.route('/')
    def index():
        return render_template('home.html')
        
    @app.route('/about')
    def about():
        return render_template('about.html')
        
    return app
