from flask import Blueprint, render_template, session, redirect, url_for
from app.middleware.auth import login_required
from app.services.analytics_service import AnalyticsService
from app.models.models import Profile, Course, StudentProgress, Notification, Bookmark

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@login_required
def index():
    user_id = session['user_id']
    role = session['user_role']
    
    if role == 'super_admin':
        stats = AnalyticsService.get_super_admin_stats()
        return render_template('dashboard/super_admin.html', stats=stats)
        
    elif role == 'admin':
        stats = AnalyticsService.get_admin_stats(admin_id=user_id)
        # Fetch courses managed by this admin
        courses = Course.query.filter_by(created_by=user_id, deleted_at=None).all()
        return render_template('dashboard/admin.html', stats=stats, courses=courses)
        
    else: # student
        stats = AnalyticsService.get_student_stats(student_id=user_id)
        
        # Enrolled courses: courses where student has done some lesson progress
        # Or courses that are published. For a simple student dashboard:
        # Let's show all published courses and mark progress
        published_courses = Course.query.filter_by(is_published=True, deleted_at=None).all()
        
        # Calculate progress percentage per course
        courses_with_progress = []
        for course in published_courses:
            # count lessons in course
            total_lessons = 0
            for module in course.modules:
                total_lessons += len(module.lessons)
                
            completed_in_course = 0
            if total_lessons > 0:
                # count lessons completed by student in this course
                # we query lessons inside modules of this course
                completed_lessons = StudentProgress.query.filter(
                    StudentProgress.student_id == user_id,
                    StudentProgress.lesson_id.in_([l.id for m in course.modules for l in m.lessons])
                ).count()
                progress_pct = int((completed_lessons / total_lessons) * 100)
            else:
                progress_pct = 0
                
            courses_with_progress.append({
                'course': course,
                'progress': progress_pct,
                'total_lessons': total_lessons
            })
            
        # Bookmarks
        bookmarks = Bookmark.query.filter_by(student_id=user_id).all()
        
        # Unread notifications
        notifications = Notification.query.filter_by(user_id=user_id, is_read=False).order_by(Notification.created_at.desc()).limit(5).all()
        
        return render_template('dashboard/student.html', 
                               stats=stats, 
                               courses_with_progress=courses_with_progress,
                               bookmarks=bookmarks,
                               notifications=notifications)
