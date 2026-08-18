import io
import os
import json
from app import app
from database.connection import db
from models.user import User
from models.question import Question
from models.interview import InterviewSession

def run_project_test():
    print("=" * 60)
    print("    HireWise AI - Project Interview Flow Test    ")
    print("=" * 60)
    
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    client = app.test_client()
    
    with app.app_context():
        # Ensure test database setup is verified
        db.create_all()
        
        # Ensure test user exists
        user = User.query.filter_by(username="test_student").first()
        if not user:
            user = User(username="test_student", email="test@student.edu")
            user.set_password("password123")
            db.session.add(user)
            db.session.commit()
            print("[ INFO ] Created test user: test_student")
        else:
            print("[ INFO ] Using existing test user.")

    # 1. Login user
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

    # 2. Start Project Mock Session
    print("\n--- Step 2: Starting Project Interview Mode ---")
    select_data = {
        "interview_type": "Project",
        "project_input_option": "manual",
        "project_title": "Distributed Task Scheduler",
        "project_description": "A high-performance concurrent system to queue and schedule recurring jobs with fallback retries.",
        "project_technologies": "Go, Redis, PostgreSQL, Docker, gRPC",
        "project_features": "Distributed locking, exponential backoff retries, dashboard monitoring",
        "project_contribution": "Designed the distributed lock module and gRPC interface",
        "project_challenges": "Handling lock expiry during network partitions and database transaction deadlocks",
        "role_applied": "Backend Engineer",
        "experiment_mode": "adaptive_gemini"
    }
    
    select_response = client.post('/interview/select', data=select_data, follow_redirects=True)
    
    with app.app_context():
        db_user = User.query.filter_by(username="test_student").first()
        active_sess = InterviewSession.query.filter_by(
            user_id=db_user.id, 
            interview_type='Project',
            status='started'
        ).order_by(InterviewSession.created_at.desc()).first()
        
        if active_sess:
            sess_id = active_sess.id
            comp_map = json.loads(active_sess.competency_map or '{}')
            project_all_ids = comp_map.get("project_all_question_ids", [])
            q_ids = json.loads(active_sess.question_ids or '[]')
            print(f"[ SUCCESS ] Created Session ID: {sess_id}")
            print(f"  - Total project questions generated: {len(project_all_ids)}")
            print(f"  - Currently queued questions in session: {len(q_ids)}")
            
            # Verify understanding format
            understanding = comp_map.get("project_understanding", {})
            print(f"  - Generated project title: {understanding.get('project_title')}")
            print(f"  - Generated project domain: {understanding.get('domain')}")
        else:
            print("[ FAILED ] Project session not created in database.")
            sess_id = None

    if not sess_id:
        return

    # 3. Submit Simulated Answer to /interview/submit_answer
    print("\n--- Step 3: Posting Simulated Answer for First Question ---")
    
    # Load first question text
    with app.app_context():
        active_sess = db.session.get(InterviewSession, sess_id)
        q_text = active_sess.last_question_text
        print(f"  - First Question text: \"{q_text}\"")

    fake_audio = (io.BytesIO(b"RIFF....WAVEfmt ....data...."), "test_audio.webm")
    fake_video = (io.BytesIO(b"....webm....video....data"), "test_video.webm")
    
    data = {
        "session_id": sess_id,
        "duration": "15.2",
        "browser_transcript": "For distributed task scheduling, we implemented distributed locks utilizing Redis SETNX commands. This guarantees that only one node processes a given task at any time.",
        "is_follow_up": "false",
        "question_text": q_text,
        "audio": fake_audio,
        "video": fake_video
    }
    
    response = client.post(
        '/interview/submit_answer',
        data=data,
        content_type='multipart/form-data'
    )
    
    print(f"Server Status Code: {response.status_code}")
    resp_json = response.get_json()
    if resp_json and resp_json.get("success"):
        print("[ SUCCESS ] Response grade calculated successfully.")
        print(f"  - Next Question text: \"{resp_json.get('next_question_text')}\"")
        print(f"  - Completion percentage: {resp_json.get('completion_percentage')}%")
    else:
        print("[ ERROR ] submit_answer failed.")
        print(json.dumps(resp_json, indent=2))
        return

    # 4. Finalize Session
    print("\n--- Step 4: Finalizing Interview and Generating Feedback ---")
    finalize_response = client.get(f'/interview/finalize/{sess_id}', follow_redirects=True)
    
    with app.app_context():
        final_sess = db.session.get(InterviewSession, sess_id)
        comp_map = json.loads(final_sess.competency_map or '{}')
        proj_feedback = comp_map.get("project_feedback", {})
        
        print(f"  - Session status: {final_sess.status}")
        print(f"  - Overall Score: {final_sess.overall_score}%")
        print(f"  - Communication Score: {final_sess.communication_score}%")
        print(f"  - Technical Score: {final_sess.technical_score}%")
        print(f"  - Project presentation strengths found: {len(proj_feedback.get('strengths', []))}")
        print(f"  - Project presentation weaknesses found: {len(proj_feedback.get('weaknesses', []))}")
        
        if final_sess.status == 'completed' and proj_feedback.get("scores"):
            print("\n[ SUCCESS ] END-TO-END PROJECT INTERVIEW FLOW IS FULLY OPERATIONAL.")
        else:
            print("\n[ ERROR ] Scorecard or project feedback not generated correctly.")

if __name__ == '__main__':
    run_project_test()
