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
        youtube_url = request.form.get('youtube_url', '').strip()
        pdf_file = request.files.get('pdf_file')
        
        if not title:
            flash('Lesson title is required.', 'danger')
            return render_template('admin/lessons/new.html', module=module), 400
            
        video_url = None
        pdf_url = None
        
        try:
            if content_type == 'video':
                if video_file and video_file.filename != '':
                    video_url = SupabaseService.upload_file(video_file, 'lessons', folder_name='videos')
                elif youtube_url:
                    import re
                    pattern = r'(?:https?://)?(?:www\.)?(?:youtube\.com/(?:[^/]+/.+/|(?:v|e(?:mbed)?)/|.*[?&]v=)|youtu\.be/)([^"&?/ ]{11})'
                    match = re.search(pattern, youtube_url)
                    if match:
                        video_url = f"https://www.youtube.com/embed/{match.group(1)}"
                    else:
                        video_url = youtube_url
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

@admin_bp.route('/lessons/<lesson_id>/edit', methods=['GET', 'POST'])
def edit_lesson(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    module = Module.query.get_or_404(lesson.module_id)
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content_type = request.form.get('content_type', 'text')
        sort_order = int(request.form.get('sort_order', 0))
        text_content = request.form.get('text_content', '').strip()
        
        video_file = request.files.get('video_file')
        youtube_url = request.form.get('youtube_url', '').strip()
        pdf_file = request.files.get('pdf_file')
        
        if not title:
            flash('Lesson title is required.', 'danger')
            return render_template('admin/lessons/edit.html', lesson=lesson, module=module), 400
            
        try:
            if content_type == 'video':
                if video_file and video_file.filename != '':
                    lesson.video_url = SupabaseService.upload_file(video_file, 'lessons', folder_name='videos')
                elif youtube_url:
                    import re
                    pattern = r'(?:https?://)?(?:www\.)?(?:youtube\.com/(?:[^/]+/.+/|(?:v|e(?:mbed)?)/|.*[?&]v=)|youtu\.be/)([^"&?/ ]{11})'
                    match = re.search(pattern, youtube_url)
                    if match:
                        lesson.video_url = f"https://www.youtube.com/embed/{match.group(1)}"
                    else:
                        lesson.video_url = youtube_url
            elif content_type == 'pdf' and pdf_file and pdf_file.filename != '':
                lesson.pdf_url = SupabaseService.upload_file(pdf_file, 'lessons', folder_name='pdfs')
        except Exception as e:
            flash(f"Failed to upload lesson asset: {e}", 'danger')
            return render_template('admin/lessons/edit.html', lesson=lesson, module=module), 500
            
        lesson.title = title
        lesson.content_type = content_type
        lesson.text_content = text_content
        lesson.sort_order = sort_order
        
        db.session.commit()
        flash('Lesson updated successfully!', 'success')
        return redirect(url_for('admin.manage_course_details', course_id=module.course_id))
        
    return render_template('admin/lessons/edit.html', lesson=lesson, module=module)


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

# --- ADMIN BATCHES VIEW & CRUD ---
@admin_bp.route('/batches')
def list_batches():
    from app.models.models import Batch
    batches_list = Batch.query.order_by(Batch.start_date.asc()).all()
    return render_template('admin/batches/list.html', batches=batches_list)

@admin_bp.route('/batches/new', methods=['GET', 'POST'])
def new_batch():
    from app.models.models import Batch, Course
    courses_list = Course.query.filter_by(deleted_at=None).all()
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        course_id = request.form.get('course_id', '').strip()
        start_date_str = request.form.get('start_date', '').strip()
        duration = request.form.get('duration', '').strip()
        mode = request.form.get('mode', 'Live Classes').strip()
        status = request.form.get('status', 'Open').strip()
        
        if not name or not start_date_str or not duration:
            flash('Batch name, start date, and duration are required.', 'danger')
            return render_template('admin/batches/new.html', courses=courses_list), 400
            
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid start date format. Use YYYY-MM-DD.', 'danger')
            return render_template('admin/batches/new.html', courses=courses_list), 400
            
        batch = Batch(
            name=name,
            course_id=course_id if course_id else None,
            start_date=start_date,
            duration=duration,
            mode=mode,
            status=status
        )
        db.session.add(batch)
        db.session.commit()
        
        # Log activity
        AnalyticsService.log_activity(
            user_id=session['user_id'],
            action='create_batch',
            details={'batch_id': batch.id, 'name': name},
            ip_address=request.remote_addr
        )
        
        flash('Live batch created successfully!', 'success')
        return redirect(url_for('admin.list_batches'))
        
    return render_template('admin/batches/new.html', courses=courses_list)

@admin_bp.route('/batches/applications/<batch_id>')
def view_batch_applicants(batch_id):
    from app.models.models import Batch, BatchApplication
    batch = Batch.query.get_or_404(batch_id)
    applications = BatchApplication.query.filter_by(batch_id=batch_id).order_by(BatchApplication.applied_at.desc()).all()
    return render_template('admin/batches/applicants.html', batch=batch, applications=applications)

@admin_bp.route('/batches/applications/<app_id>/status', methods=['POST'])
def update_application_status(app_id):
    from app.models.models import BatchApplication
    application = BatchApplication.query.get_or_404(app_id)
    status = request.form.get('status', 'applied').strip()
    
    if status not in ['applied', 'approved', 'rejected']:
        flash('Invalid status value.', 'danger')
        return redirect(url_for('admin.view_batch_applicants', batch_id=application.batch_id))
        
    application.status = status
    db.session.commit()
    
    # Notify student
    from app.services.notification_service import NotificationService
    status_emoji = '✅' if status == 'approved' else '❌' if status == 'rejected' else '📥'
    NotificationService.send_notification(
        user_id=application.student_id,
        title=f"Batch Application Update {status_emoji}",
        message=f"Your application for '{application.batch.name}' has been {status}."
    )
    
    flash(f"Application status updated to '{status}' successfully!", 'success')
    return redirect(url_for('admin.view_batch_applicants', batch_id=application.batch_id))
