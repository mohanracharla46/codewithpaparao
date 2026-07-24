from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from app import db
from app.middleware.auth import login_required, role_required
from app.models.models import Quiz, QuizQuestion, QuizAttempt, Notification, Bookmark, Profile, Course, Lesson
from app.services.supabase_service import SupabaseService
from app.services.analytics_service import AnalyticsService

student_bp = Blueprint('student', __name__)

@student_bp.route('/profile', methods=['GET', 'POST'])
@login_required
@role_required(['student'])
def profile():
    user_id = str(session['user_id'])  # Ensure it's a string for path operations
    profile = Profile.query.get_or_404(user_id)
    
    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        avatar_file = request.files.get('avatar')
        
        if not first_name:
            flash('First name is required.', 'danger')
            return render_template('student/profile.html', profile=profile), 400
            
        profile.first_name = first_name
        profile.last_name = last_name
        
        if avatar_file and avatar_file.filename != '':
            try:
                # Upload avatar to Supabase Storage in 'avatars' bucket
                # user_id must be str for os.path.join in upload_file
                avatar_url = SupabaseService.upload_file(avatar_file, 'avatars', folder_name=user_id)
                profile.avatar_url = avatar_url
            except Exception as e:
                flash(f"Failed to upload profile picture: {e}", 'danger')
                
        db.session.commit()
        db.session.refresh(profile)  # Refresh to ensure in-memory object matches DB
        
        # Update session with new name
        new_full_name = profile.full_name
        session['user_name'] = new_full_name
        session.modified = True  # Force session to persist the update
        
        # Log activity
        AnalyticsService.log_activity(
            user_id=user_id,
            action='update_profile',
            details={'first_name': first_name, 'last_name': last_name},
            ip_address=request.remote_addr
        )
        
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('student.profile'))
        
    return render_template('student/profile.html', profile=profile)


@student_bp.route('/quizzes/<quiz_id>', methods=['GET'])
@login_required
@role_required(['student'])
def take_quiz(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    # Check if student is enrolled in the course containing this quiz
    # Course -> Module -> Quiz
    course = quiz.module.course
    
    # Render quiz attempt page
    return render_template('student/take_quiz.html', quiz=quiz, course=course)

@student_bp.route('/quizzes/<quiz_id>/submit', methods=['POST'])
@login_required
@role_required(['student'])
def submit_quiz(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    user_id = session['user_id']
    
    # Calculate score
    questions = quiz.questions
    total_questions = len(questions)
    
    if total_questions == 0:
        return jsonify({'error': 'Quiz has no questions.'}), 400
        
    correct_count = 0
    answers = request.json.get('answers', {}) # Dict of {question_id: selected_option_index}
    
    for q in questions:
        submitted_ans = answers.get(q.id)
        if submitted_ans is not None and int(submitted_ans) == q.correct_option:
            correct_count += 1
            
    score_pct = int((correct_count / total_questions) * 100)
    passed = score_pct >= quiz.passing_score
    
    # Record attempt
    attempt = QuizAttempt(
        student_id=user_id,
        quiz_id=quiz_id,
        score=score_pct,
        passed=passed
    )
    db.session.add(attempt)
    db.session.commit()
    
    # Log activity
    AnalyticsService.log_activity(
        user_id=user_id,
        action='submit_quiz',
        details={'quiz_id': quiz_id, 'score': score_pct, 'passed': passed},
        ip_address=request.remote_addr
    )
    
    return jsonify({
        'status': 'success',
        'score': score_pct,
        'passed': passed,
        'correct_count': correct_count,
        'total_questions': total_questions,
        'passing_score': quiz.passing_score
    })

@student_bp.route('/notifications', methods=['GET'])
@login_required
def notifications():
    user_id = session['user_id']
    notifications_list = Notification.query.filter_by(user_id=user_id).order_by(Notification.created_at.desc()).all()
    return render_template('student/notifications.html', notifications=notifications_list)

@student_bp.route('/notifications/<notification_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    user_id = session['user_id']
    notification = Notification.query.filter_by(id=notification_id, user_id=user_id).first_or_404()
    notification.is_read = True
    db.session.commit()
    return jsonify({'status': 'success'})

@student_bp.route('/notifications/read-all', methods=['POST'])
@login_required
def mark_all_notifications_read():
    user_id = session['user_id']
    notifications = Notification.query.filter_by(user_id=user_id, is_read=False).all()
    for n in notifications:
        n.is_read = True
    db.session.commit()
    return jsonify({'status': 'success', 'count': len(notifications)})

@student_bp.route('/bookmarks', methods=['GET'])
@login_required
@role_required(['student'])
def bookmarks():
    user_id = session['user_id']
    bookmarks_list = Bookmark.query.filter_by(student_id=user_id).all()
    return render_template('student/bookmarks.html', bookmarks=bookmarks_list)

@student_bp.route('/batches/apply/<batch_id>', methods=['POST'])
@login_required
@role_required(['student'])
def apply_batch(batch_id):
    from app.models.models import Batch, BatchApplication
    user_id = session['user_id']
    
    batch = Batch.query.get_or_404(batch_id)
    
    existing = BatchApplication.query.filter_by(batch_id=batch_id, student_id=user_id).first()
    if existing:
        flash(f"You have already applied for the batch '{batch.name}'.", 'warning')
        return redirect(url_for('index'))
        
    application = BatchApplication(
        batch_id=batch_id,
        student_id=user_id,
        status='applied'
    )
    db.session.add(application)
    db.session.commit()
    
    AnalyticsService.log_activity(
        user_id=user_id,
        action='apply_batch',
        details={'batch_id': batch_id, 'batch_name': batch.name},
        ip_address=request.remote_addr
    )
    
    from app.services.notification_service import NotificationService
    NotificationService.send_notification(
        user_id=user_id,
        title="Batch Application Received 📥",
        message=f"Your application for the cohort '{batch.name}' has been received and is pending admin review."
    )
    
    flash(f"Successfully applied for the batch '{batch.name}'!", 'success')
    return redirect(url_for('index'))
