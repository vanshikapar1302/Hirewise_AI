from datetime import datetime
from database.connection import db

class EmailLog(db.Model):
    __tablename__ = 'email_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    email = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(256), nullable=False)
    event_type = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(100), nullable=False)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    ip_address = db.Column(db.String(45), nullable=True)
    
    # Relationship
    user = db.relationship('User', backref=db.backref('email_logs', lazy='dynamic'))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
