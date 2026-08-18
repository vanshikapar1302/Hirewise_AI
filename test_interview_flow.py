import io
import os
import json
from app import app
from database.connection import db
from models.user import User
from models.question import Question
from models.interview import InterviewSession

def run_test():
    print("=" * 60)
    print("      HireWise AI - End-to-End Interview Flow Test      ")
    print("=" * 60)
    
    # 1. Setup client
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    client = app.test_client()
    
    with app.app_context():
        # Ensure database tables exist
        db.create_all()
        
        # 2. Check or create dummy user
        user = User.query.filter_by(username="test_student").first()
        if not user:
            user = User(username="test_student", email="test@student.edu")
            user.set_password("password123")
            db.session.add(user)
            db.session.commit()
            print("[ INFO ] Created test user: test_student")
        else:
            print("[ INFO ] Using existing test user.")
            
        # Ensure we have at least one HR question seeded
        q = Question.query.filter_by(category="HR").first()
        if not q:
            q = Question(
                text="Tell me about a project you are proud of.",
                category="HR",
                difficulty="Easy",
                expected_keywords=json.dumps(["project", "challenges", "skills"])
            )
            db.session.add(q)
            db.session.commit()
            print("[ INFO ] Seeded fallback HR question.")
            
    # 3. Perform login session
    print("\n--- Step 1: Simulating Log In ---")
    login_response = client.post('/login', data={
        "email_or_username": "test_student",
        "password": "password123"
    }, follow_redirects=True)
    
    if login_response.status_code == 200:
        print("[ SUCCESS ] Login successful.")
    else:
        print(f"[ FAILED ] Login status: {login_response.status_code}")
        return
        
    # 4. Start Mock Session
    print("\n--- Step 2: Starting HR Mock Session ---")
    select_response = client.post('/interview/select', data={
        "interview_type": "HR",
        "company_name": ""
    }, follow_redirects=True)
    
    # Check session parameters from database
    with app.app_context():
        db_user = User.query.filter_by(username="test_student").first()
        active_sess = InterviewSession.query.filter_by(user_id=db_user.id, status='started').order_by(InterviewSession.created_at.desc()).first()
        if active_sess:
            sess_id = active_sess.id
            q_ids = json.loads(active_sess.question_ids or '[]')
        else:
            sess_id = None
            q_ids = []
        
    if sess_id:
        print(f"[ SUCCESS ] Created Session ID: {sess_id} containing {len(q_ids)} questions in database.")
    else:
        print("[ FAILED ] Session not found in database.")
        print(select_response.data.decode('utf-8')[:500])
        return
        
    # 5. Submit Simulated Answer to /interview/submit_answer
    print("\n--- Step 3: Posting Simulated Answer for Analysis ---")
    
    # Build fake audio and video binaries (empty bytes representing recorded streams)
    fake_audio = (io.BytesIO(b"RIFF....WAVEfmt ....data...."), "test_audio.webm")
    fake_video = (io.BytesIO(b"....webm....video....data"), "test_video.webm")
    
    data = {
        "session_id": sess_id,
        "duration": "12.5",
        "browser_transcript": "I built a web dashboard utilizing python and SQLite to prepare engineering students for placements.",
        "is_follow_up": "false",
        "question_text": "Tell me about a project you are proud of.",
        "audio": fake_audio,
        "video": fake_video
    }
    
    try:
        response = client.post(
            '/interview/submit_answer',
            data=data,
            content_type='multipart/form-data'
        )
        
        print(f"Server Status Code: {response.status_code}")
        print("Response Payload:")
        resp_json = response.get_json()
        print(json.dumps(resp_json, indent=2))
        
        if resp_json and resp_json.get("success"):
            print("\n[ SUCCESS ] END-TO-END INTERVIEW FLOW IS FULLY OPERATIONAL.")
        else:
            print("\n[ ERROR ] Server returned analysis failure. Inspect logs.")
            
    except Exception as e:
        print(f"\n[ CRITICAL ] Exception during client post: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    run_test()
