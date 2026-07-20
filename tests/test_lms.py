import unittest
import os
import sys

# Ensure workspace root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.models import Profile, Course, Module, Lesson

class LMSTestCase(unittest.TestCase):
    def setUp(self):
        # Configure app in testing mode
        self.app = create_app('testing')
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        
        # Build clean database
        db.create_all()
        
        # Seed test profiles
        self.student_profile = Profile(
            id='student-uuid-1234',
            first_name='Test',
            last_name='Student',
            email='teststudent@lms.com',
            role='student',
            status='active'
        )
        self.admin_profile = Profile(
            id='admin-uuid-1234',
            first_name='Test',
            last_name='Admin',
            email='testadmin@lms.com',
            role='admin',
            status='active'
        )
        self.superadmin_profile = Profile(
            id='superadmin-uuid-1234',
            first_name='Test',
            last_name='SuperAdmin',
            email='testsa@lms.com',
            role='super_admin',
            status='active'
        )
        db.session.add_all([self.student_profile, self.admin_profile, self.superadmin_profile])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    # Test 1: Basic profiles database creation
    def test_profile_creation(self):
        p = Profile.query.filter_by(email='teststudent@lms.com').first()
        self.assertIsNotNone(p)
        self.assertEqual(p.role, 'student')
        self.assertEqual(p.full_name, 'Test Student')

    # Test 2: Anonymous redirects to login
    def test_anonymous_access_redirects(self):
        res = self.client.get('/dashboard/')
        self.assertEqual(res.status_code, 302)
        self.assertIn('/auth/login', res.location)

    # Test 3: Authenticated access to dashboard
    def test_student_dashboard_access(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.student_profile.id
            sess['user_role'] = self.student_profile.role
            sess['user_name'] = self.student_profile.full_name
            
        res = self.client.get('/dashboard/')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Student Portal', res.data)

    # Test 4: Student RBAC restriction checking
    def test_student_rbac_restriction(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.student_profile.id
            sess['user_role'] = self.student_profile.role
            
        # Attempt to access admin routes (expect redirect with flash warning, or status code 302)
        res = self.client.get('/admin/analytics')
        self.assertEqual(res.status_code, 302)
        self.assertIn('/dashboard/', res.location)
        
        # Attempt to access super admin routes
        res = self.client.get('/super-admin/settings')
        self.assertEqual(res.status_code, 302)
        self.assertIn('/dashboard/', res.location)

    # Test 5: Admin RBAC accessibility
    def test_admin_rbac_accessibility(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.admin_profile.id
            sess['user_role'] = self.admin_profile.role
            
        res = self.client.get('/admin/analytics')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Curriculum Analytics', res.data)

    # Test 6: Course CRUD creation
    def test_course_creation_model(self):
        c = Course(
            title='Intro to AI',
            description='Learn machine learning principles.',
            difficulty='beginner',
            is_published=True,
            created_by=self.admin_profile.id
        )
        db.session.add(c)
        db.session.commit()
        
        saved_course = Course.query.filter_by(title='Intro to AI').first()
        self.assertIsNotNone(saved_course)
        self.assertEqual(saved_course.difficulty, 'beginner')
        self.assertTrue(saved_course.is_published)

    # Test 7: Landing page rendering
    def test_landing_page_rendering(self):
        res = self.client.get('/')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'codewithpaparao', res.data)
        self.assertIn(b'Master In-Demand', res.data)

if __name__ == '__main__':
    unittest.main()
