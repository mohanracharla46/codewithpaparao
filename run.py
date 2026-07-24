import os
from app import create_app, db

env = os.environ.get('FLASK_ENV', 'development')
app = create_app(env)

# Initialize tables & default seed data on startup
with app.app_context():
    try:
        db.create_all()
        from app.models.models import Profile, SystemSetting
        
        # Check if settings exist, seed default
        if not SystemSetting.query.filter_by(key='site_info').first():
            site_info = SystemSetting(
                key='site_info',
                value={
                    'site_name': 'CodeWithPapaRao',
                    'tagline': 'Premium SaaS Learning Portal',
                    'contact_email': 'support@codewithpaparao.com',
                    'registration_open': True
                }
            )
            db.session.add(site_info)
            db.session.commit()
            
        mock_sa_id = '00000000-0000-0000-0000-000000000001'
        mock_a_id = '00000000-0000-0000-0000-000000000002'
        mock_s_id = '00000000-0000-0000-0000-000000000003'
        
        if not Profile.query.filter_by(email='superadmin@lms.com').first():
            sa = Profile(
                id=mock_sa_id,
                first_name='Super',
                last_name='Admin',
                email='superadmin@lms.com',
                role='super_admin',
                status='active'
            )
            db.session.add(sa)
            
        admin_prof = Profile.query.filter_by(email='admin@lms.com').first()
        if not admin_prof:
            a = Profile(
                id=mock_a_id,
                first_name='Admin',
                last_name='',
                email='admin@lms.com',
                role='admin',
                status='active'
            )
            db.session.add(a)
        else:
            admin_prof.first_name = 'Admin'
            admin_prof.last_name = ''
            
        if not Profile.query.filter_by(email='student@lms.com').first():
            s = Profile(
                id=mock_s_id,
                first_name='John',
                last_name='Doe',
                email='student@lms.com',
                role='student',
                status='active'
            )
            db.session.add(s)
            
        # Seed default batches
        from app.models.models import Batch
        from datetime import date
        if not Batch.query.first():
            from app.models.models import Course
            dsa_course = Course.query.filter(Course.title.ilike('%dsa%') | Course.title.ilike('%data structure%')).first()
            cpp_course = Course.query.filter(Course.title.ilike('%c++%') | Course.title.ilike('%cpp%')).first()
            python_course = Course.query.filter(Course.title.ilike('%python%')).first()
            java_course = Course.query.filter(Course.title.ilike('%java%')).first()
            
            batches_to_seed = [
                Batch(
                    name='DSA & Algorithms Masterclass',
                    course_id=dsa_course.id if dsa_course else None,
                    start_date=date(2026, 8, 10),
                    duration='8 Weeks',
                    mode='Live Classes',
                    status='Filling Fast'
                ),
                Batch(
                    name='C++ Systems Core & Architecture',
                    course_id=cpp_course.id if cpp_course else None,
                    start_date=date(2026, 8, 18),
                    duration='6 Weeks',
                    mode='Live + Mentorship',
                    status='Open'
                ),
                Batch(
                    name='Python Core Fast-Track',
                    course_id=python_course.id if python_course else None,
                    start_date=date(2026, 9, 1),
                    duration='4 Weeks',
                    mode='Live Interactive',
                    status='Announced'
                ),
                Batch(
                    name='Java Enterprise Architecture',
                    course_id=java_course.id if java_course else None,
                    start_date=date(2026, 9, 15),
                    duration='10 Weeks',
                    mode='Live Cohort',
                    status='Announced'
                )
            ]
            for b in batches_to_seed:
                db.session.add(b)
            
        db.session.commit()
    except Exception as e:
        print(f"Database setup notice: {e}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
