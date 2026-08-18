from datetime import datetime
from database.connection import db

class AdminUser(db.Model):
    __tablename__ = 'admin_users'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    department = db.Column(db.String(100), nullable=True, default="Management")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship
    user = db.relationship('User', backref=db.backref('admin_profile', uselist=False, cascade="all, delete-orphan"))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __repr__(self):
        return f'<AdminUser id={self.id} user_id={self.user_id}>'
