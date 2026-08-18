import json
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym
from database.connection import db

if TYPE_CHECKING:
    from models.response import Response

class InterviewSession(db.Model):
    __tablename__ = 'interview_sessions'

    id: Mapped[int] = mapped_column(db.Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    interview_type: Mapped[str] = mapped_column(db.String(50), nullable=False)  # 'HR', 'Technical', 'Mixed', 'Company', 'Resume'
    company_name: Mapped[Optional[str]] = mapped_column(db.String(50), nullable=True)     # 'Amazon', 'Google', etc.
    status: Mapped[str] = mapped_column(db.String(20), default='started')       # 'started', 'completed'
    created_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow)

    # Synonyms mapping database fields to requested names
    company = synonym('company_name')
    role = synonym('role_applied')
    date = synonym('created_at')

    # Progression tracking columns
    question_ids: Mapped[Optional[str]] = mapped_column(db.Text, default='[]', nullable=True) # JSON list of integers
    current_index: Mapped[int] = mapped_column(db.Integer, default=0, nullable=False)
    asked_follow_up: Mapped[bool] = mapped_column(db.Boolean, default=False, nullable=False)
    last_question_id: Mapped[Optional[int]] = mapped_column(db.Integer, nullable=True)
    last_question_text: Mapped[Optional[str]] = mapped_column(db.Text, nullable=True)
    pending_follow_up: Mapped[Optional[str]] = mapped_column(db.Text, nullable=True)

    # Extra aggregated metrics
    role_applied: Mapped[Optional[str]] = mapped_column(db.String(100), nullable=True)
    duration: Mapped[int] = mapped_column(db.Integer, default=0) # duration in seconds
    questions_asked: Mapped[Optional[str]] = mapped_column(db.Text, nullable=True) # JSON list
    user_answers: Mapped[Optional[str]] = mapped_column(db.Text, nullable=True) # JSON list
    audio_transcript: Mapped[Optional[str]] = mapped_column(db.Text, nullable=True) # combined transcript text
    eye_contact_score: Mapped[float] = mapped_column(db.Float, default=0.0) # aggregated average eye contact
    filler_word_count: Mapped[int] = mapped_column(db.Integer, default=0) # aggregated total filler count
    improvement_areas: Mapped[Optional[str]] = mapped_column(db.Text, nullable=True)

    # Aggregate Scores (out of 100)
    communication_score: Mapped[float] = mapped_column(db.Float, default=0.0)
    technical_score: Mapped[float] = mapped_column(db.Float, default=0.0)
    answer_quality_score: Mapped[float] = mapped_column(db.Float, default=0.0)
    professionalism_score: Mapped[float] = mapped_column(db.Float, default=0.0)
    confidence_score: Mapped[float] = mapped_column(db.Float, default=0.0)        # Based on Eye Contact and Speech Fluency
    overall_score: Mapped[float] = mapped_column(db.Float, default=0.0)           # Weighted average of above

    # Textual Summaries
    feedback_summary: Mapped[Optional[str]] = mapped_column(db.Text, nullable=True)
    recommendations: Mapped[Optional[str]] = mapped_column(db.Text, nullable=True)        # Actionable items
    experiment_mode: Mapped[str] = mapped_column(db.String(50), default='fixed')           # 'fixed', 'adaptive_rule', 'adaptive_gpt', etc.
    decision_log: Mapped[Optional[str]] = mapped_column(db.Text, default='[]')             # JSON representation of next-question choices
    competency_map: Mapped[Optional[str]] = mapped_column(db.Text, default='{}')           # JSON representation of Knows/Weak/Unknown skills


    # Relationships
    responses: Mapped[List["Response"]] = relationship('Response', backref='session', lazy='dynamic', cascade="all, delete-orphan")

    def get_decision_log(self):
        try:
            return json.loads(self.decision_log or '[]')
        except Exception:
            return []

    def get_competency_map(self):
        try:
            return json.loads(self.competency_map or '{}')
        except Exception:
            return {}

    def __repr__(self):
        return f'<InterviewSession {self.id}: {self.interview_type} (User: {self.user_id}) - Score: {self.overall_score}>'