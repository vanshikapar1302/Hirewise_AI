import json
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column
from database.connection import db

class Response(db.Model):
    __tablename__ = 'responses'

    id: Mapped[int] = mapped_column(db.Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey('interview_sessions.id', ondelete='CASCADE'), nullable=False)
    question_id: Mapped[Optional[int]] = mapped_column(db.Integer, db.ForeignKey('questions.id', ondelete='SET NULL'), nullable=True)
    question_text: Mapped[str] = mapped_column(db.Text, nullable=False)

    # Media paths
    audio_path: Mapped[Optional[str]] = mapped_column(db.String(256), nullable=True)
    video_path: Mapped[Optional[str]] = mapped_column(db.String(256), nullable=True)

    # NLP & Speech Stats
    transcript: Mapped[Optional[str]] = mapped_column(db.Text, nullable=True)
    filler_count: Mapped[int] = mapped_column(db.Integer, default=0)
    filler_words_json: Mapped[str] = mapped_column(db.Text, default='{}')     # JSON representing specific counts (e.g. {"like": 2, "uh": 1})
    wpm: Mapped[int] = mapped_column(db.Integer, default=0)
    duration: Mapped[float] = mapped_column(db.Float, default=0.0)             # response duration in seconds

    # Computer Vision Stats
    eye_contact_score: Mapped[float] = mapped_column(db.Float, default=0.0)    # Eye contact consistency percentage (0-100)
    head_stability_score: Mapped[float] = mapped_column(db.Float, default=0.0)  # Head stability variance-based score
    attention_duration_score: Mapped[float] = mapped_column(db.Float, default=0.0) # Longest segment of continuous focus
    confidence_score: Mapped[float] = mapped_column(db.Float, default=0.0)     # Combined eye_contact, stability, duration score

    # AI Evaluation (out of 10)
    relevance_score: Mapped[float] = mapped_column(db.Float, default=0.0)
    clarity_score: Mapped[float] = mapped_column(db.Float, default=0.0)
    completeness_score: Mapped[float] = mapped_column(db.Float, default=0.0)
    structure_score: Mapped[float] = mapped_column(db.Float, default=0.0)
    professionalism_score: Mapped[float] = mapped_column(db.Float, default=0.0)
    correctness_score: Mapped[float] = mapped_column(db.Float, default=0.0)
    depth_score: Mapped[float] = mapped_column(db.Float, default=0.0)
    communication_quality_score: Mapped[float] = mapped_column(db.Float, default=0.0)
    answer_score: Mapped[float] = mapped_column(db.Float, default=0.0)                  # Overall computed score (0-100)


    feedback: Mapped[Optional[str]] = mapped_column(db.Text, nullable=True)
    follow_up_question: Mapped[Optional[str]] = mapped_column(db.Text, nullable=True)   # Next follow-up question suggested by AI
    created_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow)

    def get_filler_words(self):
        try:
            return json.loads(self.filler_words_json)
        except Exception:
            return {}

    def set_filler_words(self, words_dict):
        self.filler_words_json = json.dumps(words_dict)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __repr__(self):
        return f'<Response {self.id} for Session {self.session_id}>'

