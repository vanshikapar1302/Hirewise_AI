from datetime import datetime
from database.connection import db

class SystemLog(db.Model):
    __tablename__ = 'system_logs'

    id = db.Column(db.Integer, primary_key=True)
    level = db.Column(db.String(20), nullable=False, default="INFO") # 'INFO', 'WARNING', 'ERROR'
    message = db.Column(db.Text, nullable=False)
    module = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __repr__(self):
        return f'<SystemLog [{self.level}] {self.message[:30]}...>'
