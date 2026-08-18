import os
# Read DATABASE_URL from .env
from pathlib import Path
base_dir = Path(__file__).resolve().parent
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

import unittest
import json
from app import app
from database.connection import db
from models.user import User
from models.question import Question
from models.interview import InterviewSession
from models.response import Response
from models.resume_upload import ResumeUpload
from models.skill_state import SessionSkillState, SessionSkillHistory
from services.adaptive_engine import AdaptiveEngine, SkillGraph
import services.adaptive_engine as adaptive_engine_module

class TestAdaptiveResearch(unittest.TestCase):
    def setUp(self):
        # Configure app for testing
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
        self.app_context = app.app_context()
        self.app_context.push()
        
        # Mask and print database info
        masked_uri = db_uri.split("@")[-1] if "@" in db_uri else db_uri
        print(f"\n[INFO] Running tests against Supabase PostgreSQL: postgresql://*****@{masked_uri}")
        
        # Clean up any leftover test user or questions
        self.cleanup_db()
        
        # Seed test user
        self.user = User(username="research_tester", email="tester@hirewise.ai")
        self.user.set_password("password123")
        db.session.add(self.user)
        db.session.commit()

        # Seed standard technical questions
        db.session.add(Question(text="Lists easy question [TEST]", category="Technical", difficulty="Easy", skill="Python", subtopic="Lists"))
        db.session.add(Question(text="Lists hard question [TEST]", category="Technical", difficulty="Hard", skill="Python", subtopic="Lists"))
        db.session.add(Question(text="Sorting medium question [TEST]", category="Technical", difficulty="Medium", skill="DSA", subtopic="Sorting"))
        db.session.add(Question(text="Sorting hard question [TEST]", category="Technical", difficulty="Hard", skill="DSA", subtopic="Sorting"))
        db.session.commit()
        
        self.engine = AdaptiveEngine()

    def tearDown(self):
        self.cleanup_db()
        db.session.remove()
        self.app_context.pop()

    def cleanup_db(self):
        try:
            # Delete by username
            user = User.query.filter_by(username="research_tester").first()
            if user:
                # Delete sessions
                sessions = InterviewSession.query.filter_by(user_id=user.id).all()
                for s in sessions:
                    SessionSkillState.query.filter_by(session_id=s.id).delete()
                    SessionSkillHistory.query.filter_by(session_id=s.id).delete()
                    Response.query.filter_by(session_id=s.id).delete()
                    db.session.delete(s)
                # Delete resumes
                ResumeUpload.query.filter_by(user_id=user.id).delete()
                db.session.delete(user)
            
            # Delete questions containing [TEST]
            Question.query.filter(Question.text.like("%[TEST]%")).delete()
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"[WARNING] Cleanup database failed: {e}")

    def test_resume_aware_prior_initialization(self):
        """Verifies that starting priors are adjusted based on candidate resume content."""
        # 1. Test prior selection without resume
        session = InterviewSession(user_id=self.user.id, interview_type="Technical", status="started")
        db.session.add(session)
        db.session.commit()
        
        prior_score_no_resume, prior_unc_no_resume = self.engine.get_initial_prior_for_skill(session, "Python")
        self.assertEqual(prior_score_no_resume, 50.0)
        self.assertEqual(prior_unc_no_resume, 15.0)
        
        # 2. Test with resume upload content matching Python
        resume = ResumeUpload(
            user_id=self.user.id,
            filename="my_cv.pdf",
            file_path="uploads/resumes/my_cv.pdf",
            skills_extracted="Python, Django, Flask",
            projects="Built a web scraping pipeline in Python",
            experience="Senior Python Developer at Tech Corp",
            parsed_text="Highly proficient in python scripting and data analysis.",
            ats_score=85
        )
        db.session.add(resume)
        db.session.commit()
        
        # Prior score should scale based on skills & keywords evidence
        prior_score_with_resume, prior_unc_with_resume = self.engine.get_initial_prior_for_skill(session, "Python")
        self.assertGreater(prior_score_with_resume, 50.0)
        self.assertLess(prior_unc_with_resume, 15.0)
        print(f"[ TEST SUCCESS ] Resume-aware initialization: Prior Score = {prior_score_with_resume}, Uncertainty = {prior_unc_with_resume}")

    def test_skill_graph_propagation(self):
        """Verifies that a score update on a subtopic propagates to parents/prerequisites."""
        session = InterviewSession(user_id=self.user.id, interview_type="Technical", status="started")
        db.session.add(session)
        db.session.commit()
        
        # Initial score of subtopic 'Lists'
        lists_state = SessionSkillState(session_id=session.id, skill_name="Lists", score=50.0)
        db.session.add(lists_state)
        db.session.commit()
        
        # Propagate a positive update of +20.0 to 'Lists'
        self.engine.propagate_skill_graph_updates(session.id, "Lists", 20.0)
        
        # Verify parent node 'Python' is created and updated
        python_state = SessionSkillState.query.filter_by(session_id=session.id, skill_name="Python").first()
        self.assertIsNotNone(python_state)
        # Parent change is decay factor 0.5 * 20.0 = +10.0
        self.assertGreater(python_state.score, 50.0)
        print(f"[ TEST SUCCESS ] Skill propagation verified: Parent 'Python' updated to {python_state.score}")

    def test_bayesian_updates(self):
        """Verifies that Bayesian updates alter estimation scores and decrease uncertainty."""
        session = InterviewSession(user_id=self.user.id, interview_type="Technical", status="started")
        db.session.add(session)
        db.session.commit()
        
        # Perform initial response answer evaluation (simulated score: 95.0)
        state_after_update = self.engine.update_skill_state(session.id, "Python", 95.0)
        self.assertGreater(state_after_update.score, 50.0)
        
        # Check uncertainty parameter stored inside competency_map metadata
        c_map = self.engine._get_competency_map_metadata(session.id)
        unc_after_first = c_map.get("Python", {}).get("uncertainty")
        self.assertIsNotNone(unc_after_first)
        self.assertLess(unc_after_first, 15.0)
        
        # Perform second response update (simulated score: 90.0)
        self.engine.update_skill_state(session.id, "Python", 90.0)
        c_map2 = self.engine._get_competency_map_metadata(session.id)
        unc_after_second = c_map2.get("Python", {}).get("uncertainty")
        # Uncertainty should further decrease with additional observations
        self.assertLess(unc_after_second, unc_after_first)
        print(f"[ TEST SUCCESS ] Bayesian updates verified: Uncertainty decreased from {unc_after_first:.2f} to {unc_after_second:.2f}")

    def test_competency_convergence(self):
        """Verifies that the boundary convergence flag transitions to 'Converged' when uncertainty is low."""
        session = InterviewSession(user_id=self.user.id, interview_type="Technical", status="started")
        db.session.add(session)
        db.session.commit()
        
        # Run multiple simulated updates to push down standard error/uncertainty
        for i in range(6):
            self.engine.update_skill_state(session.id, "Python", 90.0)
            
        final_map = self.engine.detect_competency_boundaries(session.id)
        python_status = final_map.get("Python", {})
        self.assertEqual(python_status.get("confidence_level"), "Converged")
        print(f"[ TEST SUCCESS ] Competency convergence verified: Confidence Level is '{python_status.get('confidence_level')}'")

    def test_information_based_question_selection(self):
        """Verifies that item selection selects questions maximizing Fisher Information."""
        session = InterviewSession(user_id=self.user.id, interview_type="Technical", status="started")
        db.session.add(session)
        db.session.commit()
        
        # 1. Candidate is estimated at high capability (score = 85.0)
        state = SessionSkillState(session_id=session.id, skill_name="Lists", score=85.0)
        db.session.add(state)
        db.session.commit()
        
        # Information-theoretic selection should pick the 'Hard' difficulty question since it matches capability
        selected_q, _ = self.engine.get_next_question(session)
        self.assertEqual(selected_q.difficulty, "Hard")
        print(f"[ TEST SUCCESS ] Information-theoretic selection verified: Selected {selected_q.difficulty} question.")

    def test_feature_flags_toggle_rollback(self):
        """Verifies that turning off flags reverts logic back to the legacy system behavior."""
        session = InterviewSession(user_id=self.user.id, interview_type="Technical", status="started")
        db.session.add(session)
        db.session.commit()
        
        # Disable Bayesian Estimation flag
        adaptive_engine_module.ENABLE_BAYESIAN_ESTIMATION = False
        
        # Run update (should use legacy EMA: 0.4 * 90.0 + 0.6 * 50.0 = 66.0)
        state = self.engine.update_skill_state(session.id, "Python", 90.0)
        self.assertEqual(state.score, 66.0)
        
        # Re-enable flag
        adaptive_engine_module.ENABLE_BAYESIAN_ESTIMATION = True
        print("[ TEST SUCCESS ] Feature flags toggle/fallback verified.")

    def test_confidence_weighted_uncertainty_acceleration(self):
        """Verifies that high confidence accelerates posterior uncertainty convergence (smaller sigma)."""
        session = InterviewSession(user_id=self.user.id, interview_type="Technical", status="started")
        db.session.add(session)
        db.session.commit()
        
        # High confidence data (perfect scores, no fillers)
        high_conf = {
            "eye_contact_score": 100.0,
            "filler_count": 0,
            "speech_confidence_score": 100.0,
            "attention_duration_score": 100.0,
            "head_stability_score": 100.0
        }
        
        # Base/default confidence update (usually defaults to 80.0)
        self.engine.update_skill_state(session.id, "Python", 90.0)
        c_map = self.engine._get_competency_map_metadata(session.id)
        unc_default = c_map.get("Python", {}).get("uncertainty")
        
        # We need a new session to compare cleanly
        session2 = InterviewSession(user_id=self.user.id, interview_type="Technical", status="started")
        db.session.add(session2)
        db.session.commit()
        
        self.engine.update_skill_state(session2.id, "Python", 90.0, confidence_data=high_conf)
        c_map2 = self.engine._get_competency_map_metadata(session2.id)
        unc_high = c_map2.get("Python", {}).get("uncertainty")
        
        # High confidence should yield lower uncertainty (faster convergence)
        self.assertLess(unc_high, unc_default)
        print(f"[ TEST SUCCESS ] Uncertainty convergence accelerated with high confidence: default={unc_default:.2f}, high_conf={unc_high:.2f}")

    def test_confidence_weighted_uncertainty_deceleration(self):
        """Verifies that low confidence decelerates posterior uncertainty convergence (larger sigma)."""
        session = InterviewSession(user_id=self.user.id, interview_type="Technical", status="started")
        db.session.add(session)
        db.session.commit()
        
        # Low confidence data (poor scores, many fillers)
        low_conf = {
            "eye_contact_score": 30.0,
            "filler_count": 8,
            "speech_confidence_score": 30.0,
            "attention_duration_score": 30.0,
            "head_stability_score": 30.0
        }
        
        # Base/default confidence update
        self.engine.update_skill_state(session.id, "Python", 90.0)
        c_map = self.engine._get_competency_map_metadata(session.id)
        unc_default = c_map.get("Python", {}).get("uncertainty")
        
        # New session to compare cleanly
        session2 = InterviewSession(user_id=self.user.id, interview_type="Technical", status="started")
        db.session.add(session2)
        db.session.commit()
        
        self.engine.update_skill_state(session2.id, "Python", 90.0, confidence_data=low_conf)
        c_map2 = self.engine._get_competency_map_metadata(session2.id)
        unc_low = c_map2.get("Python", {}).get("uncertainty")
        
        # Low confidence should yield higher uncertainty (slower convergence)
        self.assertGreater(unc_low, unc_default)
        print(f"[ TEST SUCCESS ] Uncertainty convergence decelerated with low confidence: default={unc_default:.2f}, low_conf={unc_low:.2f}")

    def test_explainability_telemetry_fields(self):
        """Verifies that explainability and research logs are correctly generated and stored."""
        session = InterviewSession(user_id=self.user.id, interview_type="Technical", status="started")
        # Seed a dummy entry in decision_log so update_skill_state has an entry to update
        session.decision_log = json.dumps([{
            "question_index": 1,
            "target_skill": "Python",
            "target_difficulty": "Medium"
        }])
        db.session.add(session)
        db.session.commit()
        
        conf_data = {
            "eye_contact_score": 85.0,
            "filler_count": 2,
            "speech_confidence_score": 90.0,
            "attention_duration_score": 88.0,
            "head_stability_score": 92.0
        }
        
        self.engine.update_skill_state(session.id, "Python", 85.0, confidence_data=conf_data)
        
        # 1. Check database decision_log entry has updated fields
        db.session.refresh(session)
        dec_log = json.loads(session.decision_log)
        self.assertEqual(len(dec_log), 1)
        entry = dec_log[0]
        
        self.assertIn("confidence_signal", entry)
        self.assertIn("adjusted_sigma", entry)
        self.assertIn("original_sigma", entry)
        self.assertIn("adjustment_reason", entry)
        self.assertIn("eye_contact_component", entry)
        self.assertIn("filler_words_component", entry)
        
        # 2. Check research log file exports/bayesian_experiment_log.json
        from pathlib import Path
        base_dir = Path(__file__).resolve().parent
        log_file = base_dir / "exports" / "bayesian_experiment_log.json"
        
        self.assertTrue(log_file.exists())
        with open(log_file, 'r', encoding='utf-8') as lf:
            records = json.load(lf)
            self.assertGreater(len(records), 0)
            last_record = records[-1]
            self.assertEqual(last_record["session_id"], session.id)
            self.assertEqual(last_record["filler_count"], 2)
            self.assertIn("reason", last_record)
            
        print("[ TEST SUCCESS ] Explainability and research logging verified successfully.")

class TestResumeInflationScore(unittest.TestCase):
    def setUp(self):
        # Configure app for testing
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
        self.app_context = app.app_context()
        self.app_context.push()
        
        # Clean up leftover test user or questions
        self.cleanup_db()
        
        # Seed test user
        self.user = User(username="inflation_tester", email="tester@hirewise.ai")
        self.user.set_password("password123")
        db.session.add(self.user)
        db.session.commit()

        # Seed standard technical questions
        db.session.add(Question(text="Lists easy question [TEST]", category="Technical", difficulty="Easy", skill="Python", subtopic="Lists"))
        db.session.add(Question(text="Sorting medium question [TEST]", category="Technical", difficulty="Medium", skill="DSA", subtopic="Sorting"))
        db.session.commit()
        
        self.engine = AdaptiveEngine()

    def tearDown(self):
        self.cleanup_db()
        db.session.remove()
        self.app_context.pop()

    def cleanup_db(self):
        try:
            # Delete by username
            user = User.query.filter_by(username="inflation_tester").first()
            if user:
                # Delete sessions
                sessions = InterviewSession.query.filter_by(user_id=user.id).all()
                for s in sessions:
                    SessionSkillState.query.filter_by(session_id=s.id).delete()
                    SessionSkillHistory.query.filter_by(session_id=s.id).delete()
                    Response.query.filter_by(session_id=s.id).delete()
                    db.session.delete(s)
                # Delete resumes
                ResumeUpload.query.filter_by(user_id=user.id).delete()
                db.session.delete(user)
            
            # Delete questions containing [TEST]
            Question.query.filter(Question.text.like("%[TEST]%")).delete()
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"[WARNING] Cleanup database failed: {e}")

    def test_parse_explicit_claims(self):
        """Verifies parsing of explicit claims in candidate resumes."""
        resume = ResumeUpload(
            user_id=self.user.id,
            filename="cv.pdf",
            file_path="uploads/cv.pdf",
            skills_extracted="Python - Expert, SQL - Beginner, Java",
            parsed_text="Has Intermediate level in DSA.",
            ats_score=80
        )
        db.session.add(resume)
        db.session.commit()
        
        self.assertEqual(self.engine.parse_claimed_skill_level(resume, "Python"), "Expert")
        self.assertEqual(self.engine.parse_claimed_skill_level(resume, "SQL"), "Beginner")
        self.assertEqual(self.engine.parse_claimed_skill_level(resume, "DSA"), "Intermediate")
        # Skill not mentioned
        self.assertIsNone(self.engine.parse_claimed_skill_level(resume, "C++"))

    def test_parse_implicit_claims_fallback(self):
        """Verifies fallback levels when explicit level is missing."""
        # Case 1: High ATS score fallback -> Expert
        resume_high = ResumeUpload(
            user_id=self.user.id,
            filename="cv1.pdf",
            file_path="uploads/cv1.pdf",
            skills_extracted="Python, SQL",
            parsed_text="Experienced software engineer.",
            ats_score=85
        )
        self.assertEqual(self.engine.parse_claimed_skill_level(resume_high, "Python"), "Expert")

        # Case 2: Low ATS score, no senior keywords fallback -> Intermediate
        resume_low = ResumeUpload(
            user_id=self.user.id,
            filename="cv2.pdf",
            file_path="uploads/cv2.pdf",
            skills_extracted="Python, SQL",
            parsed_text="Entry level dev.",
            ats_score=60
        )
        self.assertEqual(self.engine.parse_claimed_skill_level(resume_low, "Python"), "Intermediate")

        # Case 3: Low ATS score but has senior keywords -> Expert
        resume_sen = ResumeUpload(
            user_id=self.user.id,
            filename="cv3.pdf",
            file_path="uploads/cv3.pdf",
            skills_extracted="Python, SQL",
            parsed_text="Senior backend software developer.",
            ats_score=60
        )
        self.assertEqual(self.engine.parse_claimed_skill_level(resume_sen, "Python"), "Expert")

    def test_inflation_score_calculation(self):
        """Verifies overall inflation score, mismatch %, and explanations."""
        session = InterviewSession(user_id=self.user.id, interview_type="Technical", status="started")
        db.session.add(session)
        db.session.commit()

        # Seed resume claims
        resume = ResumeUpload(
            user_id=self.user.id,
            filename="cv.pdf",
            file_path="uploads/cv.pdf",
            skills_extracted="Python - Expert, DSA - Intermediate",
            parsed_text="",
            ats_score=80
        )
        db.session.add(resume)
        db.session.commit()

        # Update skill states to simulate performance:
        state_py = SessionSkillState(session_id=session.id, skill_name="Python", score=40.0, level="Beginner")
        state_dsa = SessionSkillState(session_id=session.id, skill_name="DSA", score=70.0, level="Intermediate")
        db.session.add(state_py)
        db.session.add(state_dsa)
        db.session.commit()

        # Trigger boundary detection
        comp_map = self.engine.detect_competency_boundaries(session.id)
        
        # Verify inflation analysis output
        self.assertIn("resume_inflation_analysis", comp_map)
        analysis = comp_map["resume_inflation_analysis"]
        
        self.assertEqual(analysis["resume_inflation_score"], 50.0)
        self.assertEqual(len(analysis["skills_mismatch"]), 2)
        
        py_mismatch = next(item for item in analysis["skills_mismatch"] if item["skill_name"] == "Python")
        self.assertEqual(py_mismatch["claimed_level"], "Expert")
        self.assertEqual(py_mismatch["estimated_level"], "Beginner")
        self.assertEqual(py_mismatch["mismatch_percentage"], 100.0)
        self.assertIn("inflation mismatch", py_mismatch["justification"])
        
        dsa_mismatch = next(item for item in analysis["skills_mismatch"] if item["skill_name"] == "DSA")
        self.assertEqual(dsa_mismatch["claimed_level"], "Intermediate")
        self.assertEqual(dsa_mismatch["estimated_level"], "Intermediate")
        self.assertEqual(dsa_mismatch["mismatch_percentage"], 0.0)
        self.assertIn("No inflation detected", dsa_mismatch["justification"])
        
        self.assertGreater(len(analysis["explainability_log"]), 0)
        print("[ TEST SUCCESS ] Resume inflation score calculations, mismatches, and explainability verified.")
class TestMultimodalConvergenceAnalysis(unittest.TestCase):
    def setUp(self):
        # Configure app for testing
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
        self.app_context = app.app_context()
        self.app_context.push()
        
        # Clean up leftover test user
        self.cleanup_db()
        
        # Seed test user
        self.user = User(username="convergence_tester", email="tester_conv@hirewise.ai")
        self.user.set_password("password123")
        db.session.add(self.user)
        db.session.commit()
        
        self.engine = AdaptiveEngine()

    def tearDown(self):
        self.cleanup_db()
        db.session.remove()
        self.app_context.pop()

    def cleanup_db(self):
        try:
            # Delete user
            user = User.query.filter_by(username="convergence_tester").first()
            if user:
                sessions = InterviewSession.query.filter_by(user_id=user.id).all()
                for s in sessions:
                    SessionSkillState.query.filter_by(session_id=s.id).delete()
                    SessionSkillHistory.query.filter_by(session_id=s.id).delete()
                    Response.query.filter_by(session_id=s.id).delete()
                    db.session.delete(s)
                db.session.delete(user)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"[WARNING] Test Cleanup failed: {e}")

    def test_convergence_speed_and_telemetry(self):
        """Verifies that high-confidence sessions converge faster, telemetry is correct, and metrics persist."""
        # 1. High confidence session
        session_high = InterviewSession(user_id=self.user.id, interview_type="Technical", status="started")
        db.session.add(session_high)
        db.session.commit()
        
        high_conf = {
            "eye_contact_score": 100.0,
            "filler_count": 0,
            "speech_confidence_score": 100.0,
            "attention_duration_score": 100.0,
            "head_stability_score": 100.0
        }
        
        for _ in range(5):
            self.engine.update_skill_state(session_high.id, "Python", 90.0, confidence_data=high_conf)
            
        final_map_high = self.engine.detect_competency_boundaries(session_high.id)
        
        # 2. Low confidence session
        session_low = InterviewSession(user_id=self.user.id, interview_type="Technical", status="started")
        db.session.add(session_low)
        db.session.commit()
        
        low_conf = {
            "eye_contact_score": 30.0,
            "filler_count": 8,
            "speech_confidence_score": 30.0,
            "attention_duration_score": 30.0,
            "head_stability_score": 30.0
        }
        
        for _ in range(5):
            self.engine.update_skill_state(session_low.id, "Python", 90.0, confidence_data=low_conf)
            
        final_map_low = self.engine.detect_competency_boundaries(session_low.id)
        
        # 3. Verify keys and categories
        self.assertIn("multimodal_convergence_telemetry", final_map_high)
        self.assertIn("multimodal_convergence_analysis", final_map_high)
        
        high_telemetry = final_map_high["multimodal_convergence_telemetry"]
        self.assertEqual(len(high_telemetry), 5)
        
        # Check first turn keys
        first_turn = high_telemetry[0]
        required_keys = [
            "turn_number", "sigma_before", "sigma_after", "sigma_change", 
            "confidence_signal", "eye_contact_score", "filler_count", 
            "speech_confidence", "attention_duration", "head_stability"
        ]
        for key in required_keys:
            self.assertIn(key, first_turn)
            
        analysis_high = final_map_high["multimodal_convergence_analysis"]
        analysis_low = final_map_low["multimodal_convergence_analysis"]
        
        self.assertEqual(analysis_high["confidence_category"], "High Confidence")
        self.assertEqual(analysis_low["confidence_category"], "Low Confidence")
        
        # High confidence should stabilize in fewer questions than low confidence
        self.assertLess(
            analysis_high["total_questions_until_sigma_stabilizes"], 
            analysis_low["total_questions_until_sigma_stabilizes"]
        )
        
        # High confidence average sigma reduction should be greater
        self.assertGreater(
            analysis_high["average_sigma_reduction_per_turn"],
            analysis_low["average_sigma_reduction_per_turn"]
        )
        
        print(f"[ TEST SUCCESS ] High confidence total questions = {analysis_high['total_questions_until_sigma_stabilizes']} ({analysis_high['convergence_category']})")
        print(f"[ TEST SUCCESS ] Low confidence total questions = {analysis_low['total_questions_until_sigma_stabilizes']} ({analysis_low['convergence_category']})")

if __name__ == '__main__':
    unittest.main()
