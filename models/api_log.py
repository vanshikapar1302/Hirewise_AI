from datetime import datetime
from database.connection import db

class APILog(db.Model):
    __tablename__ = 'api_logs'

    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(50), nullable=False) # 'Gemini', 'Claude', 'Local'
    endpoint = db.Column(db.String(256), nullable=True)
    request_payload = db.Column(db.Text, nullable=True)
    response_payload = db.Column(db.Text, nullable=True)
    status_code = db.Column(db.Integer, nullable=True)
    response_time = db.Column(db.Float, default=0.0) # in seconds
    is_success = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __repr__(self):
        return f'<APILog provider={self.provider} success={self.is_success} latency={self.response_time}s>'
