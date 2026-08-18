from datetime import datetime
from sqlalchemy.orm import synonym
from database.connection import db

class InterviewResponse(db.Model):
    __tablename__ = 'interview_responses'

    id = db.Column(db.Integer, primary_key=True)
    interview_id = db.Column(db.Integer, db.ForeignKey('interview_sessions.id', ondelete='CASCADE'), nullable=False)
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=True)
    skill = db.Column(db.String(100), nullable=True)
    score = db.Column(db.Float, default=0.0)

    # Synonyms for backward compatibility if needed
    session_id = synonym('interview_id')
    question_text = synonym('question')
    transcript = synonym('answer')

    interview_session = db.relationship('InterviewSession', backref=db.backref('interview_responses_list', lazy='dynamic', cascade="all, delete-orphan"))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __repr__(self):
        return f"<InterviewResponse id={self.id} interview_id={self.interview_id}>"
