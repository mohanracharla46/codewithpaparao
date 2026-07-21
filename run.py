import os
from app import create_app, db

env = os.environ.get('FLASK_ENV', 'development')
app = create_app(env)

if __name__ == '__main__':
    with app.app_context():
        # Setup tables (specifically for SQLite development/testing)
        db.create_all()
        # Seed basic system settings and initial superadmin if needed
        from app.models.models import Profile, SystemSetting
        import uuid
        
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
            
        # Seed a mock admin/superadmin for initial local developer setup if it's empty
        # We can seed a superadmin, an admin, and a student user.
        # Since it is a demo environment, this helps developers boot it instantly.
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
            
        db.session.commit()
        print("Database seeded with default mock profiles:")
        print(" - Super Admin: superadmin@lms.com")
        print(" - Admin: admin@lms.com (credentials: admin / password)")
        print(" - Student: student@lms.com")
        print("All mock passwords in mock mode are 'password123', except Admin which is 'password'.")
        
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
