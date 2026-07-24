import os
import logging
from flask import Flask, session, g, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from config import config_by_name

db = SQLAlchemy()
csrf = CSRFProtect()

def create_app(config_name='development'):
    app = Flask(__name__, static_folder='static')
    app.config.from_object(config_by_name[config_name])
    
    # --- Static file caching: tell browsers to cache static assets for 7 days ---
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 60 * 60 * 24 * 7  # 7 days in seconds
    
    # Initialize extensions
    db.init_app(app)
    csrf.init_app(app)
    
    # --- Enable gzip response compression if flask_compress is installed ---
    try:
        from flask_compress import Compress
        Compress(app)
    except ImportError:
        pass  # Optional: install with 'pip install flask-compress'

    
    # Configure logging
    if not app.debug:
        logging.basicConfig(level=logging.INFO,
                            format='%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]')
    
    # Context processor to inject system settings & current user profile
    @app.context_processor
    def inject_global_data():
        from app.models.models import SystemSetting, Profile
        site_name = "CodeWithPapaRao"
        
        # Safe query
        try:
            site_info = SystemSetting.query.filter_by(key='site_info').first()
            if site_info and isinstance(site_info.value, dict):
                site_name = site_info.value.get('site_name', 'CodeWithPapaRao')
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
        from app.models.models import Batch, BatchApplication
        batches = Batch.query.order_by(Batch.start_date.asc()).all()
        applied_batch_ids = set()
        if session.get('user_id') and session.get('user_role') == 'student':
            applied = BatchApplication.query.filter_by(student_id=session['user_id']).all()
            applied_batch_ids = {app.batch_id for app in applied}
        return render_template('home.html', batches=batches, applied_batch_ids=applied_batch_ids)
        
    @app.route('/about')
    def about():
        return render_template('about.html')
        
    # Custom route to serve local uploads from /tmp/uploads on Vercel
    @app.route('/static/uploads/<path:filename>')
    def serve_uploads(filename):
        from flask import send_from_directory
        if os.environ.get('VERCEL'):
            return send_from_directory('/tmp/uploads', filename)
        return send_from_directory(os.path.join(app.root_path, 'static', 'uploads'), filename)
        
    return app
