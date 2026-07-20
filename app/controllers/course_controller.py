from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from app import db
from app.middleware.auth import login_required
from app.models.models import Course, Module, Lesson, StudentProgress, Bookmark, Certificate, Profile
import uuid
from datetime import datetime

course_bp = Blueprint('course', __name__)

@course_bp.route('/')
@login_required
def list_courses():
    search_query = request.args.get('search', '').strip()
    difficulty_filter = request.args.get('difficulty', '').strip()
    
    query = Course.query.filter(Course.deleted_at.is_(None), Course.is_published.is_(True))
    
    if search_query:
        query = query.filter(Course.title.ilike(f"%{search_query}%") | Course.description.ilike(f"%{search_query}%"))
        
    if difficulty_filter:
        query = query.filter(Course.difficulty == difficulty_filter)
        
    courses = query.order_by(Course.created_at.desc()).all()
    return render_template('courses/list.html', courses=courses, search=search_query, difficulty=difficulty_filter)

@course_bp.route('/<course_id>')
@login_required
def detail(course_id):
    course = Course.query.filter_by(id=course_id, deleted_at=None).first_or_404()
    
    # Calculate progress if student
    user_id = session['user_id']
    role = session['user_role']
    
    progress_pct = 0
    completed_lesson_ids = []
    
    total_lessons = sum(len(m.lessons) for m in course.modules)
    
    if role == 'student':
        # Get completed lessons in this course
        completed_progress = StudentProgress.query.filter(
            StudentProgress.student_id == user_id,
            StudentProgress.lesson_id.in_([l.id for m in course.modules for l in m.lessons])
        ).all()
        completed_lesson_ids = [p.lesson_id for p in completed_progress]
        
        if total_lessons > 0:
            progress_pct = int((len(completed_lesson_ids) / total_lessons) * 100)
            
    # Check if certificate is issued
    certificate = Certificate.query.filter_by(student_id=user_id, course_id=course_id).first()

    return render_template('courses/detail.html', 
                           course=course, 
                           progress_pct=progress_pct, 
                           completed_lesson_ids=completed_lesson_ids,
                           total_lessons=total_lessons,
                           certificate=certificate)

@course_bp.route('/lessons/<lesson_id>')
@login_required
def lesson_view(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    module = lesson.module
    course = module.course
    
    user_id = session['user_id']
    
    # Mark as completed automatically or update progress database records
    # To prevent issues, let's mark it as completed or allow the student to toggle it.
    # The requirement is "Track Progress" - we can mark it completed when they visit or hit a button.
    # Let's check if there's already a progress record
    progress = StudentProgress.query.filter_by(student_id=user_id, lesson_id=lesson_id).first()
    is_completed = progress is not None
    
    # Check bookmark state
    bookmark = Bookmark.query.filter_by(student_id=user_id, lesson_id=lesson_id).first()
    is_bookmarked = bookmark is not None
    
    # Get all lessons in this course for sidebar layout
    # Course -> Modules -> Lessons
    # Let's collect them in a flat/structured list
    sidebar_modules = course.modules # already sorted by sort_order
    
    # Find next and previous lessons
    flat_lessons = [l for m in sidebar_modules for l in m.lessons]
    current_idx = next((i for i, l in enumerate(flat_lessons) if l.id == lesson_id), -1)
    
    prev_lesson = flat_lessons[current_idx - 1] if current_idx > 0 else None
    next_lesson = flat_lessons[current_idx + 1] if current_idx < len(flat_lessons) - 1 else None

    # Load quiz for this module if it exists
    quiz = next((q for q in module.quizzes), None)

    return render_template('courses/lesson.html', 
                           lesson=lesson, 
                           module=module, 
                           course=course,
                           sidebar_modules=sidebar_modules,
                           is_completed=is_completed,
                           is_bookmarked=is_bookmarked,
                           prev_lesson=prev_lesson,
                           next_lesson=next_lesson,
                           quiz=quiz)

@course_bp.route('/lessons/<lesson_id>/complete', methods=['POST'])
@login_required
def complete_lesson(lesson_id):
    user_id = session['user_id']
    
    # Add progress record
    existing = StudentProgress.query.filter_by(student_id=user_id, lesson_id=lesson_id).first()
    if not existing:
        progress = StudentProgress(student_id=user_id, lesson_id=lesson_id)
        db.session.add(progress)
        db.session.commit()
        
    # Check if this triggers course completion and certificate issuance
    lesson = Lesson.query.get_or_404(lesson_id)
    course = lesson.module.course
    
    flat_lessons = [l for m in course.modules for l in m.lessons]
    total_lessons = len(flat_lessons)
    
    completed_count = StudentProgress.query.filter(
        StudentProgress.student_id == user_id,
        StudentProgress.lesson_id.in_([l.id for l in flat_lessons])
    ).count()
    
    certificate_generated = False
    cert_code = None
    
    if completed_count == total_lessons and total_lessons > 0:
        # Check if already issued
        existing_cert = Certificate.query.filter_by(student_id=user_id, course_id=course.id).first()
        if not existing_cert:
            cert_code = f"CERT-{course.title[:3].upper()}-{str(uuid.uuid4())[:8].upper()}"
            # Render a dummy static certificate or point to a placeholder generator
            cert = Certificate(
                student_id=user_id,
                course_id=course.id,
                certificate_code=cert_code,
                pdf_url=f"/courses/certificates/download/{cert_code}"
            )
            db.session.add(cert)
            db.session.commit()
            certificate_generated = True
            
            # Send notification
            from app.services.notification_service import NotificationService
            NotificationService.send_notification(
                user_id=user_id,
                title="Course Completed! 🎓",
                message=f"Congratulations! You have completed '{course.title}' and earned a certificate. Code: {cert_code}"
            )

    return jsonify({
        'status': 'success', 
        'completed': True,
        'progress_pct': int((completed_count / total_lessons) * 100) if total_lessons > 0 else 0,
        'certificate_generated': certificate_generated,
        'certificate_code': cert_code
    })

@course_bp.route('/lessons/<lesson_id>/bookmark', methods=['POST'])
@login_required
def toggle_bookmark(lesson_id):
    user_id = session['user_id']
    bookmark = Bookmark.query.filter_by(student_id=user_id, lesson_id=lesson_id).first()
    
    if bookmark:
        db.session.delete(bookmark)
        db.session.commit()
        bookmarked = False
    else:
        new_bookmark = Bookmark(student_id=user_id, lesson_id=lesson_id)
        db.session.add(new_bookmark)
        db.session.commit()
        bookmarked = True
        
    return jsonify({'status': 'success', 'bookmarked': bookmarked})

@course_bp.route('/certificates/download/<cert_code>')
@login_required
def download_certificate(cert_code):
    cert = Certificate.query.filter_by(certificate_code=cert_code).first_or_404()
    
    # Security check: Admins/super admins or the student themselves can access
    if session['user_role'] == 'student' and cert.student_id != session['user_id']:
        flash('Unauthorized certificate access.', 'danger')
        return redirect(url_for('dashboard.index'))
        
    return render_template('courses/certificate_pdf.html', cert=cert)
