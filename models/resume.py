from datetime import datetime
from sqlalchemy.orm import synonym
from database.connection import db

class Resume(db.Model):
    __tablename__ = 'resumes'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    file_path = db.Column(db.String(512), nullable=False)
    extracted_skills = db.Column(db.Text, nullable=True)
    projects = db.Column(db.Text, nullable=True)
    ats_score = db.Column(db.Integer, nullable=True, default=0)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Synonyms for backward compatibility
    created_at = synonym('uploaded_at')

    user = db.relationship('User', backref=db.backref('candidate_resumes_list', lazy='dynamic', cascade="all, delete-orphan"))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __repr__(self):
        return f"<Resume id={self.id} user_id={self.user_id} file_path={self.file_path}>"
