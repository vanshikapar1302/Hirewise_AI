import json
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column
from database.connection import db

class Question(db.Model):
    __tablename__ = 'questions'

    id: Mapped[int] = mapped_column(db.Integer, primary_key=True)
    text: Mapped[str] = mapped_column(db.Text, nullable=False)
    category: Mapped[str] = mapped_column(db.String(50), nullable=False)  # 'HR', 'Technical', 'Behavioral', 'Company', 'Resume'
    company: Mapped[Optional[str]] = mapped_column(db.String(50), nullable=True)     # 'Amazon', 'Google', 'Microsoft', 'TCS', 'Infosys'
    difficulty: Mapped[str] = mapped_column(db.String(20), default='Medium') # 'Easy', 'Medium', 'Hard'
    expected_keywords: Mapped[str] = mapped_column(db.Text, default='[]')   # JSON array of expected keywords
    skill: Mapped[Optional[str]] = mapped_column(db.String(50), nullable=True)  # 'Python', 'DSA', 'DBMS', etc.
    subtopic: Mapped[Optional[str]] = mapped_column(db.String(50), nullable=True) # 'Loops', 'Trees', 'Joins'
    prerequisite_skills: Mapped[str] = mapped_column(db.Text, default='[]')   # JSON array of prerequisite skill requirements


    def get_keywords(self):
        try:
            return json.loads(self.expected_keywords)
        except Exception:
            return []

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __repr__(self):
        return f'<Question {self.id}: {self.category} - {self.text[:30]}...>'

