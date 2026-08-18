import os
from pathlib import Path
base_dir = Path(__file__).resolve().parent

# Read DATABASE_URL from .env
env_path = base_dir / ".env"
db_uri = None
if env_path.exists():
    with open(env_path, 'r') as f:
        for line in f:
            if line.startswith("DATABASE_URL="):
                db_uri = line.split("DATABASE_URL=")[1].strip()
                break
if not db_uri:
    db_uri = os.environ.get("DATABASE_URL")
if not db_uri:
    raise ValueError("[ERROR] DATABASE_URL is missing. SQLite fallback is disabled by configuration rules.")
if db_uri.startswith("postgres://"):
    db_uri = db_uri.replace("postgres://", "postgresql://", 1)

os.environ["DATABASE_URL"] = db_uri

import io
import json
from app import app
from database.connection import db
from models.user import User
from models.question import Question
from models.interview import InterviewSession
from models.response import Response
from models.skill_state import SessionSkillState, SessionSkillHistory

def run_test():
    print("=" * 70)
    print("      HireWise AI - Adaptive Interview & Research Flow Test      ")
    print("=" * 70)
    
    masked_uri = db_uri.split("@")[-1] if "@" in db_uri else db_uri
    print(f"[INFO] Running flow test against Supabase PostgreSQL: postgresql://*****@{masked_uri}")
    
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
        user_id = user.id
        
        # Seed mock resume with explicit claims to test Resume Inflation Score
        from models.resume_upload import ResumeUpload
        ResumeUpload.query.filter_by(user_id=user_id).delete()
        resume = ResumeUpload(
            user_id=user_id,
            filename="cv.pdf",
            file_path="uploads/cv.pdf",
            skills_extracted="Python - Expert, DSA - Intermediate, DBMS - Beginner",
            parsed_text="Highly proficient in python scripting and data structures.",
            ats_score=80
        )
        db.session.add(resume)
        db.session.commit()
        print("[ INFO ] Seeded mock resume with explicit claims for test_student.")
            
        # Ensure we have some base questions seeded for Python, DSA, DBMS
        # If not, preload_questions runs on startup, but let's make sure
        python_q = Question.query.filter_by(skill="Python").first()
        if not python_q:
            # Seed basic questions
            db.session.add(Question(text="Mutable vs Immutable objects in Python?", category="Technical", difficulty="Medium", skill="Python", subtopic="Data Types", expected_keywords='["mutable","immutable","list","tuple"]'))
            db.session.add(Question(text="List comprehensions in Python?", category="Technical", difficulty="Easy", skill="Python", subtopic="Lists", expected_keywords='["list","comprehension","syntax"]'))
            db.session.add(Question(text="What is the Python GIL?", category="Technical", difficulty="Hard", skill="Python", subtopic="Concurrency", expected_keywords='["gil","lock","thread"]'))
            db.session.add(Question(text="What is a Stack vs Queue?", category="Technical", difficulty="Easy", skill="DSA", subtopic="Basic Data Structures", expected_keywords='["stack","queue","lifo","fifo"]'))
            db.session.add(Question(text="Explain Quicksort?", category="Technical", difficulty="Medium", skill="DSA", subtopic="Sorting", expected_keywords='["quicksort","pivot","partition"]'))
            db.session.add(Question(text="Explain Dynamic Programming?", category="Technical", difficulty="Hard", skill="DSA", subtopic="Dynamic Programming", expected_keywords='["dynamic","programming","memoization"]'))
            db.session.add(Question(text="Primary key vs Unique key?", category="Technical", difficulty="Easy", skill="DBMS", subtopic="Keys", expected_keywords='["primary","unique","key"]'))
            db.session.add(Question(text="What is database Indexing?", category="Technical", difficulty="Medium", skill="DBMS", subtopic="Indexing", expected_keywords='["index","indexing","btree"]'))
            db.session.add(Question(text="What are database ACID properties?", category="Technical", difficulty="Hard", skill="DBMS", subtopic="Transactions", expected_keywords='["acid","atomicity","consistency"]'))
            db.session.commit()
            print("[ INFO ] Seeded fallback research-grade questions.")
        else:
            print("[ INFO ] Standard structured questions already present in database.")

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
        
    # 4. Start Mock Adaptive Session
    print("\n--- Step 2: Launching Rule-Based Adaptive Session ---")
    select_response = client.post('/interview/select', data={
        "interview_type": "Technical",
        "experiment_mode": "adaptive_rule",
        "company_name": "",
        "role_applied": "Software Engineer"
    }, follow_redirects=True)
    
    # Check session parameters from database
    with app.app_context():
        active_sess = InterviewSession.query.filter_by(user_id=user_id, status='started', experiment_mode='adaptive_rule').order_by(InterviewSession.created_at.desc()).first()
        if active_sess:
            sess_id = active_sess.id
            q_ids = json.loads(active_sess.question_ids or '[]')
        else:
            sess_id = None
            q_ids = []
        
    if sess_id:
        print(f"[ SUCCESS ] Created Session ID: {sess_id}")
        print(f"[ INFO ] Initial Question ID seeded: {q_ids}")
    else:
        print("[ FAILED ] Session not found in database.")
        return

    # 5. Run the adaptive submissions loop (simulate 5 responses)
    # We will alternate answers: high quality vs low quality to watch difficulty scale
    transcripts = [
        "Python lists are mutable meaning their elements can be modified, whereas tuples are immutable and their values cannot be changed after creation.", # High Python response -> expect DSA Medium/Hard next
        "I do not know much about stacks and queues, they are some data structures.", # Low DSA response -> expect DBMS Easy/Medium next
        "A primary key uniquely identifies each record in a database table and cannot contain nulls. A unique key also prevents duplicates but allows a single null.", # High DBMS response -> expect Python Medium/Hard next
        "GIL stands for Global Interpreter Lock which allows only one thread to control CPython execution, preventing multiple threads from executing python code in parallel.", # High Python response -> expect DSA Hard next
        "Dynamic programming solves complex problems by breaking them down into simpler overlapping subproblems and caching the results with memoization." # High DSA response -> finished
    ]
    
    # Build fake audio and video binaries
    fake_audio = (io.BytesIO(b"RIFF....WAVEfmt ....data...."), "test_audio.webm")
    fake_video = (io.BytesIO(b"....webm....video....data"), "test_video.webm")

    print("\n--- Step 3: Simulating Multi-Turn Adaptive Questioning Loop ---")
    for turn in range(5):
        # Retrieve the current question text from database
        with app.app_context():
            s = InterviewSession.query.get(sess_id)
            current_q_id = json.loads(s.question_ids)[s.current_index]
            q_obj = Question.query.get(current_q_id)
            q_text = q_obj.text
            q_skill = q_obj.skill
            q_diff = q_obj.difficulty
            
        print(f"\n[ TURN {turn+1} ] Assessing Skill: {q_skill} | Difficulty: {q_diff}")
        print(f"Question: \"{q_text}\"")
        
        # Post the answer
        fake_audio = (io.BytesIO(b"RIFF....WAVEfmt ....data...."), "test_audio.webm")
        fake_video = (io.BytesIO(b"....webm....video....data"), "test_video.webm")
        
        data = {
            "session_id": sess_id,
            "duration": "15.0",
            "browser_transcript": transcripts[turn],
            "is_follow_up": "false",
            "question_text": q_text,
            "audio": fake_audio,
            "video": fake_video
        }
        
        resp = client.post('/interview/submit_answer', data=data, content_type='multipart/form-data')
        resp_json = resp.get_json()
        
        if not resp_json or not resp_json.get("success"):
            print(f"[ FAILED ] Submission on turn {turn+1} failed.")
            print(resp.data.decode('utf-8')[:500])
            return
            
        # Inspect updated skill states
        with app.app_context():
            s = db.session.get(InterviewSession, sess_id)
            all_states = SessionSkillState.query.filter_by(session_id=sess_id).all()
            print(f"Current Skill States: { {st.skill_name: st.score for st in all_states} }")
            
            # Print decision log reason
            dec_log = json.loads(s.decision_log or '[]')
            if len(dec_log) > turn:
                print(f"Orchestrator Decision: {dec_log[-1]['reason']}")
                
    # 6. Finalize the session
    print("\n--- Step 4: Finalizing Session and Generating Reports ---")
    fin_resp = client.get(f'/interview/finalize/{sess_id}', follow_redirects=True)
    if fin_resp.status_code == 200:
        print("[ SUCCESS ] Session finalized successfully.")
        
        # Verify scores and competency maps in database
        with app.app_context():
            final_sess = db.session.get(InterviewSession, sess_id)
            print(f"Final Scores:")
            print(f"- Overall Score: {final_sess.overall_score}%")
            print(f"- Technical Score: {final_sess.technical_score}%")
            print(f"- Communication Score: {final_sess.communication_score}%")
            print(f"- Confidence Score: {final_sess.confidence_score}%")
            print("\nFinal Competency Boundary Map:")
            comp_map = json.loads(final_sess.competency_map or '{}')
            print(json.dumps(comp_map, indent=2))
    else:
        print(f"[ FAILED ] Finalization status: {fin_resp.status_code}")
        return

    # 7. Test Export of Research Dataset CSV
    print("\n--- Step 5: Testing Research CSV Dataset Export ---")
    # Must log in as admin user to query export
    # Seed default admin user if not present (already handled by init_db, let's login admin)
    with app.app_context():
        admin = User.query.filter_by(username="admin").first()
        if not admin:
            admin_role = db.session.query(db.func.min(Role.id)).scalar()
            admin = User(username="admin", email="admin@hirewise.ai", role_id=admin_role)
            admin.set_password("AdminPassword123")
            db.session.add(admin)
            db.session.commit()
            
    client.post('/admin/login', data={
        "email_or_username": "admin",
        "password": "AdminPassword123"
    }, follow_redirects=True)
    
    csv_resp = client.get('/admin/reports/export/research_experiment')
    if csv_resp.status_code == 200 and csv_resp.headers.get('Content-Type') == 'text/csv':
        print("[ SUCCESS ] Successfully exported research CSV dataset.")
        print(f"CSV Size: {len(csv_resp.data)} bytes")
        # Print a snippet of CSV data
        print("CSV Header Snippet:")
        print(csv_resp.data.decode('utf-8').split('\n')[0])
        print(csv_resp.data.decode('utf-8').split('\n')[1][:150] + "...")
        print("\n" + "=" * 70)
        print("      ADAPTIVE QUESTIONING PIPELINE INTEGRATED SUCCESSFULLY!      ")
        print("=" * 70)
    else:
        print(f"[ FAILED ] Export research CSV dataset status: {csv_resp.status_code}")
        return

if __name__ == '__main__':
    run_test()
