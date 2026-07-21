import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-lms-super-secret-key-12345')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Supabase config
    SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
    SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')
    
    # Supabase PostgreSQL URI (fallback to local SQLite if not configured)
    db_url = os.environ.get('DATABASE_URL') or os.environ.get('SUPABASE_DB_URL')
    if db_url and db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
        
    if not db_url:
        if os.environ.get('VERCEL'):
            db_url = "sqlite:////tmp/lms.sqlite"
        else:
            db_url = "sqlite:///lms.sqlite"

    SQLALCHEMY_DATABASE_URI = db_url
    
    # Mock settings (if True, services will mock external API calls)
    MOCK_SERVICES = os.environ.get('MOCK_SERVICES', 'True').lower() in ('true', '1', 'yes')
    
    # Firebase Cloud Messaging config
    FIREBASE_CREDENTIALS_PATH = os.environ.get('FIREBASE_CREDENTIALS_PATH', 'firebase_credentials.json')

class DevelopmentConfig(Config):
    DEBUG = True
    WTF_CSRF_ENABLED = True

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False

class ProductionConfig(Config):
    DEBUG = False
    WTF_CSRF_ENABLED = True

config_by_name = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig
}
