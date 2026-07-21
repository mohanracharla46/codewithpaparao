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
        self.assertIn(b'CodeWithPapaRao', res.data)
        self.assertIn(b'Master In-Demand', res.data)

    # Test 8: Public About Me page rendering
    def test_about_page_rendering(self):
        res = self.client.get('/about')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Meet your instructor', res.data)
        self.assertIn(b'Papa Rao', res.data)

    # Test 9: Public Courses Catalog page rendering
    def test_public_courses_catalog_rendering(self):
        res = self.client.get('/courses/')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Explore Our Programming Tracks', res.data)

    # Test 10: Public Language details page rendering
    def test_language_detail_pages_public(self):
        for lang, expected_title in [('c', b'C Programming'), 
                                     ('python', b'Python Core'), 
                                     ('java', b'Java Core'), 
                                     ('cpp', b'C++ Development'), 
                                     ('dsa', b'DSA Masterclass')]:
            res = self.client.get(f'/courses/lang/{lang}')
            self.assertEqual(res.status_code, 200)
            self.assertIn(expected_title, res.data)

    # Test 11: Authenticated access to language detail seeds the course dynamically
    def test_language_detail_page_autoseed_logged_in(self):
        # Verify no C Programming course in database initially
        course = Course.query.filter_by(title='C Programming').first()
        self.assertIsNone(course)
        
        # Log in the student
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.student_profile.id
            sess['user_role'] = self.student_profile.role
            sess['user_name'] = self.student_profile.full_name
            
        # Access the C language landing page which triggers database seeding
        res = self.client.get('/courses/lang/c')
        self.assertEqual(res.status_code, 200)
        
        # Verify C Programming course now exists in database
        course = Course.query.filter_by(title='C Programming').first()
        self.assertIsNotNone(course)
        self.assertEqual(course.difficulty, 'beginner')
        
        # Verify modules and lessons were created
        self.assertTrue(len(course.modules) > 0)
        self.assertTrue(len(course.modules[0].lessons) > 0)
        
        # Verify page renders the syllabus link for logged in student
        self.assertIn(course.id.encode(), res.data)

    # Test 12: Verify that public and course reader pages do NOT display the dashboard sidebar when logged in
    def test_pages_hide_sidebar_logged_in(self):
        # Create a course and a lesson in db to check detail and lesson pages
        course = Course(
            title="Syllabus Test Course",
            description="Detail test",
            difficulty="beginner",
            is_published=True,
            created_by=self.admin_profile.id
        )
        db.session.add(course)
        db.session.commit()
        
        module = Module(course_id=course.id, title="Module 1", sort_order=1)
        db.session.add(module)
        db.session.commit()
        
        lesson = Lesson(module_id=module.id, title="Lesson 1", content_type="text", text_content="Lesson content", sort_order=1)
        db.session.add(lesson)
        db.session.commit()

        with self.client.session_transaction() as sess:
            sess['user_id'] = self.student_profile.id
            sess['user_role'] = self.student_profile.role
            sess['user_name'] = self.student_profile.full_name
            
        urls = [
            '/about', 
            '/courses/', 
            '/courses/lang/c',
            f'/courses/{course.id}',
            f'/courses/lessons/{lesson.id}'
        ]
        for url in urls:
            res = self.client.get(url)
            self.assertEqual(res.status_code, 200)
            self.assertNotIn(b'<aside class="sidebar">', res.data)

    # Test 13: Verify that language pages display multiple matching courses created by admins
    def test_language_detail_page_shows_multiple_courses(self):
        # Create two custom Python courses under the admin profile
        course1 = Course(
            title="Intro to Python Coding",
            description="First Python course.",
            difficulty="beginner",
            is_published=True,
            created_by=self.admin_profile.id
        )
        course2 = Course(
            title="Python Advanced Patterns",
            description="Second Python course.",
            difficulty="advanced",
            is_published=True,
            created_by=self.admin_profile.id
        )
        db.session.add_all([course1, course2])
        db.session.commit()
        
        # Access the Python page as guest
        res = self.client.get('/courses/lang/python')
        self.assertEqual(res.status_code, 200)
        
        # Verify both courses appear in the rendered HTML
        self.assertIn(b"Intro to Python Coding", res.data)
        self.assertIn(b"Python Advanced Patterns", res.data)
        self.assertIn(course1.id.encode(), res.data)
        self.assertIn(course2.id.encode(), res.data)

    # Test 14: Verify that admin can edit a lesson
    def test_admin_can_edit_lesson(self):
        # Create a course, a module, and a lesson
        course = Course(
            title="Intro to Rust",
            description="Learn Rust.",
            difficulty="intermediate",
            is_published=True,
            created_by=self.admin_profile.id
        )
        db.session.add(course)
        db.session.commit()
        
        module = Module(course_id=course.id, title="Basics", sort_order=1)
        db.session.add(module)
        db.session.commit()
        
        lesson = Lesson(
            module_id=module.id,
            title="Ownership",
            content_type="text",
            text_content="Original notes",
            sort_order=1
        )
        db.session.add(lesson)
        db.session.commit()
        
        # Log in as admin
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.admin_profile.id
            sess['user_role'] = self.admin_profile.role
            
        # GET edit page
        res = self.client.get(f'/admin/lessons/{lesson.id}/edit')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Ownership", res.data)
        
        # POST edit page
        res = self.client.post(f'/admin/lessons/{lesson.id}/edit', data={
            'title': 'Rust Ownership Rules',
            'content_type': 'text',
            'sort_order': '5',
            'text_content': 'Updated ownership notes'
        })
        # Check redirect back to course manager
        self.assertEqual(res.status_code, 302)
        self.assertIn(f'/courses/manage/{course.id}', res.location)
        
        # Verify db updated
        updated_lesson = Lesson.query.get(lesson.id)
        self.assertEqual(updated_lesson.title, 'Rust Ownership Rules')
        self.assertEqual(updated_lesson.sort_order, 5)
        self.assertEqual(updated_lesson.text_content, 'Updated ownership notes')

if __name__ == '__main__':
    unittest.main()
