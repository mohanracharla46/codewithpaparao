import uuid
from datetime import datetime
from app import db
from sqlalchemy.types import TypeDecorator, CHAR
from sqlalchemy.dialects.postgresql import UUID as pgUUID

class GUID(TypeDecorator):
    """Platform-independent GUID type.
    Uses PostgreSQL's UUID type, otherwise CHAR(36), storing as string.
    """
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(pgUUID(as_uuid=False))
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        else:
            return str(value)

    def process_result_value(self, value, dialect):
        return value


class Profile(db.Model):
    __tablename__ = 'profiles'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    email = db.Column(db.String(255), unique=True, nullable=False)
    role = db.Column(db.String(20), nullable=False, default='student') # student, admin, super_admin
    avatar_url = db.Column(db.Text)
    status = db.Column(db.String(20), nullable=False, default='active') # active, suspended
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    courses_created = db.relationship('Course', backref='creator', lazy=True)
    quiz_attempts = db.relationship('QuizAttempt', backref='student', lazy=True, cascade="all, delete-orphan")
    progress_records = db.relationship('StudentProgress', backref='student', lazy=True, cascade="all, delete-orphan")
    certificates = db.relationship('Certificate', backref='student', lazy=True, cascade="all, delete-orphan")
    notifications = db.relationship('Notification', backref='user', lazy=True, cascade="all, delete-orphan")
    bookmarks = db.relationship('Bookmark', backref='student', lazy=True, cascade="all, delete-orphan")
    activity_logs = db.relationship('ActivityLog', backref='user', lazy=True)

    @property
    def full_name(self):
        return f"{self.first_name or ''} {self.last_name or ''}".strip() or self.email.split('@')[0]

class Course(db.Model):
    __tablename__ = 'courses'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    thumbnail_url = db.Column(db.Text)
    difficulty = db.Column(db.String(50), nullable=False, default='beginner') # beginner, intermediate, advanced
    is_published = db.Column(db.Boolean, nullable=False, default=False)
    created_by = db.Column(db.String(36), db.ForeignKey('profiles.id', ondelete='SET NULL'))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = db.Column(db.DateTime, nullable=True) # Soft delete

    # Relationships
    modules = db.relationship('Module', backref='course', lazy=True, order_by="Module.sort_order", cascade="all, delete-orphan")
    certificates = db.relationship('Certificate', backref='course', lazy=True, cascade="all, delete-orphan")

class Module(db.Model):
    __tablename__ = 'modules'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    course_id = db.Column(db.String(36), db.ForeignKey('courses.id', ondelete='CASCADE'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    lessons = db.relationship('Lesson', backref='module', lazy=True, order_by="Lesson.sort_order", cascade="all, delete-orphan")
    quizzes = db.relationship('Quiz', backref='module', lazy=True, cascade="all, delete-orphan")

class Lesson(db.Model):
    __tablename__ = 'lessons'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    module_id = db.Column(db.String(36), db.ForeignKey('modules.id', ondelete='CASCADE'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    content_type = db.Column(db.String(50), nullable=False) # video, pdf, text
    video_url = db.Column(db.Text)
    pdf_url = db.Column(db.Text)
    text_content = db.Column(db.Text)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    progress_records = db.relationship('StudentProgress', backref='lesson', lazy=True, cascade="all, delete-orphan")
    bookmarks = db.relationship('Bookmark', backref='lesson', lazy=True, cascade="all, delete-orphan")

class Quiz(db.Model):
    __tablename__ = 'quizzes'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    module_id = db.Column(db.String(36), db.ForeignKey('modules.id', ondelete='CASCADE'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    passing_score = db.Column(db.Integer, nullable=False, default=70) # percentage
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    questions = db.relationship('QuizQuestion', backref='quiz', lazy=True, cascade="all, delete-orphan")
    attempts = db.relationship('QuizAttempt', backref='quiz', lazy=True, cascade="all, delete-orphan")

class QuizQuestion(db.Model):
    __tablename__ = 'quiz_questions'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    quiz_id = db.Column(db.String(36), db.ForeignKey('quizzes.id', ondelete='CASCADE'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    options = db.Column(db.JSON, nullable=False) # List of strings e.g. ["A", "B", "C"]
    correct_option = db.Column(db.Integer, nullable=False) # index of correct option
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class QuizAttempt(db.Model):
    __tablename__ = 'quiz_attempts'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = db.Column(db.String(36), db.ForeignKey('profiles.id', ondelete='CASCADE'), nullable=False)
    quiz_id = db.Column(db.String(36), db.ForeignKey('quizzes.id', ondelete='CASCADE'), nullable=False)
    score = db.Column(db.Integer, nullable=False) # final score percentage
    passed = db.Column(db.Boolean, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class StudentProgress(db.Model):
    __tablename__ = 'student_progress'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = db.Column(db.String(36), db.ForeignKey('profiles.id', ondelete='CASCADE'), nullable=False)
    lesson_id = db.Column(db.String(36), db.ForeignKey('lessons.id', ondelete='CASCADE'), nullable=False)
    completed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('student_id', 'lesson_id', name='unique_student_lesson'),)

class Certificate(db.Model):
    __tablename__ = 'certificates'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = db.Column(db.String(36), db.ForeignKey('profiles.id', ondelete='CASCADE'), nullable=False)
    course_id = db.Column(db.String(36), db.ForeignKey('courses.id', ondelete='CASCADE'), nullable=False)
    certificate_code = db.Column(db.String(100), unique=True, nullable=False)
    issued_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    pdf_url = db.Column(db.Text, nullable=False)

class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('profiles.id', ondelete='CASCADE'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class Bookmark(db.Model):
    __tablename__ = 'bookmarks'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = db.Column(db.String(36), db.ForeignKey('profiles.id', ondelete='CASCADE'), nullable=False)
    lesson_id = db.Column(db.String(36), db.ForeignKey('lessons.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('student_id', 'lesson_id', name='unique_student_bookmark'),)

class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('profiles.id', ondelete='SET NULL'), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.JSON)
    ip_address = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class SystemSetting(db.Model):
    __tablename__ = 'system_settings'
    
    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.JSON, nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

class Batch(db.Model):
    __tablename__ = 'batches'
    
    id = db.Column(GUID, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(255), nullable=False)
    course_id = db.Column(GUID, db.ForeignKey('courses.id', ondelete='CASCADE'), nullable=True)
    start_date = db.Column(db.Date, nullable=False)
    duration = db.Column(db.String(100), nullable=False)
    mode = db.Column(db.String(100), nullable=False, default='Live Classes')
    status = db.Column(db.String(50), nullable=False, default='Open')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    course = db.relationship('Course', backref='batches', lazy=True)
    applications = db.relationship('BatchApplication', backref='batch', lazy=True, cascade="all, delete-orphan")

class BatchApplication(db.Model):
    __tablename__ = 'batch_applications'
    
    id = db.Column(GUID, primary_key=True, default=lambda: str(uuid.uuid4()))
    batch_id = db.Column(GUID, db.ForeignKey('batches.id', ondelete='CASCADE'), nullable=False)
    student_id = db.Column(GUID, db.ForeignKey('profiles.id', ondelete='CASCADE'), nullable=False)
    status = db.Column(db.String(50), nullable=False, default='applied') # applied, approved, rejected
    applied_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    student = db.relationship('Profile', backref='batch_applications', lazy=True)
    
    __table_args__ = (db.UniqueConstraint('batch_id', 'student_id', name='unique_student_batch_application'),)
