import os
import sys
from pathlib import Path

# Setup paths
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

from app import app
from database.connection import db
from models.user import User
from models.chat import ChatSession, ChatMessage
from services.mentor_service import MentorService

def run_tests():
    print("=" * 70)
    print("           HIREWISE MENTOR - CHATGPT-LIKE CONVERSATIONAL TESTS       ")
    print("=" * 70)
    
    with app.app_context():
        # 1. Fetch or create a test user
        test_user = User.query.filter_by(username="test_candidate").first()
        if not test_user:
            test_user = User(
                username="test_candidate",
                email="test_candidate@hirewise.ai",
                full_name="Alex Candidate",
                skill_level="Beginner"
            )
            test_user.set_password("SecureTestPass123!")
            db.session.add(test_user)
            db.session.commit()
            
        # 2. Create a clean ChatSession
        session = ChatSession(
            user_id=test_user.id,
            mode="chat",
            title="ChatGPT Behavior Test"
        )
        db.session.add(session)
        db.session.commit()
        
        mentor_service = MentorService()
        
        # Test Cases
        queries = [
            ("What is array?", ["Definition", "Syntax", "Example", "Complexity", "Applications"]),
            ("Interview questions on arrays", ["questions", "interview"]),
            ("I know Java and Flask.", ["Java", "Flask", "Profile"]),
            ("What should I learn next?", ["learn", "next", "context"]),
            ("Explain binary search.", ["binary search", "Complexity", "Search"])
        ]
        
        history = []
        
        for idx, (query, expected_keywords) in enumerate(queries):
            print(f"\n--- Turn {idx + 1}: Query: '{query}' ---")
            
            # Save User Message
            user_msg = ChatMessage(
                session_id=session.id,
                sender="user",
                content=query,
                user_id=test_user.id
            )
            db.session.add(user_msg)
            db.session.commit()
            
            # Re-fetch full history to pass to service
            db_messages = ChatMessage.query.filter_by(session_id=session.id).order_by(ChatMessage.created_at.asc()).all()
            history_payload = [{"sender": m.sender, "content": m.content} for m in db_messages]
            
            # Generate AI response
            reply, provider, suggestions = mentor_service.generate_response(session.mode, history_payload)
            
            print(f"Active Provider: {provider.upper()}")
            print(f"Suggestions: {suggestions}")
            print(f"Response:\n{reply[:400]}...")
            
            # Save AI Response
            ai_msg = ChatMessage(
                session_id=session.id,
                sender="ai",
                content=reply,
                user_id=test_user.id
            )
            db.session.add(ai_msg)
            db.session.commit()
            
            # Verification check
            found_keywords = [k for k in expected_keywords if k.lower() in reply.lower()]
            print(f"Verification Check: Found keywords {found_keywords} of expected {expected_keywords}")

        # Clean up session
        db.session.delete(session)
        db.session.commit()
        print("\n" + "=" * 70)
        print("                 CONVERSATIONAL TEST SEQUENCE COMPLETED              ")
        print("=" * 70)

if __name__ == "__main__":
    run_tests()
