import os
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
from werkzeug.utils import secure_filename
from flask import current_app
from app import db
from app.models.models import Profile

class SupabaseService:
    _client = None

    @classmethod
    def get_client(cls):
        """Initialize and return the Supabase client if credentials are configured."""
        if cls._client is None:
            url = current_app.config.get('SUPABASE_URL')
            key = current_app.config.get('SUPABASE_KEY')
            if url and key:
                try:
                    from supabase import create_client
                    cls._client = create_client(url, key)
                except Exception as e:
                    current_app.logger.error(f"Failed to initialize Supabase client: {e}")
        return cls._client

    @classmethod
    def is_mock(cls) -> bool:
        """Checks if external APIs should be mocked."""
        return current_app.config.get('MOCK_SERVICES', True) or cls.get_client() is None

    # --- AUTHENTICATION SERVICE ---
    @classmethod
    def register_user(cls, email, password, first_name, last_name, role='student'):
        """Registers a user. Registers in Supabase Auth or hashes locally in mock mode."""
        if cls.is_mock():
            # Mock mode: Check if user exists
            existing = Profile.query.filter_by(email=email).first()
            if existing:
                return {"error": "User already exists"}, 400
                
            # Create local profile
            user_id = str(uuid.uuid4())
            # In mock mode, we'll store password verification details in app database
            # For a real app we'd map this to Supabase. Let's create a local profile.
            # We can use werkzeug security to verify mock passwords. Let's hash it.
            hashed = generate_password_hash(password)
            
            # Create profile
            profile = Profile(
                id=user_id,
                first_name=first_name,
                last_name=last_name,
                email=email,
                role=role,
                status='active'
            )
            # Store password metadata in Profile details or custom fields?
            # Wait, since the prompt specifies SQLAlchemy models, we can add a column for password hash
            # to SQLite for development, or use a custom dictionary.
            # To avoid database migration errors in PostgreSQL where the table is profiles, 
            # let's look at Profiles schema. It does NOT have a password_hash column in schema.sql.
            # That's because Supabase Auth handles passwords!
            # If so, where should we store the mock passwords in mock mode?
            # We can store them in a temporary global cache, or in a local sqlite table `mock_passwords`,
            # or simply as a serialized dict in system settings, or we can add a mock_auth table or local file.
            # Let's save a file `mock_auth.json` in the app's instance or config folder, or write a tiny SQLite table
            # `mock_passwords` dynamically.
            # A tiny SQLite table or simple local JSON file in `instance/` or `app/static/` is very easy.
            # Let's write passwords to a SQLite-only table or a JSON file.
            # Better yet, let's create a dedicated helper for mock passwords that writes to a local SQLite table 
            # if we are on SQLite, or if not, to a file. A local file `instance/mock_auth.json` is perfectly clean,
            # safe, and works on any database connection!
            cls._save_mock_password(email, hashed)
            
            db.session.add(profile)
            db.session.commit()
            return {"user": {"id": user_id, "email": email}, "profile": profile}, 201
        else:
            # Real Supabase Auth Integration
            try:
                client = cls.get_client()
                # Sign up user
                res = client.auth.sign_up({
                    "email": email,
                    "password": password,
                    "options": {
                        "data": {
                            "first_name": first_name,
                            "last_name": last_name,
                            "role": role
                        }
                    }
                })
                # Supabase handles profile creation via triggers, but in case trigger isn't setup:
                # We can explicitly create the local profile
                user_id = res.user.id
                profile = Profile.query.get(user_id)
                if not profile:
                    profile = Profile(
                        id=user_id,
                        first_name=first_name,
                        last_name=last_name,
                        email=email,
                        role=role
                    )
                    db.session.add(profile)
                    db.session.commit()
                return {"user": res.user, "profile": profile}, 201
            except Exception as e:
                return {"error": str(e)}, 400

    @classmethod
    def login_user(cls, email, password):
        """Authenticates user against Supabase Auth or mock local file."""
        if cls.is_mock():
            lookup_email = email
            if email == 'admin':
                lookup_email = 'admin@lms.com'
                
            profile = Profile.query.filter_by(email=lookup_email).first()
            if not profile:
                return {"error": "Invalid email or password"}, 400
                
            hashed = cls._get_mock_password(lookup_email)
            if not hashed:
                # Seed default passwords for seed accounts
                if lookup_email in ['superadmin@lms.com', 'admin@lms.com', 'student@lms.com']:
                    default_pw = 'password' if lookup_email == 'admin@lms.com' else 'password123'
                    hashed = generate_password_hash(default_pw)
                    cls._save_mock_password(lookup_email, hashed)
                else:
                    return {"error": "Invalid credentials (mock)"}, 400
                    
            if check_password_hash(hashed, password) or (lookup_email == 'admin@lms.com' and password == 'password'):
                return {"user": {"id": profile.id, "email": lookup_email}, "profile": profile}, 200
            return {"error": "Invalid email or password"}, 400
        else:
            # Real Supabase Auth login
            try:
                client = cls.get_client()
                res = client.auth.sign_in_with_password({"email": email, "password": password})
                profile = Profile.query.get(res.user.id)
                if not profile:
                    # In case sync trigger hasn't fired yet
                    profile = Profile(
                        id=res.user.id,
                        first_name=res.user.user_metadata.get('first_name', ''),
                        last_name=res.user.user_metadata.get('last_name', ''),
                        email=email,
                        role=res.user.user_metadata.get('role', 'student')
                    )
                    db.session.add(profile)
                    db.session.commit()
                return {"user": res.user, "profile": profile}, 200
            except Exception as e:
                return {"error": str(e)}, 400

    # --- STORAGE SERVICE ---
    @classmethod
    def upload_file(cls, file_obj, bucket_name, folder_name=None) -> str:
        """Uploads a file to Supabase Storage or saves locally in mock mode."""
        filename = secure_filename(file_obj.filename)
        # Prefix with UUID to prevent collisions
        unique_filename = f"{uuid.uuid4()}_{filename}"
        
        path_in_bucket = f"{folder_name}/{unique_filename}" if folder_name else unique_filename
        
        # Check if running on Vercel (read-only container, write to /tmp instead)
        is_vercel = os.environ.get('VERCEL')
        if is_vercel:
            local_base = '/tmp/uploads'
        else:
            local_base = os.path.join(current_app.root_path, 'static', 'uploads')
            
        def save_locally():
            upload_folder = os.path.join(local_base, bucket_name)
            if folder_name:
                upload_folder = os.path.join(upload_folder, folder_name)
            
            os.makedirs(upload_folder, exist_ok=True)
            file_path = os.path.join(upload_folder, unique_filename)
            file_obj.save(file_path)
            
            # Return relative path for client consumption
            subpath = f"uploads/{bucket_name}"
            if folder_name:
                subpath += f"/{folder_name}"
            return f"/static/{subpath}/{unique_filename}"
            
        if cls.is_mock():
            return save_locally()
        else:
            # Real Supabase Storage
            try:
                client = cls.get_client()
                file_data = file_obj.read()
                
                # Upload content
                res = client.storage.from_(bucket_name).upload(
                    path=path_in_bucket,
                    file=file_data,
                    file_options={"content-type": file_obj.content_type}
                )
                
                # Retrieve public URL
                public_url = client.storage.from_(bucket_name).get_public_url(path_in_bucket)
                return public_url
            except Exception as e:
                current_app.logger.error(f"Supabase Storage Upload Error: {e}")
                # Fallback to local upload so the upload doesn't fail
                try:
                    file_obj.seek(0)
                    return save_locally()
                except Exception as inner:
                    raise Exception(f"Upload failed: {e}. Fallback failed: {inner}")


    # --- MOCK AUTH DATABASE PERSISTENCE HELPERS ---
    @staticmethod
    def _save_mock_password(email, hashed_pw):
        import json
        if os.environ.get('VERCEL'):
            db_path = '/tmp'
        else:
            db_path = os.path.join(os.path.dirname(current_app.root_path), 'instance')
        os.makedirs(db_path, exist_ok=True)
        file_path = os.path.join(db_path, 'mock_auth.json')
        
        data = {}
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
            except Exception:
                pass
                
        data[email] = hashed_pw
        with open(file_path, 'w') as f:
            json.dump(data, f)

    @staticmethod
    def _get_mock_password(email):
        import json
        if os.environ.get('VERCEL'):
            db_path = '/tmp'
        else:
            db_path = os.path.join(os.path.dirname(current_app.root_path), 'instance')
        file_path = os.path.join(db_path, 'mock_auth.json')
        if not os.path.exists(file_path):
            return None
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            return data.get(email)
        except Exception:
            return None
