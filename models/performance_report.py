from datetime import datetime
from database.connection import db

class PerformanceReport(db.Model):
    __tablename__ = 'performance_reports'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey('interview_sessions.id', ondelete='CASCADE'), nullable=False)
    technical_score = db.Column(db.Float, default=0.0)
    communication_score = db.Column(db.Float, default=0.0)
    confidence_score = db.Column(db.Float, default=0.0)
    overall_score = db.Column(db.Float, default=0.0)
    feedback_summary = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref=db.backref('performance_reports', lazy='dynamic', cascade="all, delete-orphan"))
    session = db.relationship('InterviewSession', backref=db.backref('performance_report', uselist=False, cascade="all, delete-orphan"))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __repr__(self):
        return f'<PerformanceReport id={self.id} user_id={self.user_id} score={self.overall_score}>'
