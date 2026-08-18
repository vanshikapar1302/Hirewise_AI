from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import synonym
from database.connection import db

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(512), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id', ondelete='SET NULL'), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Synonyms and Role String Column for database requirements
    hashed_password = synonym('password_hash')
    registration_date = synonym('created_at')
    account_status = synonym('is_active')
    role = db.Column(db.String(50), default='user')
    
    # Extra user details
    full_name = db.Column(db.String(100), nullable=True)
    profile_photo = db.Column(db.String(256), nullable=True, default='default_profile.png')
    last_login = db.Column(db.DateTime, nullable=True)
    total_interviews = db.Column(db.Integer, default=0, nullable=False)
    average_score = db.Column(db.Float, default=0.0, nullable=False)
    highest_score = db.Column(db.Float, default=0.0, nullable=False)
    skill_level = db.Column(db.String(50), default='Beginner', nullable=False)
    mentor_sessions_count = db.Column(db.Integer, default=0, nullable=False)
    total_practice_time = db.Column(db.Integer, default=0, nullable=False) # stored in seconds
    
    # Notification Preferences
    login_emails_enabled = db.Column(db.Boolean, default=True, nullable=False)
    security_alerts_enabled = db.Column(db.Boolean, default=True, nullable=False)
    interview_reports_enabled = db.Column(db.Boolean, default=True, nullable=False)
    resume_notifications_enabled = db.Column(db.Boolean, default=True, nullable=False)
    marketing_emails_enabled = db.Column(db.Boolean, default=False, nullable=False)
    
    # Relationships
    role_obj = db.relationship('Role', backref=db.backref('users', lazy='dynamic'))
    interviews = db.relationship('InterviewSession', backref='user', lazy='dynamic', cascade="all, delete-orphan")

    @property
    def is_admin(self):
        return (self.role == 'admin') or (self.role_obj is not None and self.role_obj.name == 'ADMIN')

    @property
    def role_name(self):
        if self.role:
            return self.role.upper()
        return self.role_obj.name if self.role_obj else 'USER'
    
    @property
    def name(self):
        return self.full_name or self.username
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
        
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.role:
            if self.role_obj and self.role_obj.name == 'ADMIN':
                self.role = 'admin'
            else:
                self.role = 'user'

    def __repr__(self):
        return f'<User {self.username}>'

