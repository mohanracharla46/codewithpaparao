from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from app import db
from app.middleware.auth import login_required, role_required
from app.models.models import Course, Module, Lesson, Quiz, QuizQuestion, Profile, ActivityLog
from app.services.supabase_service import SupabaseService
from app.services.notification_service import NotificationService
from app.services.analytics_service import AnalyticsService
from datetime import datetime

admin_bp = Blueprint('admin', __name__)

# Protect all routes under this blueprint for Admins & Super Admins
@admin_bp.before_request
@login_required
@role_required(['admin', 'super_admin'])
def restrict_to_admin():
    pass

# --- COURSE CRUD ---
@admin_bp.route('/courses/new', methods=['GET', 'POST'])
def new_course():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        difficulty = request.form.get('difficulty', 'beginner')
        is_published = request.form.get('is_published') == 'on'
        thumbnail = request.files.get('thumbnail')
        
        if not title:
            flash('Course title is required.', 'danger')
            return render_template('admin/courses/new.html'), 400
            
        thumbnail_url = None
        if thumbnail and thumbnail.filename != '':
            try:
                thumbnail_url = SupabaseService.upload_file(thumbnail, 'courses', folder_name='thumbnails')
            except Exception as e:
                flash(f"Failed to upload course thumbnail: {e}", 'danger')
                
        course = Course(
            title=title,
            description=description,
            difficulty=difficulty,
            is_published=is_published,
            thumbnail_url=thumbnail_url,
            created_by=session['user_id']
        )
        db.session.add(course)
        db.session.commit()
        
        # Log activity
        AnalyticsService.log_activity(
            user_id=session['user_id'],
            action='create_course',
            details={'course_id': course.id, 'title': title},
            ip_address=request.remote_addr
        )
        
        flash('Course created successfully!', 'success')
        return redirect(url_for('dashboard.index'))
        
    return render_template('admin/courses/new.html')

@admin_bp.route('/courses/edit/<course_id>', methods=['GET', 'POST'])
def edit_course(course_id):
    course = Course.query.filter_by(id=course_id, deleted_at=None).first_or_404()
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        difficulty = request.form.get('difficulty', 'beginner')
        is_published = request.form.get('is_published') == 'on'
        thumbnail = request.files.get('thumbnail')
        
        if not title:
            flash('Course title is required.', 'danger')
            return render_template('admin/courses/edit.html', course=course), 400
            
        if thumbnail and thumbnail.filename != '':
            try:
                thumbnail_url = SupabaseService.upload_file(thumbnail, 'courses', folder_name='thumbnails')
                course.thumbnail_url = thumbnail_url
            except Exception as e:
                flash(f"Failed to upload course thumbnail: {e}", 'danger')
                
        course.title = title
        course.description = description
        course.difficulty = difficulty
        course.is_published = is_published
        course.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # Log activity
        AnalyticsService.log_activity(
            user_id=session['user_id'],
            action='edit_course',
            details={'course_id': course.id, 'title': title},
            ip_address=request.remote_addr
        )
        
        flash('Course updated successfully!', 'success')
        return redirect(url_for('dashboard.index'))
        
    return render_template('admin/courses/edit.html', course=course)

@admin_bp.route('/courses/delete/<course_id>', methods=['POST'])
def delete_course(course_id):
    course = Course.query.get_or_404(course_id)
    course.deleted_at = datetime.utcnow() # Soft delete
    db.session.commit()
    
    # Log activity
    AnalyticsService.log_activity(
        user_id=session['user_id'],
        action='delete_course',
        details={'course_id': course.id},
        ip_address=request.remote_addr
    )
    
    flash('Course deleted successfully (soft-deleted).', 'info')
    return redirect(url_for('dashboard.index'))


# --- MODULE CRUD ---
@admin_bp.route('/courses/<course_id>/modules/new', methods=['GET', 'POST'])
def new_module(course_id):
    course = Course.query.filter_by(id=course_id, deleted_at=None).first_or_404()
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        sort_order = int(request.form.get('sort_order', 0))
        
        if not title:
            flash('Module title is required.', 'danger')
            return render_template('admin/modules/new.html', course=course), 400
            
        module = Module(
            course_id=course_id,
            title=title,
            sort_order=sort_order
        )
        db.session.add(module)
        db.session.commit()
        
        flash('Module created successfully!', 'success')
        return redirect(url_for('admin.manage_course_details', course_id=course_id))
        
    return render_template('admin/modules/new.html', course=course)

@admin_bp.route('/courses/manage/<course_id>')
def manage_course_details(course_id):
    course = Course.query.filter_by(id=course_id, deleted_at=None).first_or_404()
    return render_template('admin/courses/manage.html', course=course)


# --- LESSON CRUD ---
@admin_bp.route('/modules/<module_id>/lessons/new', methods=['GET', 'POST'])
def new_lesson(module_id):
    module = Module.query.get_or_404(module_id)
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content_type = request.form.get('content_type', 'text') # text, video, pdf
        sort_order = int(request.form.get('sort_order', 0))
        text_content = request.form.get('text_content', '').strip()
        
        video_file = request.files.get('video_file')
        pdf_file = request.files.get('pdf_file')
        
        if not title:
            flash('Lesson title is required.', 'danger')
            return render_template('admin/lessons/new.html', module=module), 400
            
        video_url = None
        pdf_url = None
        
        try:
            if content_type == 'video' and video_file and video_file.filename != '':
                video_url = SupabaseService.upload_file(video_file, 'lessons', folder_name='videos')
            elif content_type == 'pdf' and pdf_file and pdf_file.filename != '':
                pdf_url = SupabaseService.upload_file(pdf_file, 'lessons', folder_name='pdfs')
        except Exception as e:
            flash(f"Failed to upload lesson asset: {e}", 'danger')
            return render_template('admin/lessons/new.html', module=module), 500
            
        lesson = Lesson(
            module_id=module_id,
            title=title,
            content_type=content_type,
            text_content=text_content,
            video_url=video_url,
            pdf_url=pdf_url,
            sort_order=sort_order
        )
        db.session.add(lesson)
        db.session.commit()
        
        flash('Lesson created successfully!', 'success')
        return redirect(url_for('admin.manage_course_details', course_id=module.course_id))
        
    return render_template('admin/lessons/new.html', module=module)


# --- QUIZ & QUESTION CRUD ---
@admin_bp.route('/modules/<module_id>/quizzes/new', methods=['GET', 'POST'])
def new_quiz(module_id):
    module = Module.query.get_or_404(module_id)
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        passing_score = int(request.form.get('passing_score', 70))
        
        if not title:
            flash('Quiz title is required.', 'danger')
            return render_template('admin/quizzes/new.html', module=module), 400
            
        quiz = Quiz(
            module_id=module_id,
            title=title,
            passing_score=passing_score
        )
        db.session.add(quiz)
        db.session.commit()
        
        flash('Quiz created successfully! Now add questions.', 'success')
        return redirect(url_for('admin.manage_quiz_questions', quiz_id=quiz.id))
        
    return render_template('admin/quizzes/new.html', module=module)

@admin_bp.route('/quizzes/<quiz_id>/questions', methods=['GET', 'POST'])
def manage_quiz_questions(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    
    if request.method == 'POST':
        question_text = request.form.get('question_text', '').strip()
        option_0 = request.form.get('option_0', '').strip()
        option_1 = request.form.get('option_1', '').strip()
        option_2 = request.form.get('option_2', '').strip()
        option_3 = request.form.get('option_3', '').strip()
        correct_option = int(request.form.get('correct_option', 0))
        
        if not question_text or not option_0 or not option_1:
            flash('Questions must have text and at least 2 options.', 'danger')
            return render_template('admin/quizzes/questions.html', quiz=quiz), 400
            
        options = [option_0, option_1]
        if option_2:
            options.append(option_2)
        if option_3:
            options.append(option_3)
            
        question = QuizQuestion(
            quiz_id=quiz_id,
            question_text=question_text,
            options=options,
            correct_option=correct_option
        )
        db.session.add(question)
        db.session.commit()
        
        flash('Question added successfully!', 'success')
        return redirect(url_for('admin.manage_quiz_questions', quiz_id=quiz_id))
        
    return render_template('admin/quizzes/questions.html', quiz=quiz)


# --- NOTIFICATIONS BROADCAST ---
@admin_bp.route('/notifications/broadcast', methods=['GET', 'POST'])
def broadcast_notification():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        message = request.form.get('message', '').strip()
        role_filter = request.form.get('role_filter', 'student') # student, admin, or None for all
        
        if not title or not message:
            flash('Title and message are required.', 'danger')
            return render_template('admin/notifications/broadcast.html'), 400
            
        # Call NotificationService
        sent_count = NotificationService.broadcast_notification(
            title=title,
            message=message,
            role_filter=role_filter if role_filter != 'all' else None
        )
        
        # Log activity
        AnalyticsService.log_activity(
            user_id=session['user_id'],
            action='broadcast_notification',
            details={'title': title, 'role_filter': role_filter, 'sent_count': sent_count},
            ip_address=request.remote_addr
        )
        
        flash(f"Notification broadcast successfully to {sent_count} user(s).", 'success')
        return redirect(url_for('dashboard.index'))
        
    return render_template('admin/notifications/broadcast.html')

# --- ANALYTICS VIEW ---
@admin_bp.route('/analytics')
def analytics():
    stats = AnalyticsService.get_admin_stats(admin_id=session['user_id'])
    
    # Fetch recent course enrollments/activity details
    recent_activities = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(15).all()
    
    return render_template('admin/analytics.html', stats=stats, recent_activities=recent_activities)

# --- ADMIN COURSES VIEW ---
@admin_bp.route('/courses')
def courses():
    courses_list = Course.query.filter_by(deleted_at=None).all()
    return render_template('admin/courses/list.html', courses=courses_list)

# --- ADMIN STUDENTS VIEW ---
@admin_bp.route('/students')
def students():
    students_list = Profile.query.filter_by(role='student').order_by(Profile.created_at.desc()).all()
    return render_template('admin/students.html', students=students_list)

# --- ADMIN QUIZZES VIEW ---
@admin_bp.route('/quizzes')
def quizzes():
    quizzes_list = Quiz.query.join(Module).join(Course).filter(Course.deleted_at == None).all()
    return render_template('admin/quizzes/list.html', quizzes=quizzes_list)

# --- ADMIN REPORTS VIEW ---
@admin_bp.route('/reports')
def reports():
    activities = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(50).all()
    return render_template('admin/reports.html', activities=activities)

# --- ADMIN CERTIFICATES VIEW ---
@admin_bp.route('/certificates')
def certificates():
    from app.models.models import Certificate
    certificates_list = Certificate.query.order_by(Certificate.issued_at.desc()).all()
    return render_template('admin/certificates.html', certificates=certificates_list)
