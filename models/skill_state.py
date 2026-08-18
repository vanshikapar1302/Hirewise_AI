from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from database.connection import db

class SessionSkillState(db.Model):
    __tablename__ = 'session_skill_states'

    id: Mapped[int] = mapped_column(db.Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey('interview_sessions.id', ondelete='CASCADE'), nullable=False)
    skill_name: Mapped[str] = mapped_column(db.String(50), nullable=False)
    score: Mapped[float] = mapped_column(db.Float, default=50.0)
    level: Mapped[str] = mapped_column(db.String(20), default='Beginner') # 'Beginner', 'Intermediate', 'Advanced'
    updated_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __repr__(self):
        return f'<SessionSkillState {self.skill_name}: {self.score:.1f} ({self.level})>'


class SessionSkillHistory(db.Model):
    __tablename__ = 'session_skill_history'

    id: Mapped[int] = mapped_column(db.Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey('interview_sessions.id', ondelete='CASCADE'), nullable=False)
    skill_name: Mapped[str] = mapped_column(db.String(50), nullable=False)
    previous_score: Mapped[float] = mapped_column(db.Float, default=50.0)
    updated_score: Mapped[float] = mapped_column(db.Float, default=50.0)
    timestamp: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __repr__(self):
        return f'<SessionSkillHistory {self.skill_name}: {self.previous_score:.1f} -> {self.updated_score:.1f}>'
