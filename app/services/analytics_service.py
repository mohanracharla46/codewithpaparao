from app import db
from app.models.models import Profile, Course, Module, Lesson, Quiz, QuizAttempt, StudentProgress, Certificate, ActivityLog
from sqlalchemy import func

class AnalyticsService:

    @staticmethod
    def get_super_admin_stats():
        """Aggregates system-wide analytics for Super Admins."""
        total_admins = Profile.query.filter(Profile.role == 'admin').count()
        total_students = Profile.query.filter(Profile.role == 'student').count()
        total_courses = Course.query.filter(Course.deleted_at.is_(None)).count()
        total_certificates = Certificate.query.count()
        
        # Recent logs
        recent_logs = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(10).all()
        
        # Activity distribution (last 7 days counts)
        # For simplicity, returning counts
        logs_count = ActivityLog.query.count()
        
        return {
            "total_admins": total_admins,
            "total_students": total_students,
            "total_courses": total_courses,
            "total_certificates": total_certificates,
            "total_logs": logs_count,
            "recent_logs": recent_logs
        }

    @staticmethod
    def get_admin_stats(admin_id=None):
        """Aggregates analytics for courses managed by admins."""
        # Standard stats
        courses_query = Course.query.filter(Course.deleted_at.is_(None))
        if admin_id:
            courses_query = courses_query.filter(Course.created_by == admin_id)
            
        courses = courses_query.all()
        course_ids = [c.id for c in courses]
        
        total_courses = len(courses)
        published_courses = sum(1 for c in courses if c.is_published)
        
        # Student count - total unique students who have started progress or taken quizzes
        student_count = 0
        quiz_pass_rate = 0.0
        
        if course_ids:
            # Let's count how many students have certificates or progress in these courses
            # To do this, find lessons linked to these courses
            lessons = Lesson.query.join(Lesson.module).filter(Lesson.module.has(Module.course_id.in_(course_ids))).all()
            lesson_ids = [l.id for l in lessons]
            
            if lesson_ids:
                student_count = db.session.query(StudentProgress.student_id).filter(
                    StudentProgress.lesson_id.in_(lesson_ids)
                ).distinct().count()
                
            # Quiz success rate
            attempts = QuizAttempt.query.join(QuizAttempt.quiz).filter(
                Quiz.module.has(Module.course_id.in_(course_ids))
            ).all()
            
            if attempts:
                passes = sum(1 for a in attempts if a.passed)
                quiz_pass_rate = round((passes / len(attempts)) * 100, 1)

        return {
            "total_courses": total_courses,
            "published_courses": published_courses,
            "total_students": student_count,
            "quiz_pass_rate": quiz_pass_rate
        }

    @staticmethod
    def get_student_stats(student_id):
        """Aggregates learning stats for a student."""
        # Total lessons completed
        completed_lessons = StudentProgress.query.filter_by(student_id=student_id).count()
        
        # Certificates earned
        certificates_count = Certificate.query.filter_by(student_id=student_id).count()
        
        # Quizzes taken
        attempts = QuizAttempt.query.filter_by(student_id=student_id).all()
        quizzes_taken = len(attempts)
        
        # Average quiz score
        avg_score = 0
        if attempts:
            avg_score = int(sum(a.score for a in attempts) / quizzes_taken)
            
        # Unique courses started (student has completed at least one lesson or earned certificate)
        # Let's find distinct course IDs from lessons completed
        started_courses = db.session.query(Course.id).join(Module).join(Lesson).join(
            StudentProgress, StudentProgress.lesson_id == Lesson.id
        ).filter(StudentProgress.student_id == student_id).distinct().count()

        return {
            "completed_lessons": completed_lessons,
            "certificates_count": certificates_count,
            "quizzes_taken": quizzes_taken,
            "avg_score": avg_score,
            "started_courses": started_courses
        }
        
    @staticmethod
    def log_activity(user_id, action, details=None, ip_address=None):
        """Creates an audit log entry in the activity_logs table."""
        try:
            log = ActivityLog(
                user_id=user_id,
                action=action,
                details=details or {},
                ip_address=ip_address
            )
            db.session.add(log)
            db.session.commit()
        except Exception:
            db.session.rollback()
