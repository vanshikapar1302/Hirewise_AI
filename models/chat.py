from datetime import datetime
from sqlalchemy.orm import synonym
from database.connection import db

class ChatSession(db.Model):
    __tablename__ = 'chat_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    title = db.Column(db.String(150), default="New Chat Session")
    mode = db.Column(db.String(50), default="chat") # 'chat', 'practice_hr', 'practice_tech', 'practice_behav', 'practice_company', 'learning'
    num_messages = db.Column(db.Integer, default=0, nullable=False)
    duration = db.Column(db.Integer, default=0, nullable=False) # stored in seconds
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='chat_sessions', lazy=True)
    messages = db.relationship('ChatMessage', backref='session', lazy='dynamic', cascade="all, delete-orphan")
    practice_records = db.relationship('PracticeHistory', backref='session', lazy='dynamic', cascade="all, delete-orphan")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('chat_sessions.id', ondelete='CASCADE'), nullable=False)
    sender = db.Column(db.String(10), nullable=False) # 'user' or 'ai'
    content = db.Column(db.Text, nullable=False)
    is_audio = db.Column(db.Boolean, default=False)
    audio_path = db.Column(db.String(256), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Extended columns for memory
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=True)
    message_role = db.Column(db.String(50), nullable=True)
    message_content = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    # Synonyms for database specifications
    role = synonym('message_role')
    message = synonym('message_content')

    def __init__(self, **kwargs):
        # Sync sender and message_role
        if 'sender' in kwargs and 'message_role' not in kwargs:
            kwargs['message_role'] = 'user' if kwargs['sender'] == 'user' else 'assistant'
        elif 'message_role' in kwargs and 'sender' not in kwargs:
            kwargs['sender'] = 'user' if kwargs['message_role'] in ('user', 'candidate') else 'ai'
            
        # Sync content and message_content
        if 'content' in kwargs and 'message_content' not in kwargs:
            kwargs['message_content'] = kwargs['content']
        elif 'message_content' in kwargs and 'content' not in kwargs:
            kwargs['content'] = kwargs['message_content']
            
        # Sync created_at and timestamp
        if 'created_at' in kwargs and 'timestamp' not in kwargs:
            kwargs['timestamp'] = kwargs['created_at']
        elif 'timestamp' in kwargs and 'created_at' not in kwargs:
            kwargs['created_at'] = kwargs['timestamp']
            
        # Resolve user_id if session_id is provided but user_id is missing
        if 'user_id' not in kwargs and 'session_id' in kwargs and kwargs['session_id']:
            try:
                from flask import has_request_context
                from flask_login import current_user
                if has_request_context() and current_user and current_user.is_authenticated:
                    kwargs['user_id'] = current_user.id
                else:
                    from models.chat import ChatSession
                    sess = ChatSession.query.get(kwargs['session_id'])
                    if sess:
                        kwargs['user_id'] = sess.user_id
            except Exception:
                pass
                
        super().__init__(**kwargs)


class PracticeHistory(db.Model):
    __tablename__ = 'practice_history'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey('chat_sessions.id', ondelete='CASCADE'), nullable=False)
    topic = db.Column(db.String(100), nullable=True)
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=False)
    feedback = db.Column(db.Text, nullable=True)
    score = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

