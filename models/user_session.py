from datetime import datetime
from database.connection import db

class UserSession(db.Model):
    __tablename__ = 'user_sessions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    login_time = db.Column(db.DateTime, default=datetime.utcnow)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(256), nullable=True)
    logout_time = db.Column(db.DateTime, nullable=True)

    # Relationship
    user = db.relationship('User', backref=db.backref('sessions', lazy='dynamic', cascade="all, delete-orphan"))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __repr__(self):
        return f'<UserSession id={self.id} user_id={self.user_id} login_time={self.login_time}>'
