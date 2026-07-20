import os
import json
from flask import current_app
from app import db
from app.models.models import Notification, Profile

class NotificationService:
    _initialized = False

    @classmethod
    def initialize_firebase(cls):
        """Initializes Firebase Admin SDK if credentials JSON exists."""
        if cls._initialized:
            return True
            
        cred_path = current_app.config.get('FIREBASE_CREDENTIALS_PATH')
        if cred_path and os.path.exists(cred_path):
            try:
                import firebase_admin
                from firebase_admin import credentials
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
                cls._initialized = True
                current_app.logger.info("Firebase SDK initialized successfully.")
                return True
            except Exception as e:
                current_app.logger.error(f"Failed to initialize Firebase Admin SDK: {e}")
        return False

    @classmethod
    def send_notification(cls, user_id, title, message, data_payload=None) -> bool:
        """Sends a notification to a specific user.
        
        Saves the notification to the database AND attempts to send via Firebase FCM if configured.
        """
        # 1. Save to local SQL database (so it shows in user notification center)
        try:
            notification = Notification(
                user_id=user_id,
                title=title,
                message=message
            )
            db.session.add(notification)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to save notification to database: {e}")
            return False

        # 2. Attempt FCM push
        if cls.initialize_firebase():
            try:
                from firebase_admin import messaging
                # Retrieve user push tokens from user profiles or user settings.
                # In this version, we will mock FCM push since user device tokens require a frontend client registration.
                # If we had a token, we would:
                # message = messaging.Message(
                #     notification=messaging.Notification(title=title, body=message),
                #     token=user_device_token,
                #     data=data_payload
                # )
                # messaging.send(message)
                pass
            except Exception as e:
                current_app.logger.error(f"Firebase FCM Delivery failed: {e}")
                
        # Return True since database save was successful
        return True

    @classmethod
    def broadcast_notification(cls, title, message, role_filter=None) -> int:
        """Sends a notification to multiple users (e.g. all students or all admins)."""
        query = Profile.query.filter(Profile.status == 'active')
        if role_filter:
            query = query.filter(Profile.role == role_filter)
            
        users = query.all()
        sent_count = 0
        
        for user in users:
            if cls.send_notification(user.id, title, message):
                sent_count += 1
                
        return sent_count
