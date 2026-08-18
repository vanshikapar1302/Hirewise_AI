import json
import re
import random
from datetime import datetime
from database.connection import db
from models.question import Question
from models.skill_state import SessionSkillState, SessionSkillHistory
from models.response import Response
from services.groq_service import GroqService

# Feature flags for research contributions
ENABLE_RESUME_PRIORS = True
ENABLE_SKILL_GRAPH = True
ENABLE_BAYESIAN_ESTIMATION = True
ENABLE_BOUNDARY_DETECTION = True
ENABLE_INFORMATION_SELECTION = True

class SkillGraph:
    def __init__(self):
        # Maps a subtopic to its parent skill(s) or prerequisite subtopic(s)
        self.prereqs = {
            # Python Subtopics
            "Lists": ["Python"],
            "Data Types": ["Python"],
            "Operators": ["Python"],
            "Decorators": ["Lists", "Data Types"],
            "Generators": ["Lists", "Data Types"],
            "Memory Management": ["Data Types"],
            "Concurrency": ["Memory Management"],
            "Metaclasses": ["Data Types"],
            "Async IO": ["Concurrency"],
            
            # DSA Subtopics
            "Basic Data Structures": ["DSA"],
            "Searching": ["DSA"],
            "Linked Lists": ["Basic Data Structures"],
            "Sorting": ["Basic Data Structures"],
            "Graph Algorithms": ["Searching", "Linked Lists"],
            "Dynamic Programming": ["Basic Data Structures"],
            "Trees": ["Basic Data Structures"],
            
            # DBMS Subtopics
            "Keys": ["DBMS"],
            "SQL Commands": ["DBMS"],
            "SQL Joins": ["SQL Commands"],
            "Indexing": ["SQL Commands"],
            "Normalization": ["Keys"],
            "Transactions": ["SQL Commands"],
            "Concurrency Control": ["Transactions"]
        }
        
    def get_prerequisites(self, node):
        return self.prereqs.get(node, [])
        
    def get_dependents(self, node):
        return [k for k, v in self.prereqs.items() if node in v]


class AdaptiveEngine:
    def __init__(self):
        self.skills = ["Python", "DSA", "DBMS"]
        self.groq_service = GroqService()
        self.skill_graph = SkillGraph()

    def parse_claimed_skill_level(self, resume, skill_name):
        """
        Parses candidate resume text and extracts their claimed level for a given skill.
        If no explicit level is found, checks general resume characteristics to default
        to 'Expert' or 'Intermediate'.
        """
        skills_text = (resume.skills_extracted or "").lower()
        parsed_text = (resume.parsed_text or "").lower()
        skill_lower = skill_name.lower()
        
        # Check if the skill is mentioned in either place
        if skill_lower not in skills_text and skill_lower not in parsed_text:
            return None
            
        # Match explicit levels near the skill name
        patterns = [
            rf"{re.escape(skill_lower)}\s*[\-\:\(]*\s*(expert|advanced|proficient|senior|lead|intermediate|medium|beginner|novice|basic|entry)",
            rf"(expert|advanced|proficient|senior|lead|intermediate|medium|beginner|novice|basic|entry)\s*(?:in|with|level)?\s*{re.escape(skill_lower)}"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, skills_text, re.IGNORECASE)
            if match:
                level_str = match.group(1).lower()
                if level_str in ["expert", "advanced", "proficient", "senior", "lead"]:
                    return "Expert"
                elif level_str in ["intermediate", "medium"]:
                    return "Intermediate"
                elif level_str in ["beginner", "novice", "basic", "entry"]:
                    return "Beginner"
            
            match = re.search(pattern, parsed_text, re.IGNORECASE)
            if match:
                level_str = match.group(1).lower()
                if level_str in ["expert", "advanced", "proficient", "senior", "lead"]:
                    return "Expert"
                elif level_str in ["intermediate", "medium"]:
                    return "Intermediate"
                elif level_str in ["beginner", "novice", "basic", "entry"]:
                    return "Beginner"
                    
        if skill_lower in skills_text:
            has_senior_indicators = any(kw in parsed_text for kw in ["senior", "lead", "expert", "advanced", "proficient"])
            if has_senior_indicators or (resume.ats_score and resume.ats_score >= 75):
                return "Expert"
            else:
                return "Intermediate"
                
        if skill_lower in parsed_text:
            return "Intermediate"
            
        return None

    def _add_resume_inflation_analysis(self, session, final_map):
        """
        Adds resume inflation analysis block directly to the competency map dict.
        """
        from models.resume_upload import ResumeUpload
        
        inflation_analysis = {
            "resume_inflation_score": 0.0,
            "skills_mismatch": [],
            "explainability_log": []
        }
        
        if not session:
            final_map["resume_inflation_analysis"] = inflation_analysis
            return final_map
            
        resume = ResumeUpload.query.filter_by(user_id=session.user_id).order_by(ResumeUpload.created_at.desc()).first()
        
        if resume:
            skills_mismatch = []
            explain_log = []
            
            level_values = {"Beginner": 1, "Intermediate": 2, "Advanced": 3, "Expert": 3}
            evaluated_skills = [k for k in final_map.keys() if k not in ("resume_inflation_analysis", "multimodal_convergence_telemetry", "multimodal_convergence_analysis", "project_inputs", "project_understanding", "project_feedback", "project_all_question_ids")]
            
            total_mismatch_pct = 0.0
            matched_skills_count = 0
            
            explain_log.append(f"Starting Resume Inflation analysis for user ID {session.user_id} using resume ID {resume.id}.")
            
            for skill in evaluated_skills:
                skill_meta = final_map[skill]
                if not isinstance(skill_meta, dict):
                    continue
                est_score = skill_meta.get("score", 50.0)
                if est_score is None:
                    est_score = 50.0
                try:
                    est_score = float(est_score)
                except (ValueError, TypeError):
                    est_score = 50.0
                
                if est_score < 50.0:
                    est_level = "Beginner"
                elif est_score < 80.0:
                    est_level = "Intermediate"
                else:
                    est_level = "Advanced"
                
                claimed_level = self.parse_claimed_skill_level(resume, skill)
                
                if claimed_level:
                    matched_skills_count += 1
                    c_val = level_values.get(claimed_level, 2)
                    e_val = level_values.get(est_level, 2)
                    
                    if c_val > e_val:
                        mismatch_pct = ((c_val - e_val) / 2.0) * 100.0
                        justification = (
                            f"Candidate claimed {claimed_level} level in {skill} on their resume, "
                            f"but their estimated skill score of {est_score:.1f} corresponds to {est_level}, "
                            f"indicating a {mismatch_pct:.1f}% inflation mismatch."
                        )
                    else:
                        mismatch_pct = 0.0
                        justification = (
                            f"Candidate claimed {claimed_level} level in {skill} on their resume, "
                            f"and their estimated skill score of {est_score:.1f} corresponds to {est_level}. "
                            f"No inflation detected."
                        )
                    
                    total_mismatch_pct += mismatch_pct
                    
                    skills_mismatch.append({
                        "skill_name": skill,
                        "claimed_level": claimed_level,
                        "estimated_level": est_level,
                        "estimated_score": round(est_score, 1),
                        "mismatch_percentage": round(mismatch_pct, 1),
                        "justification": justification
                    })
                    
                    explain_log.append(
                        f"Skill '{skill}': Claimed={claimed_level}, Estimated={est_level} (score: {est_score:.1f}). "
                        f"Mismatch={mismatch_pct:.1f}%. Justification: {justification}"
                    )
                else:
                    explain_log.append(f"Skill '{skill}' was not found/claimed on the candidate's resume.")
            
            if matched_skills_count > 0:
                inflation_score = total_mismatch_pct / matched_skills_count
                explain_log.append(
                    f"Calculated overall Resume Inflation Score: {inflation_score:.1f}/100 "
                    f"based on {matched_skills_count} claimed skills."
                )
            else:
                inflation_score = 0.0
                explain_log.append("No matching resume claims found for evaluated skills. Inflation score defaults to 0.0.")
                
            inflation_analysis["resume_inflation_score"] = round(inflation_score, 1)
            inflation_analysis["skills_mismatch"] = skills_mismatch
            inflation_analysis["explainability_log"] = explain_log
        else:
            inflation_analysis["explainability_log"].append("No resume uploaded for this user. Inflation score defaults to 0.0.")
            
        final_map["resume_inflation_analysis"] = inflation_analysis
        
        print(f"[ EXPLAINABILITY LOG ] Resume Inflation Analysis for session {session.id if session else 'None'}:")
        for log in inflation_analysis["explainability_log"]:
            print(f"  - {log}")
            
        return final_map

    def get_skills_for_session(self, session):
        """
        Determines the targeted skill path for this interview session.
        If a resume is uploaded, matches and prioritizes skills, technologies, and projects from the resume.
        Otherwise falls back to ['Python', 'DSA', 'DBMS'].
        """
        if session and session.interview_type == 'Project':
            return [
                "Project Understanding",
                "Architecture",
                "Technology Stack",
                "Implementation",
                "Challenges",
                "Scalability",
                "Contribution Verification"
            ]
        # Query distinct skills present in the Question database to target only what we can test
        distinct_db_skills = db.session.query(Question.skill).filter(
            Question.skill.isnot(None), Question.skill != ''
        ).distinct().all()
        db_skills = [s[0] for s in distinct_db_skills if s[0]]
        
        # Look up latest resume
        from models.resume_upload import ResumeUpload
        resume = ResumeUpload.query.filter_by(user_id=session.user_id).order_by(ResumeUpload.created_at.desc()).first()
        
        if resume and resume.skills_extracted:
            # Parse extracted skills/technologies and projects
            resume_skills = [s.strip().lower() for s in resume.skills_extracted.split(",") if s.strip()]
            projects_text = (resume.projects or "").lower()
            resume_text = (resume.parsed_text or "").lower()
            
            matched_skills = []
            for db_skill in db_skills:
                db_skill_lower = db_skill.lower()
                score = 0
                
                # Relevance weight: check if explicitly in extracted skills list
                if db_skill_lower in resume_skills:
                    score += 15
                
                # Relevance weight: check if in projects section text
                if db_skill_lower in projects_text:
                    score += 8
                
                # Frequency count: occurrences in the full resume parsed text
                score += resume_text.count(db_skill_lower)
                
                if score > 0:
                    matched_skills.append((db_skill, score))
            
            if matched_skills:
                # Sort matched skills by score descending (highest priority first)
                matched_skills.sort(key=lambda x: x[1], reverse=True)
                skills_list = [s[0] for s in matched_skills]
                
                # Pad with standard skills if less than 3 skills matched to ensure sufficient rotation
                if len(skills_list) < 3:
                    for s in ["Python", "DSA", "DBMS"]:
                        if s not in skills_list and s in db_skills:
                            skills_list.append(s)
                return skills_list
                
        # Fallback to default
        return ["Python", "DSA", "DBMS"]

    # --- Auxiliary Telemetry Helpers ---
    def _get_competency_map_metadata(self, session_id):
        from models.interview import InterviewSession
        session = InterviewSession.query.get(session_id)
        if not session or not session.competency_map:
            return {}
        try:
            return json.loads(session.competency_map)
        except Exception:
            return {}

    def _update_competency_map_metadata(self, session_id, skill_name, score, uncertainty, boundary=None, subtopics=None):
        from models.interview import InterviewSession
        session = InterviewSession.query.get(session_id)
        if not session:
            return
            
        try:
            c_map = json.loads(session.competency_map or '{}')
        except Exception:
            c_map = {}
            
        if not isinstance(c_map, dict):
            c_map = {}
            
        skill_info = c_map.get(skill_name)
        if not isinstance(skill_info, dict):
            c_map[skill_name] = {
                "score": score,
                "boundary": boundary or "Unknown",
                "uncertainty": uncertainty,
                "confidence_level": "Exploring",
                "subtopics": subtopics or {}
            }
        else:
            skill_info["score"] = score
            skill_info["uncertainty"] = uncertainty
            if boundary:
                skill_info["boundary"] = boundary
            if subtopics is not None:
                skill_info["subtopics"] = subtopics
                
            # Compute confidence level based on uncertainty
            if uncertainty < 5.0:
                skill_info["confidence_level"] = "Converged"
            elif uncertainty < 10.0:
                skill_info["confidence_level"] = "Exploring"
            else:
                skill_info["confidence_level"] = "Uncertain"
                
        session.competency_map = json.dumps(c_map)
        db.session.commit()

    def get_initial_prior_for_skill(self, session, skill_name):
        """
        Estimates the initial prior score (0-100) and uncertainty (sigma) for a skill
        based on the candidate's resume analysis if ENABLE_RESUME_PRIORS is True.
        """
        base_score = 50.0
        base_uncertainty = 15.0
        
        if not ENABLE_RESUME_PRIORS or not session:
            return base_score, base_uncertainty
            
        # Look up latest resume
        from models.resume_upload import ResumeUpload
        resume = ResumeUpload.query.filter_by(user_id=session.user_id).order_by(ResumeUpload.created_at.desc()).first()
        
        if not resume:
            return base_score, base_uncertainty
            
        # Analyze resume content for skill evidence
        skills_text = (resume.skills_extracted or "").lower()
        projects_text = (resume.projects or "").lower()
        exp_text = (resume.experience or "").lower()
        full_text = (resume.parsed_text or "").lower()
        
        if not skill_name:
            return base_score, base_uncertainty
            
        skill_lower = skill_name.lower()
        relevance_score = 0
        
        # Explicit skills match
        if skill_lower in skills_text:
            relevance_score += 15
            
        # Projects mention
        if skill_lower in projects_text:
            relevance_score += 10
            
        # Experience mention
        if skill_lower in exp_text:
            relevance_score += 10
            
        # Keyword frequency in full resume
        freq = full_text.count(skill_lower)
        relevance_score += min(freq * 2, 10)
        
        # Adjust base score based on ATS score and relevance
        ats_factor = (resume.ats_score - 60) / 40.0 if resume.ats_score else 0.0
        ats_factor = max(-0.5, min(ats_factor, 0.5)) # clamp to [-0.5, 0.5]
        
        prior_score = base_score + relevance_score * 0.8 + ats_factor * 10.0
        prior_score = max(30.0, min(prior_score, 85.0)) # clamp starting score to reasonable bounds
        
        # If we have evidence, we are slightly more certain of their starting point
        prior_uncertainty = max(10.0, base_uncertainty - (relevance_score / 5.0))
        
        return round(prior_score, 1), round(prior_uncertainty, 1)

    def _apply_score_offset(self, session_id, node_name, offset, visited_nodes):
        state = SessionSkillState.query.filter_by(session_id=session_id, skill_name=node_name).first()
        
        if not state:
            from models.interview import InterviewSession
            session = InterviewSession.query.get(session_id)
            prior_score, prior_uncertainty = self.get_initial_prior_for_skill(session, node_name)
            state = SessionSkillState(
                session_id=session_id,
                skill_name=node_name,
                score=prior_score,
                level='Intermediate'
            )
            db.session.add(state)
            
        old_score = state.score
        new_score = max(0.0, min(100.0, old_score + offset))
        state.score = round(new_score, 1)
        state.updated_at = datetime.utcnow()
        
        if state.score < 50.0:
            state.level = 'Beginner'
        elif state.score < 80.0:
            state.level = 'Intermediate'
        else:
            state.level = 'Advanced'
            
        c_map = self._get_competency_map_metadata(session_id)
        old_unc = None
        if isinstance(c_map, dict):
            skill_info = c_map.get(node_name)
            if isinstance(skill_info, dict):
                old_unc = skill_info.get("uncertainty")
        if old_unc is None:
            from models.interview import InterviewSession
            session = InterviewSession.query.get(session_id)
            _, old_unc = self.get_initial_prior_for_skill(session, node_name)
            
        new_unc = max(2.0, min(15.0, old_unc + 0.5)) # add diffusion noise on propagation
        
        self._update_competency_map_metadata(
            session_id=session_id,
            skill_name=node_name,
            score=state.score,
            uncertainty=new_unc,
            boundary=state.level
        )
        
        history = SessionSkillHistory(
            session_id=session_id,
            skill_name=node_name,
            previous_score=round(old_score, 1),
            updated_score=state.score
        )
        db.session.add(history)

    def propagate_skill_graph_updates(self, session_id, start_node, score_change):
        if not ENABLE_SKILL_GRAPH:
            return
            
        visited = set()
        queue = [(start_node, score_change)]
        propagation_records = []
        
        while queue:
            curr_node, curr_change = queue.pop(0)
            if curr_node in visited or abs(curr_change) < 0.5:
                continue
            visited.add(curr_node)
            
            # Propagate to prerequisites (parents/ancestors)
            for prereq in self.skill_graph.get_prerequisites(curr_node):
                if prereq not in visited:
                    prereq_change = curr_change * 0.5
                    self._apply_score_offset(session_id, prereq, prereq_change, visited)
                    queue.append((prereq, prereq_change))
                    propagation_records.append(f"{curr_node}->{prereq} ({prereq_change:+.1f})")
                    
            # Propagate to dependents (children/descendants)
            for dependent in self.skill_graph.get_dependents(curr_node):
                if dependent not in visited:
                    dep_change = curr_change * 0.4 if curr_change < 0 else curr_change * 0.2
                    self._apply_score_offset(session_id, dependent, dep_change, visited)
                    queue.append((dependent, dep_change))
                    propagation_records.append(f"{curr_node}->{dependent} ({dep_change:+.1f})")
                    
        if propagation_records:
            print(f"[ INFO ] Skill Graph Propagation Updates: {', '.join(propagation_records)}")
        return propagation_records

    # --- Core Route-Faced Signatures ---
    def update_skill_state(self, session_id, skill_name, score, response_id=None, confidence_data=None):
        """
        Updates the candidate's estimated skill score using Bayesian state updates
        and propagates changes across the Dynamic Skill Graph.
        """
        if not ENABLE_BAYESIAN_ESTIMATION:
            # Legacy implementation fallback
            alpha = 0.4
            state = SessionSkillState.query.filter_by(session_id=session_id, skill_name=skill_name).first()
            previous_score = 50.0
            if state:
                previous_score = state.score
                new_score = (alpha * score) + ((1 - alpha) * previous_score)
                state.score = round(new_score, 1)
                state.updated_at = datetime.utcnow()
            else:
                new_score = (alpha * score) + ((1 - alpha) * previous_score)
                state = SessionSkillState(
                    session_id=session_id,
                    skill_name=skill_name,
                    score=round(new_score, 1),
                    level='Intermediate'
                )
                db.session.add(state)
                
            if state.score < 50.0:
                state.level = 'Beginner'
            elif state.score < 80.0:
                state.level = 'Intermediate'
            else:
                state.level = 'Advanced'
                
            history = SessionSkillHistory(
                session_id=session_id,
                skill_name=skill_name,
                previous_score=round(previous_score, 1),
                updated_score=state.score
            )
            db.session.add(history)
            db.session.commit()
            print(f"[ INFO ] Updated skill '{skill_name}' state for Session {session_id}: {previous_score:.1f} -> {state.score:.1f} ({state.level})")
            return state

        # Bayesian Estimation logic
        from models.response import Response
        from models.question import Question
        from models.interview import InterviewSession
        
        target_node = skill_name
        last_q = None
        
        # Look for the last response in this session to identify the subtopic
        if response_id:
            last_resp = Response.query.get(response_id)
        else:
            last_resp = Response.query.filter_by(session_id=session_id).order_by(Response.created_at.desc()).first()
            
        if last_resp and last_resp.question_id:
            last_q = Question.query.get(last_resp.question_id)
            if last_q and last_q.skill == skill_name and last_q.subtopic:
                target_node = last_q.subtopic
                
        # 1. Get or create state for target node
        state = SessionSkillState.query.filter_by(session_id=session_id, skill_name=target_node).first()
        session = InterviewSession.query.get(session_id)
        
        if not state:
            prior_score, prior_uncertainty = self.get_initial_prior_for_skill(session, target_node)
            state = SessionSkillState(
                session_id=session_id,
                skill_name=target_node,
                score=prior_score,
                level='Intermediate'
            )
            db.session.add(state)
            db.session.commit()
            
        previous_score = state.score
        
        # 2. Retrieve old uncertainty from competency map metadata
        c_map = self._get_competency_map_metadata(session_id)
        old_unc = None
        if isinstance(c_map, dict):
            skill_info = c_map.get(target_node)
            if isinstance(skill_info, dict):
                old_unc = skill_info.get("uncertainty")
        if old_unc is None:
            _, old_unc = self.get_initial_prior_for_skill(session, target_node)
            
        # 3. Compute measurement variance adjusted by response duration
        duration_factor = 1.0
        if last_resp and last_resp.duration > 0:
            duration_factor = max(0.7, min(last_resp.duration / 45.0, 1.5))
            
        v = 100.0 * duration_factor
        
        # Compute confidence signal components
        if confidence_data is None:
            confidence_data = {}
            if last_resp:
                confidence_data = {
                    "eye_contact_score": getattr(last_resp, "eye_contact_score", 80.0),
                    "filler_count": getattr(last_resp, "filler_count", 0),
                    "speech_confidence_score": 80.0,
                    "attention_duration_score": getattr(last_resp, "attention_duration_score", 80.0),
                    "head_stability_score": getattr(last_resp, "head_stability_score", 80.0)
                }
            else:
                confidence_data = {
                    "eye_contact_score": 80.0,
                    "filler_count": 0,
                    "speech_confidence_score": 80.0,
                    "attention_duration_score": 80.0,
                    "head_stability_score": 80.0
                }
                
        eye_contact = confidence_data.get("eye_contact_score")
        if eye_contact is None: eye_contact = 80.0
        
        filler_count = confidence_data.get("filler_count")
        if filler_count is None: filler_count = 0
        
        speech_confidence = confidence_data.get("speech_confidence_score")
        if speech_confidence is None: speech_confidence = 80.0
        
        attention_duration = confidence_data.get("attention_duration_score")
        if attention_duration is None: attention_duration = 80.0
        
        head_stability = confidence_data.get("head_stability_score")
        if head_stability is None: head_stability = 80.0
        
        filler_word_score = max(0.0, 100.0 - (filler_count * 10.0))
        
        confidence_signal = (
            0.20 * eye_contact +
            0.20 * filler_word_score +
            0.30 * speech_confidence +
            0.15 * attention_duration +
            0.15 * head_stability
        )
        
        # 4. Bayesian Update Formula
        old_var = old_unc ** 2
        new_var = 1.0 / ((1.0 / old_var) + (1.0 / v))
        new_unc_unadjusted = (new_var) ** 0.5
        
        # Adjust posterior uncertainty based on composite confidence signal
        conf_factor = confidence_signal / 100.0
        modifier = 1.5 - conf_factor  # ranges [0.5, 1.5]
        new_unc_adjusted = new_unc_unadjusted * modifier
        new_unc = max(2.0, min(new_unc_adjusted, 15.0))
        
        # Preserve existing answer correctness scoring as the primary signal
        new_score = new_var * ((previous_score / old_var) + (score / v))
        new_score = max(0.0, min(100.0, new_score))
        
        # Explainability reason
        reason_for_adjustment = (
            f"Confidence signal of {confidence_signal:.1f}% was used to scale uncertainty convergence. "
            f"Since confidence is {'high' if confidence_signal >= 75 else 'low' if confidence_signal < 50 else 'moderate'}, "
            f"convergence of the uncertainty standard error (sigma) was {'accelerated' if confidence_signal >= 75 else 'decelerated' if confidence_signal < 50 else 'maintained'} by a factor of {modifier:.2f}x. "
            f"Correctness remains the primary driver for theta competency score."
        )
        
        # Print explainability log
        print(f"[ EXPLAINABILITY LOG ] update_skill_state details for skill '{target_node}':")
        print(f"  - Original Theta: {previous_score:.2f}")
        print(f"  - Original Sigma: {old_unc:.2f}")
        print(f"  - Confidence Signal: {confidence_signal:.1f}% (eye={eye_contact:.1f}, fillers={filler_word_score:.1f}, speech={speech_confidence:.1f}, attention={attention_duration:.1f}, stability={head_stability:.1f})")
        print(f"  - Adjusted Theta: {new_score:.2f}")
        print(f"  - Adjusted Sigma: {new_unc:.2f} (modifier={modifier:.2f}x)")
        print(f"  - Reason: {reason_for_adjustment}")
        
        # Store turn entry in competency map
        try:
            c_map = self._get_competency_map_metadata(session_id)
            telemetry_list = c_map.get("multimodal_convergence_telemetry", [])
            
            turn_number = len(telemetry_list) + 1
            
            turn_entry = {
                "turn_number": turn_number,
                "sigma_before": round(old_unc, 4),
                "sigma_after": round(new_unc, 4),
                "sigma_change": round(new_unc - old_unc, 4),
                "confidence_signal": round(confidence_signal, 4),
                "eye_contact_score": round(eye_contact, 4),
                "filler_count": int(filler_count),
                "speech_confidence": round(speech_confidence, 4),
                "attention_duration": round(attention_duration, 4),
                "head_stability": round(head_stability, 4)
            }
            
            telemetry_list.append(turn_entry)
            if len(telemetry_list) > 15:
                telemetry_list = telemetry_list[-15:]
                
            c_map["multimodal_convergence_telemetry"] = telemetry_list
            session.competency_map = json.dumps(c_map)
        except Exception as e_telemetry:
            print(f"[ WARNING ] Failed to save turn telemetry to competency_map: {e_telemetry}")

        # Update the entry in decision_log for this session to store confidence telemetry
        try:
            if session.decision_log:
                decision_log = json.loads(session.decision_log)
                current_idx = session.current_index
                if 0 <= current_idx < len(decision_log):
                    entry = decision_log[current_idx]
                    entry.update({
                        "original_theta": round(previous_score, 2),
                        "original_sigma": round(old_unc, 2),
                        "confidence_signal": round(confidence_signal, 2),
                        "adjusted_theta": round(new_score, 1),
                        "adjusted_sigma": round(new_unc, 2),
                        "adjustment_reason": reason_for_adjustment,
                        "eye_contact_component": round(eye_contact, 1),
                        "filler_words_component": round(filler_word_score, 1),
                        "speech_confidence_component": round(speech_confidence, 1),
                        "attention_duration_component": round(attention_duration, 1),
                        "head_stability_component": round(head_stability, 1)
                    })
                    session.decision_log = json.dumps(decision_log)
        except Exception as e_log:
            print(f"[ WARNING ] Failed to append confidence telemetry to decision_log: {e_log}")
            
        # Write to separate research log file exports/bayesian_experiment_log.json
        try:
            from pathlib import Path
            base_dir = Path(__file__).resolve().parent.parent
            exports_dir = base_dir / "exports"
            exports_dir.mkdir(exist_ok=True)
            
            log_file = exports_dir / "bayesian_experiment_log.json"
            
            log_record = {
                "timestamp": datetime.utcnow().isoformat(),
                "session_id": session_id,
                "skill_name": target_node,
                "correctness_score": float(score),
                "original_theta": float(previous_score),
                "original_sigma": float(old_unc),
                "confidence_signal": float(confidence_signal),
                "adjusted_theta": float(new_score),
                "adjusted_sigma": float(new_unc),
                "uncertainty_modifier": float(modifier),
                "eye_contact": float(eye_contact),
                "filler_count": int(filler_count),
                "filler_word_score": float(filler_word_score),
                "speech_confidence": float(speech_confidence),
                "attention_duration": float(attention_duration),
                "head_stability": float(head_stability),
                "reason": reason_for_adjustment
            }
            
            existing_records = []
            if log_file.exists():
                try:
                    with open(log_file, 'r', encoding='utf-8') as lf:
                        existing_records = json.load(lf)
                except Exception:
                    existing_records = []
                    
            existing_records.append(log_record)
            
            with open(log_file, 'w', encoding='utf-8') as lf:
                json.dump(existing_records, lf, indent=2)
                
            print(f"[ SUCCESS ] Saved research metrics to {log_file}")
        except Exception as e_file:
            print(f"[ WARNING ] Failed to save research log file: {e_file}")
        
        state.score = round(new_score, 1)
        state.updated_at = datetime.utcnow()
        
        if state.score < 50.0:
            state.level = 'Beginner'
        elif state.score < 80.0:
            state.level = 'Intermediate'
        else:
            state.level = 'Advanced'
            
        # 5. Record update history
        history = SessionSkillHistory(
            session_id=session_id,
            skill_name=target_node,
            previous_score=round(previous_score, 1),
            updated_score=state.score
        )
        db.session.add(history)
        
        self._update_competency_map_metadata(
            session_id=session_id,
            skill_name=target_node,
            score=state.score,
            uncertainty=new_unc,
            boundary=state.level
        )
        db.session.commit()
        
        print(f"[ INFO ] Bayesian update for '{target_node}': {previous_score:.1f} -> {state.score:.1f} (unc: {new_unc:.2f})")
        
        # 6. Propagate score change to related nodes in graph
        score_change = state.score - previous_score
        self.propagate_skill_graph_updates(session_id, target_node, score_change)
        
        # Sync root skill node if target_node was a subtopic
        if target_node != skill_name:
            root_state = SessionSkillState.query.filter_by(session_id=session_id, skill_name=skill_name).first()
            if not root_state:
                prior_score, prior_uncertainty = self.get_initial_prior_for_skill(session, skill_name)
                root_state = SessionSkillState(
                    session_id=session_id,
                    skill_name=skill_name,
                    score=prior_score,
                    level='Intermediate'
                )
                db.session.add(root_state)
                db.session.commit()
                
            # Perform smaller Bayesian update directly to root skill as well
            old_r_score = root_state.score
            c_map_r = self._get_competency_map_metadata(session_id)
            old_r_unc = None
            if isinstance(c_map_r, dict):
                skill_info = c_map_r.get(skill_name)
                if isinstance(skill_info, dict):
                    old_r_unc = skill_info.get("uncertainty")
            if old_r_unc is None:
                _, old_r_unc = self.get_initial_prior_for_skill(session, skill_name)
                
            v_root = 150.0  # higher measurement variance for root node direct update
            old_r_var = old_r_unc ** 2
            new_r_var = 1.0 / ((1.0 / old_r_var) + (1.0 / v_root))
            new_r_unc_unadjusted = (new_r_var) ** 0.5
            
            # Apply the same confidence modifier to root skill uncertainty as well
            new_r_unc_adjusted = new_r_unc_unadjusted * modifier
            new_r_unc = max(2.0, min(new_r_unc_adjusted, 15.0))
            new_r_score = new_r_var * ((old_r_score / old_r_var) + (score / v_root))
            
            root_state.score = round(max(0.0, min(100.0, new_r_score)), 1)
            if root_state.score < 50.0:
                root_state.level = 'Beginner'
            elif root_state.score < 80.0:
                root_state.level = 'Intermediate'
            else:
                root_state.level = 'Advanced'
                
            self._update_competency_map_metadata(
                session_id=session_id,
                skill_name=skill_name,
                score=root_state.score,
                uncertainty=new_r_unc,
                boundary=root_state.level
            )
            db.session.commit()
            
        return state

    def get_next_question(self, session, last_response=None):
        """
        Implements rule-based and LLM-guided next question selection logic,
        incorporating Information-Theoretic and Graph-Constrained item selection.
        """
        if not ENABLE_INFORMATION_SELECTION:
            # Legacy implementation fallback
            asked_ids = json.loads(session.question_ids or '[]')
            decision_log = json.loads(session.decision_log or '[]')
            session_skills = self.get_skills_for_session(session)
            asked_questions = Question.query.filter(Question.id.in_(asked_ids)).all() if asked_ids else []
            asked_subtopics = {q.subtopic for q in asked_questions if q.subtopic}
            
            target_skill = session_skills[0] if session_skills else "Python"
            target_difficulty = "Medium"
            reason = "Initial question selection."
            
            if last_response and last_response.question_id:
                last_q = Question.query.get(last_response.question_id)
                last_skill = last_q.skill if last_q else (session_skills[0] if session_skills else "Python")
                last_difficulty = last_q.difficulty if last_q else "Medium"
                last_score = last_response.answer_score
                
                if last_score > 80.0:
                    if last_difficulty == "Easy":
                        target_difficulty = "Medium"
                    else:
                        target_difficulty = "Hard"
                    diff_reason = f"Last score {last_score:.1f} was > 80, climbing up to {target_difficulty}."
                elif last_score < 50.0:
                    if last_difficulty == "Hard":
                        target_difficulty = "Medium"
                    else:
                        target_difficulty = "Easy"
                    diff_reason = f"Last score {last_score:.1f} was < 50, stepping down to {target_difficulty}."
                else:
                    target_difficulty = last_difficulty
                    diff_reason = f"Last score {last_score:.1f} was stable (50-80), maintaining {target_difficulty}."

                current_skill_index = session_skills.index(last_skill) if last_skill in session_skills else 0
                target_skill = session_skills[(current_skill_index + 1) % len(session_skills)]
                reason = f"Rotated skill from {last_skill} to {target_skill}. {diff_reason}"
                
                if session.experiment_mode in ['adaptive_gpt', 'adaptive_claude', 'adaptive_gemini', 'adaptive_groq'] and self.groq_service.initialized:
                    try:
                        states = SessionSkillState.query.filter_by(session_id=session.id).all()
                        states_dict = {s.skill_name: s.score for s in states}
                        for sk in session_skills:
                            if sk not in states_dict:
                                states_dict[sk] = 50.0
                                
                        prompt = f"""
                        You are the orchestrator of an adaptive technical mock interview.
                        We are assessing the candidate on three skills: {', '.join(session_skills)}.
                        
                        Current candidate skill estimates:
                        {json.dumps(states_dict, indent=2)}
                        
                        History of asked questions:
                        """
                        for idx, r in enumerate(session.responses):
                            q_obj = Question.query.get(r.question_id) if r.question_id else None
                            q_skill = q_obj.skill if q_obj else "Unknown"
                            q_diff = q_obj.difficulty if q_obj else "Unknown"
                            prompt += f"- Question: {r.question_text} (Skill: {q_skill}, Difficulty: {q_diff}) | Score: {r.answer_score:.1f}\n"
                            
                        prompt += f"""
                        Determine the next target skill and difficulty level to test the candidate.
                        - You should prioritize testing skills that have not been tested yet, or where the candidate's boundary is still unclear (e.g. scores close to 50 or 80).
                        - Adjust difficulty up if they did well on that skill previously, and down if they struggled.
                        - Choose target_skill from: {session_skills}
                        - Choose target_difficulty from: ["Easy", "Medium", "Hard"]
                        
                        Respond strictly with a JSON object:
                        {{
                          "target_skill": "Skill Name",
                          "target_difficulty": "Easy/Medium/Hard",
                          "reason": "Detailed explanation of the cognitive adaptation decision"
                        }}
                        """
                        llm_res = self.groq_service.client.chat.completions.create(
                            model=self.groq_service.model_name,
                            messages=[{"role": "user", "content": prompt}]
                        )
                        llm_text = llm_res.choices[0].message.content.strip()
                        if llm_text.startswith("```"):
                            import re
                            match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", llm_text)
                            if match:
                                llm_text = match.group(1).strip()
                                
                        decision = json.loads(llm_text)
                        if decision.get("target_skill") in session_skills and decision.get("target_difficulty") in ["Easy", "Medium", "Hard"]:
                            target_skill = decision["target_skill"]
                            target_difficulty = decision["target_difficulty"]
                            reason = f"[LLM Decided] {decision.get('reason')}"
                    except Exception as ex:
                        print(f"[ WARNING ] LLM question adaptation guidance failed: {ex}. Using rule-based fallback.")

            c_map = self._get_competency_map_metadata(session.id)
            project_all_ids = c_map.get("project_all_question_ids", []) if session.interview_type == 'Project' else []

            if session.interview_type == 'Project':
                q_query = Question.query.filter(Question.id.in_(project_all_ids)).filter_by(skill=target_skill, difficulty=target_difficulty)
            else:
                q_query = Question.query.filter_by(skill=target_skill, difficulty=target_difficulty)
            if asked_ids:
                q_query = q_query.filter(Question.id.notin_(asked_ids))
            candidate_qs = q_query.all()
            
            if not candidate_qs:
                fallback_difficulties = ["Medium", "Easy", "Hard"]
                fallback_difficulties.remove(target_difficulty)
                for f_diff in fallback_difficulties:
                    if session.interview_type == 'Project':
                        q_query_fb = Question.query.filter(Question.id.in_(project_all_ids)).filter_by(skill=target_skill, difficulty=f_diff)
                    else:
                        q_query_fb = Question.query.filter_by(skill=target_skill, difficulty=f_diff)
                    if asked_ids:
                        q_query_fb = q_query_fb.filter(Question.id.notin_(asked_ids))
                    candidate_qs = q_query_fb.all()
                    if candidate_qs:
                        target_difficulty = f_diff
                        reason += f" (Fallback to {f_diff} difficulty)"
                        break
                        
            if not candidate_qs:
                if session.interview_type == 'Project':
                    q_query_fb = Question.query.filter(Question.id.in_(project_all_ids))
                else:
                    q_query_fb = Question.query.filter(Question.skill.isnot(None))
                if asked_ids:
                    q_query_fb = q_query_fb.filter(Question.id.notin_(asked_ids))
                candidate_qs = q_query_fb.all()
                if candidate_qs:
                    selected_q = random.choice(candidate_qs)
                    target_skill = selected_q.skill
                    target_difficulty = selected_q.difficulty
                    reason += f" (Global fallback to {target_skill} {target_difficulty})"
                    candidate_qs = [selected_q]
                    
            if candidate_qs:
                unused_subtopic_qs = [q for q in candidate_qs if q.subtopic not in asked_subtopics]
                selected_q = random.choice(unused_subtopic_qs) if unused_subtopic_qs else random.choice(candidate_qs)
            else:
                selected_q = Question.query.first()
                if selected_q:
                    reason += " (Absolute baseline fallback)"
                else:
                    return None, "No questions found in database."

            generated_interview_path = []
            for entry in decision_log:
                if "target_skill" in entry:
                    generated_interview_path.append(entry["target_skill"])
            generated_interview_path.append(target_skill)

            decision_entry = {
                "question_index": len(asked_ids) + 1,
                "target_skill": target_skill,
                "target_difficulty": target_difficulty,
                "selected_question_id": selected_q.id,
                "selected_question_text": selected_q.text[:60] + "...",
                "last_score": last_response.answer_score if last_response else None,
                "reason": reason,
                "detected_skills": session_skills,
                "skill_priority": session_skills,
                "generated_interview_path": generated_interview_path
            }
            decision_log.append(decision_entry)
            session.decision_log = json.dumps(decision_log)
            db.session.commit()
            return selected_q, reason

        # Information-Theoretic Selection logic
        asked_ids = json.loads(session.question_ids or '[]')
        decision_log = json.loads(session.decision_log or '[]')
        
        session_skills = self.get_skills_for_session(session)
        asked_questions = Question.query.filter(Question.id.in_(asked_ids)).all() if asked_ids else []
        asked_subtopics = {q.subtopic for q in asked_questions if q.subtopic}
        
        if session.interview_type == 'Project':
            c_map = self._get_competency_map_metadata(session.id)
            project_all_ids = c_map.get("project_all_question_ids", [])
            all_qs = Question.query.filter(Question.id.in_(project_all_ids)).all()
        else:
            all_qs = Question.query.filter(Question.skill.isnot(None)).all()
        candidate_qs = [q for q in all_qs if q.id not in asked_ids]
        
        if not candidate_qs:
            candidate_qs = all_qs if all_qs else [Question.query.first()]
            
        if not candidate_qs or not candidate_qs[0]:
            return None, "No questions found in database."
            
        scored_candidates = []
        difficulty_mapping = {"Easy": 35.0, "Medium": 65.0, "Hard": 90.0}
        
        for q in candidate_qs:
            skill = q.skill
            subtopic = q.subtopic or skill
            
            state = SessionSkillState.query.filter_by(session_id=session.id, skill_name=subtopic).first()
            if not state:
                state = SessionSkillState.query.filter_by(session_id=session.id, skill_name=skill).first()
                
            if state:
                theta = state.score
            else:
                theta, _ = self.get_initial_prior_for_skill(session, subtopic)
                
            q_diff_val = difficulty_mapping.get(q.difficulty, 65.0)
            # Fisher Info prox calculation (Gaussian with standard deviation = 18.0)
            info_score = 2.71828 ** (-((q_diff_val - theta) ** 2) / (2 * (18.0 ** 2)))
            
            # Prerequisite match checking
            prereqs = self.skill_graph.get_prerequisites(subtopic)
            prereqs_met = True
            for prereq in prereqs:
                p_state = SessionSkillState.query.filter_by(session_id=session.id, skill_name=prereq).first()
                if p_state and p_state.score < 50.0:
                    prereqs_met = False
                    break
            prereq_score = 1.0 if prereqs_met else 0.2
            
            # Resume relevance matching
            resume_score = 1.0 if skill in session_skills else 0.0
            
            # Novelty penalty to avoid repeat subtopics
            novelty_score = 0.0 if q.subtopic not in asked_subtopics else -0.5
            
            # Utility function
            utility = (0.4 * info_score) + (0.3 * prereq_score) + (0.3 * resume_score) + novelty_score
            scored_candidates.append((q, utility, info_score, prereq_score, resume_score, novelty_score))
            
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        best_q, best_utility, best_info, best_prereq, best_resume, best_novelty = scored_candidates[0]
        
        target_skill = best_q.skill
        target_difficulty = best_q.difficulty
        reason = f"Information-Theoretic selection. Utility: {best_utility:.2f} (Info: {best_info:.2f}, Prereq: {best_prereq:.2f}, Resume: {best_resume:.2f}, Novelty: {best_novelty:.2f})."
        
        # Groq-based adaptive optimization
        if session.experiment_mode in ['adaptive_gpt', 'adaptive_claude', 'adaptive_gemini', 'adaptive_groq'] and self.groq_service.initialized:
            try:
                top_5_suggestions = []
                for candidate in scored_candidates[:5]:
                    c_q = candidate[0]
                    top_5_suggestions.append({
                        "id": c_q.id,
                        "text": c_q.text[:60] + "...",
                        "skill": c_q.skill,
                        "subtopic": c_q.subtopic,
                        "difficulty": c_q.difficulty,
                        "utility_score": round(candidate[1], 2)
                    })
                    
                states = SessionSkillState.query.filter_by(session_id=session.id).all()
                states_dict = {s.skill_name: s.score for s in states}
                for sk in session_skills:
                    if sk not in states_dict:
                        states_dict[sk] = self.get_initial_prior_for_skill(session, sk)[0]
                        
                prompt = f"""
                You are the orchestrator of an adaptive technical mock interview.
                We are assessing the candidate on skills: {', '.join(session_skills)}.
                
                Current candidate competency estimates:
                {json.dumps(states_dict, indent=2)}
                
                History of asked questions:
                """
                for idx, r in enumerate(session.responses):
                    q_obj = Question.query.get(r.question_id) if r.question_id else None
                    q_skill = q_obj.skill if q_obj else "Unknown"
                    q_diff = q_obj.difficulty if q_obj else "Unknown"
                    prompt += f"- Question: {r.question_text} (Skill: {q_skill}, Difficulty: {q_diff}) | Score: {r.answer_score:.1f}\n"
                    
                prompt += f"""
                Our Information-Theoretic item selection engine has ranked the top 5 questions:
                {json.dumps(top_5_suggestions, indent=2)}
                
                Select one Question ID from the top suggestions that best fits the flow, keeps the candidate engaged, and matches their current skill boundary.
                
                Respond strictly with a JSON object:
                {{
                  "selected_question_id": <int>,
                  "reason": "Detailed explanation of cognitive adaptation decision"
                }}
                """
                llm_res = self.groq_service.client.chat.completions.create(
                    model=self.groq_service.model_name,
                    messages=[{"role": "user", "content": prompt}]
                )
                llm_text = llm_res.choices[0].message.content.strip()
                if llm_text.startswith("```"):
                    import re
                    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", llm_text)
                    if match:
                        llm_text = match.group(1).strip()
                        
                decision = json.loads(llm_text)
                chosen_id = decision.get("selected_question_id")
                chosen_q = Question.query.get(chosen_id)
                if chosen_q and chosen_q.id in [item["id"] for item in top_5_suggestions]:
                    best_q = chosen_q
                    target_skill = chosen_q.skill
                    target_difficulty = chosen_q.difficulty
                    reason = f"[LLM Decided from Suggestions] {decision.get('reason')}"
            except Exception as ex:
                print(f"[ WARNING ] LLM item guidance failed: {ex}. Using mathematical item selection.")
                
        generated_interview_path = []
        for entry in decision_log:
            if "target_skill" in entry:
                generated_interview_path.append(entry["target_skill"])
        generated_interview_path.append(target_skill)
        
        # Telemetry updates for research purposes
        c_map = self._get_competency_map_metadata(session.id)
        current_skill_unc = None
        if isinstance(c_map, dict):
            skill_info = c_map.get(best_q.subtopic or target_skill)
            if isinstance(skill_info, dict):
                current_skill_unc = skill_info.get("uncertainty")
        if current_skill_unc is None:
            current_skill_unc = 15.0
        
        # Propagations trace
        propagation_records = self._get_recent_propagations(session.id)
        
        decision_entry = {
            "question_index": len(asked_ids) + 1,
            "target_skill": target_skill,
            "target_difficulty": target_difficulty,
            "selected_question_id": best_q.id,
            "selected_question_text": best_q.text[:60] + "...",
            "last_score": last_response.answer_score if last_response else None,
            "reason": reason,
            "detected_skills": session_skills,
            "skill_priority": session_skills,
            "generated_interview_path": generated_interview_path,
            
            # Research fields
            "selected_question": best_q.text,
            "question_difficulty": target_difficulty,
            "estimated_skill": target_skill if not best_q.subtopic else f"{target_skill}/{best_q.subtopic}",
            "uncertainty_sigma": round(current_skill_unc, 2),
            "fisher_information": round(best_info, 4),
            "propagation_updates": propagation_records,
            "selection_reason": reason
        }
        decision_log.append(decision_entry)
        session.decision_log = json.dumps(decision_log)
        db.session.commit()
        
        return best_q, reason

    def _get_recent_propagations(self, session_id):
        history = SessionSkillHistory.query.filter_by(session_id=session_id).order_by(SessionSkillHistory.timestamp.desc()).limit(5).all()
        return [f"{h.skill_name} ({h.previous_score:.1f}->{h.updated_score:.1f})" for h in history]

    def detect_competency_boundaries(self, session_id):
        """
        Classifies candidate competency boundaries at the end of the session,
        incorporating uncertainty error and convergence detection if enabled.
        """
        # Load convergence telemetry
        c_map_raw = self._get_competency_map_metadata(session_id)
        if not isinstance(c_map_raw, dict):
            c_map_raw = {}
        telemetry_list = c_map_raw.get("multimodal_convergence_telemetry", [])
        if not isinstance(telemetry_list, list):
            telemetry_list = []
        
        stabilization_turn = None
        for turn in telemetry_list:
            if not isinstance(turn, dict):
                continue
            sig_change = turn.get("sigma_change")
            if sig_change is not None:
                try:
                    if abs(float(sig_change)) <= 0.15:
                        stabilization_turn = turn.get("turn_number")
                        break
                except (ValueError, TypeError):
                    pass
        if stabilization_turn is None:
            stabilization_turn = len(telemetry_list) if telemetry_list else 5
            
        reductions = []
        confidences = []
        for turn in telemetry_list:
            if not isinstance(turn, dict):
                continue
            sig_before = turn.get("sigma_before")
            sig_after = turn.get("sigma_after")
            conf_sig = turn.get("confidence_signal")
            
            if sig_before is not None and sig_after is not None:
                try:
                    reductions.append(float(sig_before) - float(sig_after))
                except (ValueError, TypeError):
                    pass
            if conf_sig is not None:
                try:
                    confidences.append(float(conf_sig))
                except (ValueError, TypeError):
                    pass
                    
        avg_reduction = round(sum(reductions) / len(reductions), 4) if reductions else 0.0
        avg_conf = sum(confidences) / len(confidences) if confidences else 80.0
            
        if avg_conf >= 75.0:
            conf_cat = "High Confidence"
        elif avg_conf >= 55.0:
            conf_cat = "Medium Confidence"
        else:
            conf_cat = "Low Confidence"
            
        if stabilization_turn <= 3:
            conv_cat = "Fast"
        elif stabilization_turn == 4:
            conv_cat = "Moderate"
        else:
            conv_cat = "Slow"
            
        convergence_analysis = {
            "total_questions_until_sigma_stabilizes": stabilization_turn,
            "average_sigma_reduction_per_turn": avg_reduction,
            "confidence_category": conf_cat,
            "convergence_category": conv_cat,
            "average_confidence_signal": round(avg_conf, 2)
        }

        if not ENABLE_BOUNDARY_DETECTION:
            # Legacy implementation fallback
            from models.interview import InterviewSession
            session = InterviewSession.query.get(session_id)
            session_skills = self.get_skills_for_session(session) if session else ["Python", "DSA", "DBMS"]
            states = SessionSkillState.query.filter_by(session_id=session_id).all()
            responses = db.session.query(Response).filter_by(session_id=session_id).all()
            
            subtopic_scores = {}
            for r in responses:
                q_obj = Question.query.get(r.question_id) if r.question_id else None
                if q_obj and q_obj.subtopic and q_obj.skill:
                    key = (q_obj.skill, q_obj.subtopic)
                    if key not in subtopic_scores:
                        subtopic_scores[key] = []
                    subtopic_scores[key].append(r.answer_score)
                    
            competency_map = {}
            for state in states:
                skill = state.skill_name
                score = state.score
                if score >= 80.0:
                    boundary = "Knows"
                elif score >= 50.0:
                    boundary = "Weak"
                else:
                    boundary = "Does_Not_Know"
                    
                competency_map[skill] = {
                    "score": score,
                    "boundary": boundary,
                    "subtopics": {}
                }
                
            for (skill, subtopic), scores in subtopic_scores.items():
                if skill in competency_map:
                    avg_sub_score = sum(scores) / len(scores)
                    if avg_sub_score >= 80.0:
                        sub_boundary = "Knows"
                    elif avg_sub_score >= 50.0:
                        sub_boundary = "Weak"
                    else:
                        sub_boundary = "Does_Not_Know"
                    competency_map[skill]["subtopics"][subtopic] = sub_boundary
                    
            for skill in session_skills:
                if skill not in competency_map:
                    competency_map[skill] = {
                        "score": 50.0,
                        "boundary": "Unknown",
                        "subtopics": {}
                    }
            competency_map["multimodal_convergence_telemetry"] = telemetry_list
            competency_map["multimodal_convergence_analysis"] = convergence_analysis
            competency_map = self._add_resume_inflation_analysis(session, competency_map)
            return competency_map

        # Advanced boundary classification
        from models.interview import InterviewSession
        session = InterviewSession.query.get(session_id)
        session_skills = self.get_skills_for_session(session) if session else ["Python", "DSA", "DBMS"]
        
        states = SessionSkillState.query.filter_by(session_id=session_id).all()
        c_map = self._get_competency_map_metadata(session_id)
        
        competency_map = {}
        for state in states:
            skill = state.skill_name
            score = state.score
            
            unc = None
            if isinstance(c_map, dict):
                skill_info = c_map.get(skill)
                if isinstance(skill_info, dict):
                    unc = skill_info.get("uncertainty")
            if unc is None:
                _, unc = self.get_initial_prior_for_skill(session, skill)
                
            if unc < 5.0:
                conf = "Converged"
            elif unc < 10.0:
                conf = "Exploring"
            else:
                conf = "Uncertain"
                
            if score >= 80.0:
                boundary = "Knows"
            elif score >= 50.0:
                boundary = "Weak"
            else:
                boundary = "Does_Not_Know"
                
            competency_map[skill] = {
                "score": score,
                "boundary": boundary,
                "uncertainty": round(unc, 2),
                "confidence_level": conf,
                "subtopics": {}
            }
            
        final_map = {}
        for skill in session_skills:
            if skill in competency_map:
                final_map[skill] = competency_map[skill]
            else:
                final_map[skill] = {
                    "score": 50.0,
                    "boundary": "Unknown",
                    "uncertainty": 15.0,
                    "confidence_level": "Uncertain",
                    "subtopics": {}
                }
                
        # Fill subtopics for parent root skills
        for state in states:
            node = state.skill_name
            prereqs = self.skill_graph.get_prerequisites(node)
            for parent in prereqs:
                if parent in final_map:
                    if state.score >= 80.0:
                        sub_boundary = "Knows"
                    elif state.score >= 50.0:
                        sub_boundary = "Weak"
                    else:
                        sub_boundary = "Does_Not_Know"
                    final_map[parent]["subtopics"][node] = sub_boundary
                    
        final_map["multimodal_convergence_telemetry"] = telemetry_list
        final_map["multimodal_convergence_analysis"] = convergence_analysis
        final_map = self._add_resume_inflation_analysis(session, final_map)
        
        # Preserve project-specific keys
        if isinstance(c_map, dict):
            for key in ["project_inputs", "project_understanding", "project_all_question_ids", "project_feedback"]:
                if key in c_map:
                    final_map[key] = c_map[key]
                    
        return final_map
