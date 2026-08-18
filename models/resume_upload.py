from datetime import datetime
from database.connection import db

class ResumeUpload(db.Model):
    __tablename__ = 'resume_uploads'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    filename = db.Column(db.String(256), nullable=False)
    file_path = db.Column(db.String(512), nullable=False)
    parsed_text = db.Column(db.Text, nullable=True)
    skills_extracted = db.Column(db.Text, nullable=True) # Comma-separated or JSON
    projects = db.Column(db.Text, nullable=True)
    experience = db.Column(db.Text, nullable=True)
    certifications = db.Column(db.Text, nullable=True)
    missing_skills = db.Column(db.Text, nullable=True)
    ats_score = db.Column(db.Integer, nullable=True, default=0)
    suggestions_generated = db.Column(db.Text, nullable=True)
    custom_questions = db.Column(db.Text, nullable=True) # JSON array of strings
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship
    user = db.relationship('User', backref=db.backref('resumes', lazy='dynamic', cascade="all, delete-orphan"))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __repr__(self):
        return f'<ResumeUpload id={self.id} user_id={self.user_id} filename={self.filename}>'
