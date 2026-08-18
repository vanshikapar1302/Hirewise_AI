import sys
import os
import json
from pathlib import Path

# Fix relative import paths
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

def print_result(check_name, pass_status, details=""):
    status_label = "[ PASS ]" if pass_status else "[ FAIL ]"
    print(f"{status_label} {check_name:<40}: {details}")

def run_verification():
    print("=" * 70)
    print("              HIREWISE AI - PLATFORM DIAGNOSTICS              ")
    print("=" * 70)
    
    overall_pass = True

    # 1. Check Python Dependencies
    print("\n--- Diagnostic Phase 1: Checking Python Packages ---")
    dependencies = {
        "Flask Framework": "flask",
        "Flask-Login Manager": "flask_login",
        "Flask-SQLAlchemy ORM": "flask_sqlalchemy",
        "Scikit-learn Analytics": "sklearn",
        "Pandas Dataframe": "pandas",
        "NumPy Numerical Library": "numpy",
        "Dotenv Config Loader": "dotenv",
        "PyPDF2 Document Parser": "PyPDF2"
    }
    
    for label, import_name in dependencies.items():
        try:
            __import__(import_name)
            print_result(label, True, "Successfully imported.")
        except ImportError as e:
            print_result(label, False, f"Missing critical module: {e}")
            overall_pass = False

    # Check non-critical libraries with fallbacks
    optional_deps = {
        "OpenCV Computer Vision": "cv2",
        "MediaPipe Mesh Tracker": "mediapipe",
        "SpeechRecognition Online API": "speech_recognition",
        "Pydub Audio Library": "pydub",
        "OpenAI Whisper Transcriber": "whisper"
    }
    
    for label, import_name in optional_deps.items():
        try:
            __import__(import_name)
            print_result(f"{label} (Optional)", True, "Imported successfully.")
        except ImportError:
            print_result(f"{label} (Optional)", True, "Missing. Fallback mode will be utilized.")

    # 2. Check Flask App and Configurations
    print("\n--- Diagnostic Phase 2: Instantiating Flask Application Context ---")
    try:
        from app import app
        from config import Config
        print_result("Flask Config Loader", True, "Successfully loaded app configurations.")
        
        blueprints = list(app.blueprints.keys())
        print_result("App Blueprints", True, f"Registered blueprints: {', '.join(blueprints)}")
    except Exception as e:
        print_result("Flask Instantiation", False, f"Failed to load application context: {e}")
        overall_pass = False
        return False

    # 3. Check Database Connection & Table Schema
    print("\n--- Diagnostic Phase 3: Validating Database Schema ---")
    with app.app_context():
        try:
            from database.connection import db
            db.engine.connect()
            print_result("Database Connection", True, "Accessed database engine successfully.")
            
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            expected_tables = ["users", "questions", "interview_sessions", "responses"]
            
            for table in expected_tables:
                if table in tables:
                    print_result(f"DB Table schema: {table}", True, "Found in database.")
                else:
                    print_result(f"DB Table schema: {table}", False, "Table missing.")
                    overall_pass = False
        except Exception as e:
            print_result("Database Schema Diagnostics", False, f"Failed: {e}")
            overall_pass = False

    # 4. Check Template Layout Integrity
    print("\n--- Diagnostic Phase 4: Checking Frontend Templates ---")
    templates_dir = BASE_DIR / "templates"
    required_templates = [
        "base.html", "index.html", "login.html", "register.html", 
        "dashboard.html", "profile.html", "select_interview.html", 
        "interview.html", "feedback.html", "history.html", "resume_upload.html"
    ]
    
    if templates_dir.exists():
        for temp_file in required_templates:
            temp_path = templates_dir / temp_file
            if temp_path.exists():
                print_result(f"Template Layout: {temp_file}", True, "Exists on disk.")
            else:
                print_result(f"Template Layout: {temp_file}", False, "Template file not found.")
                overall_pass = False
    else:
        print_result("Templates Folder", False, "Templates folder is missing.")
        overall_pass = False

    # 5. Check Dataset file
    print("\n--- Diagnostic Phase 5: Checking Dataset Questions Bank ---")
    datasets_file = BASE_DIR / "datasets" / "questions.json"
    if datasets_file.exists():
        try:
            with open(datasets_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            count = len(data.get("questions", []))
            print_result("Seeded Question Bank", True, f"Dataset contains {count} seeded entries.")
        except Exception as e:
            print_result("Seeded Question Bank", False, f"JSON corrupted: {e}")
            overall_pass = False
    else:
        print_result("Seeded Question Bank", False, f"questions.json missing at {datasets_file}")
        overall_pass = False

    # 6. Test Services Fallback Modules
    print("\n--- Diagnostic Phase 6: Testing Analysis Service Fallbacks ---")
    
    # 6a. Groq Fallback Check
    try:
        from services.groq_service import GroqService
        groq_instance = GroqService()
        test_eval = groq_instance.evaluate_answer(
            question="Tell me about yourself.",
            answer="I am an engineering student preparing for placements.",
            category="HR",
            expected_keywords='["student", "engineering"]'
        )
        if test_eval and "relevance" in test_eval and "feedback" in test_eval:
            details = "Runs Mock NLP fallback" if not groq_instance.initialized else "Runs Live API"
            print_result("Groq Service Fallback check", True, f"Successful. ({details})")
        else:
            print_result("Groq Service Fallback check", False, "Missing output keys.")
            overall_pass = False
    except Exception as e:
        print_result("Groq Service Fallback check", False, f"Crashed: {e}")
        overall_pass = False

    # 6b. Whisper Fallback Check
    try:
        from services.whisper_service import WhisperService
        whisper_instance = WhisperService()
        test_transcript = whisper_instance.transcribe("non_existent_audio.wav", "Web Speech API fallback text")
        if test_transcript == "Web Speech API fallback text":
            print_result("Whisper Service Fallback check", True, "Successfully returned client fallback text.")
        else:
            print_result("Whisper Service Fallback check", False, f"Returned unexpected transcript: {test_transcript}")
            overall_pass = False
    except Exception as e:
        print_result("Whisper Service Fallback check", False, f"Crashed: {e}")
        overall_pass = False

    # 6c. OpenCV Gaze Fallback Check
    try:
        from services.cv_service import CVService
        cv_instance = CVService()
        test_gaze = cv_instance.analyze_video("non_existent_video.webm")
        if isinstance(test_gaze, dict) and "eye_contact" in test_gaze and "confidence" in test_gaze:
            print_result("OpenCV Gaze Fallback check", True, f"Successfully mapped fallback scores: {test_gaze}")
        else:
            print_result("OpenCV Gaze Fallback check", False, f"Returned invalid score format: {test_gaze}")
            overall_pass = False
    except Exception as e:
        print_result("OpenCV Gaze Fallback check", False, f"Crashed: {e}")
        overall_pass = False

    # Final Evaluation Summary
    print("\n" + "=" * 70)
    if overall_pass:
        print("          VERIFICATION RESULT: PASS (All components operational)")
        print("=" * 70)
        print("You can start the server: python app.py")
        print("=" * 70)
        return True
    else:
        print("          VERIFICATION RESULT: FAIL (Missing critical components)")
        print("=" * 70)
        return False

if __name__ == '__main__':
    run_verification()
