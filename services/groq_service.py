import os
import json
import re
import time
from config import Config

# Try to import groq, handle import error gracefully
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    print("WARNING: groq is not installed. Using rule-based fallback evaluations.")

class GroqService:
    def __init__(self):
        self.api_key = Config.GROQ_API_KEY
        self.model_name = "llama-3.3-70b-versatile"
        
        # 1. Print Key Detection Logs
        if self.api_key:
            print("[INFO] GROQ_API_KEY detected in GroqService.")
        else:
            print("[WARNING] GROQ_API_KEY missing in GroqService.")
            
        # 2. Verify Groq integration
        self.initialized = False
        if GROQ_AVAILABLE and self.api_key:
            try:
                self.client = Groq(api_key=self.api_key, max_retries=0)
                # Verify Groq Integration: Send a test prompt
                test_response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": "Say only the word CONNECTED."}]
                )
                test_text = test_response.choices[0].message.content.strip()
                if "CONNECTED" in test_text.upper():
                    self.initialized = True
                    print("[INFO] GroqService initialized successfully.")
                else:
                    raise Exception(f"Unexpected verification output: {test_text}")
            except Exception as e:
                print(f"[ERROR] GroqService initialization failed:\n{e}")
                self.initialized = False

    def _log_api_call(self, provider, endpoint, response_time, is_success, status_code=200, response_payload=None):
        """Helper to write diagnostic API logs to database"""
        try:
            from flask import current_app, has_app_context
            if not has_app_context():
                return
            from database.connection import db
            from models.api_log import APILog
            
            with current_app.app_context():
                log = APILog(
                    provider=provider,
                    endpoint=endpoint,
                    response_time=response_time,
                    is_success=is_success,
                    status_code=status_code,
                    response_payload=response_payload[:2000] if response_payload else None
                )
                db.session.add(log)
                db.session.commit()
        except Exception as ex:
            print(f"Failed to write API Log in GroqService: {ex}")

    def evaluate_answer(self, question, answer, category, expected_keywords=None):
        """
        Evaluates an answer based on Relevance, Clarity, Completeness, Structure, Professionalism.
        Returns a dict with scores (out of 10) and feedback.
        """
        if not answer or len(answer.strip()) < 5:
            return self._generate_empty_evaluation()
            
        if self.initialized:
            start_time = time.time()
            try:
                prompt = f"""
                You are an expert interviewer evaluating a candidate's answer for a {category} mock interview question.
                
                Question: "{question}"
                Candidate's Answer: "{answer}"
                
                Evaluate the answer across the following 5 criteria:
                1. Relevance (Is the answer answering the specific question asked?)
                2. Clarity (Is it easy to understand, articulate, and free of confusion?)
                3. Completeness (Does it cover all aspects of the question?)
                4. Structure (Is it logically structured, e.g., introduction, context, action, result?)
                5. Professionalism (Does it use appropriate professional tone and industry terms?)
                
                For each criteria, assign a score out of 10 (decimal values allowed).
                Also provide a comprehensive, explainable feedback summary (highlighting strengths and reasons for scores) and actionable recommendations for improvement.
                
                Respond ONLY with a valid JSON object matching the schema below. Do not wrap the JSON in markdown code blocks or add any other text.
                
                {{
                  "relevance": 0.0,
                  "clarity": 0.0,
                  "completeness": 0.0,
                  "structure": 0.0,
                  "professionalism": 0.0,
                  "feedback": "A detailed explanation of the scores...",
                  "suggestions": "Actionable, specific suggestions for improvement..."
                }}
                """
                
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}]
                )
                duration = time.time() - start_time
                response_text = response.choices[0].message.content.strip()
                
                # Sanitize response if it contains markdown code blocks
                if response_text.startswith("```"):
                    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response_text)
                    if match:
                        response_text = match.group(1).strip()
                
                eval_data = json.loads(response_text)
                required_keys = ["relevance", "clarity", "completeness", "structure", "professionalism", "feedback", "suggestions"]
                if all(k in eval_data for k in required_keys):
                    self._log_api_call(provider="groq", endpoint="evaluate_answer", response_time=duration, is_success=True)
                    return eval_data
            except Exception as e:
                duration = time.time() - start_time
                self._log_api_call(provider="groq", endpoint="evaluate_answer", response_time=duration, is_success=False, status_code=500, response_payload=str(e))
                print(f"Groq API evaluation failed: {e}. Falling back to rule-based evaluation.")
                
        # Run Rule-based fallback if API is not available/failed
        return self._rule_based_evaluate(question, answer, category, expected_keywords)

    def evaluate_answer_adaptive(self, question, answer, category, skill=None, expected_keywords=None):
        """
        Evaluates an answer for adaptive technical interviews.
        Grades 6 research-grade metrics.
        """
        if not answer or len(answer.strip()) < 5:
            return {
                "correctness": 1.0,
                "depth": 1.0,
                "relevance": 1.0,
                "completeness": 1.0,
                "communication_quality": 1.0,
                "confidence": 1.0,
                "answer_score": 10.0,
                "feedback": "No substantial response was provided to evaluate.",
                "suggestions": "Please answer the question by speaking clearly into the microphone or typing your answer."
            }
            
        if self.initialized:
            start_time = time.time()
            try:
                skill_str = f" for the skill '{skill}'" if skill else ""
                prompt = f"""
                You are an expert technical interviewer evaluating a candidate's answer for a {category} mock interview question{skill_str}.
                
                Question: "{question}"
                Candidate's Answer: "{answer}"
                
                Evaluate the answer across the following 6 criteria:
                1. Correctness: Assign a score from 0.0 to 10.0. Is the answer technically correct? Are there any errors, misconceptions, or invalid claims?
                2. Depth: Assign a score from 0.0 to 10.0. Does the candidate explain the "how" and "why", detailing underlying mechanisms, architecture, or complexities?
                3. Relevance: Assign a score from 0.0 to 10.0. Does the response stay focused on the specific question asked, avoiding irrelevant rambling?
                4. Completeness: Assign a score from 0.0 to 10.0. Does the answer address all parts and components of the question?
                5. Communication Quality: Assign a score from 0.0 to 10.0. Is the explanation clear, well-articulated, cohesive, and easy to follow?
                6. Confidence: Assign a score from 0.0 to 10.0. Does the candidate speak with assurance, avoiding excessive hesitation markers, qualifiers (e.g. "I guess", "maybe"), or self-doubt?
                
                Calculate an overall "answer_score" from 0.0 to 100.0 (typically the average of the 6 scores multiplied by 10).
                Provide a detailed feedback summary explaining the scores, and 2-3 specific suggestions for improvement.
                
                Respond ONLY with a valid JSON object matching the schema below. Do not wrap the JSON in markdown code blocks or add any other text.
                
                {{
                  "correctness": 0.0,
                  "depth": 0.0,
                  "relevance": 0.0,
                  "completeness": 0.0,
                  "communication_quality": 0.0,
                  "confidence": 0.0,
                  "answer_score": 0.0,
                  "feedback": "A detailed explanation of the scores...",
                  "suggestions": "Actionable, specific suggestions for improvement..."
                }}
                """
                
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}]
                )
                duration = time.time() - start_time
                response_text = response.choices[0].message.content.strip()
                
                # Sanitize response if it contains markdown code blocks
                if response_text.startswith("```"):
                    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response_text)
                    if match:
                        response_text = match.group(1).strip()
                
                eval_data = json.loads(response_text)
                required_keys = ["correctness", "depth", "relevance", "completeness", "communication_quality", "confidence", "answer_score", "feedback", "suggestions"]
                if all(k in eval_data for k in required_keys):
                    self._log_api_call(provider="groq", endpoint="evaluate_answer_adaptive", response_time=duration, is_success=True)
                    return eval_data
            except Exception as e:
                duration = time.time() - start_time
                self._log_api_call(provider="groq", endpoint="evaluate_answer_adaptive", response_time=duration, is_success=False, status_code=500, response_payload=str(e))
                print(f"Groq API adaptive evaluation failed: {e}. Falling back to rule-based adaptive evaluation.")
                
        # Run Rule-based fallback if API is not available/failed
        return self._rule_based_evaluate_adaptive(question, answer, category, skill, expected_keywords)

    def _rule_based_evaluate_adaptive(self, question, answer, category, skill=None, expected_keywords=None):
        """
        Rule-based technical evaluator that scores answers when Groq API is unavailable.
        """
        words = answer.split()
        word_count = len(words)
        
        # Helper: load expected keywords
        keywords = []
        if expected_keywords:
            if isinstance(expected_keywords, str):
                try:
                    keywords = json.loads(expected_keywords)
                except Exception:
                    keywords = []
            elif isinstance(expected_keywords, list):
                keywords = expected_keywords
                
        # Heuristics:
        matched_keywords = []
        relevance_score = 5.0
        if keywords:
            for kw in keywords:
                if kw.lower() in answer.lower():
                    matched_keywords.append(kw)
            keyword_ratio = len(matched_keywords) / len(keywords) if len(keywords) > 0 else 1.0
            relevance_score += (keyword_ratio * 5.0)
        else:
            q_words = set(re.findall(r'\b\w{4,}\b', question.lower()))
            ans_words = set(re.findall(r'\b\w{4,}\b', answer.lower()))
            overlap = q_words.intersection(ans_words)
            overlap_ratio = len(overlap) / len(q_words) if len(q_words) > 0 else 0.5
            relevance_score += min(5.0, overlap_ratio * 7.5)
            
        correctness_score = 4.0
        if matched_keywords:
            correctness_score += min(5.0, len(matched_keywords) * 1.5)
        else:
            correctness_score += min(4.0, (word_count / 15) * 1.0)
        correctness_score = min(10.0, correctness_score)
        
        depth_score = 3.0
        depth_words = ["because", "how", "why", "mechanism", "underlying", "process", "components", "complexity", "internal", "structure", "explain"]
        depth_matches = [w for w in depth_words if w in answer.lower()]
        depth_score += min(4.0, len(depth_matches) * 1.0)
        if word_count > 50:
            depth_score += 1.5
        if word_count > 100:
            depth_score += 1.5
        depth_score = min(10.0, depth_score)
        
        completeness_score = 3.0
        if word_count > 25:
            completeness_score += 2.0
        if word_count > 60:
            completeness_score += 2.0
        if word_count > 110:
            completeness_score += 3.0
        completeness_score = min(10.0, completeness_score)
        
        comm_score = 5.0
        transitions = ["firstly", "secondly", "finally", "therefore", "however", "consequently", "for instance", "to summarize"]
        trans_matches = [t for t in transitions if t in answer.lower()]
        comm_score += min(3.0, len(trans_matches) * 1.0)
        if word_count > 30:
            comm_score += 2.0
        comm_score = min(10.0, comm_score)
        
        qualifiers = ["maybe", "i guess", "probably", "not sure", "don't know", "dont know", "perhaps", "i think"]
        qualifier_count = sum(1 for q in qualifiers if q in answer.lower())
        confidence_score = 9.0 - (qualifier_count * 1.5)
        confidence_score = max(2.0, min(10.0, confidence_score))
        
        if word_count < 10:
            relevance_score = max(1.0, relevance_score - 4.0)
            correctness_score = max(1.0, correctness_score - 4.0)
            depth_score = max(1.0, depth_score - 4.0)
            completeness_score = max(1.0, completeness_score - 4.0)
            comm_score = max(1.0, comm_score - 4.0)
            confidence_score = max(1.0, confidence_score - 4.0)
            
        relevance_score = round(relevance_score, 1)
        correctness_score = round(correctness_score, 1)
        depth_score = round(depth_score, 1)
        completeness_score = round(completeness_score, 1)
        comm_score = round(comm_score, 1)
        confidence_score = round(confidence_score, 1)
        
        avg_score = (relevance_score + correctness_score + depth_score + completeness_score + comm_score + confidence_score) / 6.0
        answer_score = round(avg_score * 10.0, 1)
        
        feedback = f"Rule-based Technical evaluation. Matched key concepts: {', '.join(matched_keywords) if matched_keywords else 'None'}. "
        if depth_score < 6.0:
            feedback += "The answer lacks technical depth. Try explaining 'how' things work internally. "
        else:
            feedback += "The answer demonstrates a good grasp of the technical concepts. "
        if confidence_score < 7.0:
            feedback += "Try to sound more confident and avoid tentative phrases."
            
        suggestions = "1. Detail the internal mechanics or time/space complexity.\n2. Structure using transition words like 'First', 'Then', 'Finally'.\n3. Avoid tentative expressions such as 'I think' or 'maybe'."
        
        return {
            "correctness": correctness_score,
            "depth": depth_score,
            "relevance": relevance_score,
            "completeness": completeness_score,
            "communication_quality": comm_score,
            "confidence": confidence_score,
            "answer_score": answer_score,
            "feedback": feedback,
            "suggestions": suggestions
        }

    def generate_follow_up(self, question, answer):
        """Generates a dynamic follow-up question based on the candidate's response."""
        default_follow_up = "Could you elaborate on how you handled the challenges during that implementation?"
        
        if self.initialized:
            start_time = time.time()
            try:
                prompt = f"""
                You are a professional interviewer. The candidate has just answered a question.
                
                Original Question: "{question}"
                Candidate's Answer: "{answer}"
                
                Based on their answer, ask a single relevant, natural, and engaging follow-up question. 
                Keep it concise (1-2 sentences), professional, and conversational. 
                Do not add any greetings or conversational introductory text, just output the follow-up question.
                """
                
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}]
                )
                duration = time.time() - start_time
                self._log_api_call(provider="groq", endpoint="generate_follow_up", response_time=duration, is_success=True)
                return response.choices[0].message.content.strip()
            except Exception as e:
                duration = time.time() - start_time
                self._log_api_call(provider="groq", endpoint="generate_follow_up", response_time=duration, is_success=False, status_code=500, response_payload=str(e))
                print(f"Groq API follow-up generation failed: {e}")
                
        # Fallback logic based on answer keywords
        answer_lower = answer.lower()
        if "project" in answer_lower or "built" in answer_lower:
            return "That sounds interesting. Could you tell me more about your specific role in that project and the technologies you chose?"
        elif "algorithm" in answer_lower or "code" in answer_lower or "complex" in answer_lower:
            return "How did you optimize your solution, and what was its time and space complexity?"
        elif "team" in answer_lower or "conflict" in answer_lower or "collaboration" in answer_lower:
            return "Looking back, is there anything you would have handled differently to achieve a faster or better resolution?"
        
        return default_follow_up

    def generate_resume_questions(self, resume_text):
        """Parses extracted resume text and returns 5 custom interview questions based on projects, skills, and experiences."""
        fallback_questions = [
            "Explain the technical challenges you faced in your most significant project listed in your resume.",
            "Why did you choose the specific programming languages and databases mentioned in your skills section?",
            "Can you describe a situation where you had to quickly learn a new technology mentioned in your resume?",
            "Walk me through the architecture of your favorite project. How does it handle scaling?",
            "What motivated you to work on the domain of your key project, and what were the main takeaways?"
        ]
        
        if not resume_text or len(resume_text.strip()) < 50:
            return fallback_questions
            
        if self.initialized:
            start_time = time.time()
            try:
                prompt = f"""
                You are a recruiter analyzing a candidate's resume text. 
                Generate exactly 5 customized, technical and behavioral interview questions tailored directly to the projects, technical skills, and work/academic experience mentioned in their resume.
                
                Resume Text:
                \"\"\"{resume_text[:4000]}\"\"\"
                
                Respond ONLY with a valid JSON array of strings. Do not include markdown code blocks or explanatory text.
                
                Example format:
                [
                  "Question 1 based on project X...",
                  "Question 2 based on skill Y..."
                ]
                """
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}]
                )
                duration = time.time() - start_time
                response_text = response.choices[0].message.content.strip()
                
                if response_text.startswith("```"):
                    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response_text)
                    if match:
                        response_text = match.group(1).strip()
                        
                questions = json.loads(response_text)
                if isinstance(questions, list) and len(questions) > 0:
                    self._log_api_call(provider="groq", endpoint="generate_resume_questions", response_time=duration, is_success=True)
                    return questions[:5]
            except Exception as e:
                duration = time.time() - start_time
                self._log_api_call(provider="groq", endpoint="generate_resume_questions", response_time=duration, is_success=False, status_code=500, response_payload=str(e))
                print(f"Groq API resume questions generation failed: {e}")
                
        # Simple local parser if API is not setup
        extracted_questions = []
        skills_matched = []
        tech_keywords = ["python", "javascript", "react", "sql", "java", "c++", "machine learning", "django", "flask", "node"]
        for tech in tech_keywords:
            if tech in resume_text.lower():
                skills_matched.append(tech.capitalize())
        
        if skills_matched:
            skills_str = ", ".join(skills_matched[:3])
            extracted_questions.append(f"I see you have skills in {skills_str}. Can you talk about a time when you combined these technologies to solve a problem?")
        
        project_matches = re.findall(r'(?:project|portfolio|built|developed)\b', resume_text, re.IGNORECASE)
        if len(project_matches) > 0:
            extracted_questions.append("Based on the projects on your resume, explain the main challenge you faced during development and how you overcame it.")
            extracted_questions.append("If you were to rebuild your primary project today, what design patterns or architectural decisions would you change?")
            
        for q in fallback_questions:
            if len(extracted_questions) < 5:
                extracted_questions.append(q)
                
        return extracted_questions[:5]

    def _generate_empty_evaluation(self):
        return {
            "relevance": 1.0,
            "clarity": 1.0,
            "completeness": 1.0,
            "structure": 1.0,
            "professionalism": 1.0,
            "feedback": "No substantial response was provided to evaluate.",
            "suggestions": "Please answer the question by speaking clearly into the microphone or typing your answer."
        }

    def _rule_based_evaluate(self, question, answer, category, expected_keywords=None):
        """
        Rule-based NLP evaluator that scores answers when Groq API is unavailable.
        """
        words = answer.split()
        word_count = len(words)
        
        keywords = []
        if expected_keywords:
            if isinstance(expected_keywords, str):
                try:
                    keywords = json.loads(expected_keywords)
                except Exception:
                    keywords = []
            elif isinstance(expected_keywords, list):
                keywords = expected_keywords
                
        matched_keywords = []
        relevance_score = 5.0
        if keywords:
            for kw in keywords:
                if kw.lower() in answer.lower():
                    matched_keywords.append(kw)
            keyword_ratio = len(matched_keywords) / len(keywords) if len(keywords) > 0 else 1.0
            relevance_score += (keyword_ratio * 5.0)
        else:
            q_words = set(re.findall(r'\b\w{4,}\b', question.lower()))
            ans_words = set(re.findall(r'\b\w{4,}\b', answer.lower()))
            overlap = q_words.intersection(ans_words)
            overlap_ratio = len(overlap) / len(q_words) if len(q_words) > 0 else 0.5
            relevance_score += min(5.0, overlap_ratio * 7.5)
            
        clarity_score = 6.0
        if word_count > 15:
            clarity_score += 2.0
        if '.' in answer or '?' in answer:
            clarity_score += 1.0
        if ',' in answer:
            clarity_score += 1.0
        clarity_score = min(10.0, clarity_score)
        
        completeness_score = 4.0
        if word_count > 30:
            completeness_score += 2.0
        if word_count > 60:
            completeness_score += 2.0
        if word_count > 100:
            completeness_score += 2.0
        completeness_score = min(10.0, completeness_score)
        
        structure_score = 5.0
        structuring_words = ["firstly", "secondly", "finally", "because", "however", "therefore", "for example", "instance", "conclusion", "summarize", "then", "next", "after that"]
        struct_matches = [w for w in structuring_words if w in answer.lower()]
        structure_score += min(5.0, len(struct_matches) * 1.5)
        
        professionalism_score = 6.0
        professional_words = ["system", "implement", "optimize", "deliver", "achieve", "design", "manage", "collaborate", "solve", "critical", "analyze", "strategy", "efficient"]
        prof_matches = [w for w in professional_words if w in answer.lower()]
        professionalism_score += min(4.0, len(prof_matches) * 1.0)
        
        if word_count < 10:
            relevance_score = max(2.0, relevance_score - 3.0)
            clarity_score = max(2.0, clarity_score - 3.0)
            completeness_score = max(2.0, completeness_score - 4.0)
            structure_score = max(2.0, structure_score - 3.0)
            professionalism_score = max(2.0, professionalism_score - 3.0)
            
        relevance_score = round(relevance_score, 1)
        clarity_score = round(clarity_score, 1)
        completeness_score = round(completeness_score, 1)
        structure_score = round(structure_score, 1)
        professionalism_score = round(professionalism_score, 1)
        
        feedback = f"Your answer of {word_count} words was analyzed by the HireWise rule engine. "
        if len(matched_keywords) > 0:
            feedback += f"You successfully referenced key terms: {', '.join(matched_keywords)}. "
        else:
            feedback += "Try to include more technical terms relevant to the question. "
            
        if len(struct_matches) >= 2:
            feedback += "Excellent logical structure was detected using transitional signposts."
        else:
            feedback += "The structural flow can be improved by dividing the response into a clear introduction, core points, and a concluding sentence."
            
        suggestions = "1. Try using the STAR (Situation, Task, Action, Result) methodology to format your responses.\n2. Incorporate more industry-standard terminology.\n3. Speak for at least 45-60 seconds to provide a comprehensive response."
        
        return {
            "relevance": relevance_score,
            "clarity": clarity_score,
            "completeness": completeness_score,
            "structure": structure_score,
            "professionalism": professionalism_score,
            "feedback": feedback,
            "suggestions": suggestions
        }

    def analyze_resume_details(self, resume_text):
        """Analyzes a candidate's resume and extracts key metrics using Groq."""
        fallback_details = {
            "skills": "Software Development",
            "projects": "No specific projects found in text",
            "experience": "No specific experience found in text",
            "certifications": "No certifications listed in text",
            "missing_skills": "System Design, Cloud Deployments, Microservices",
            "ats_score": 60,
            "suggestions": "1. Highlight technical achievements with measurable impact.\n2. Add standard industry keywords related to target roles.\n3. Keep formatting clean and consistent."
        }
        if not resume_text or len(resume_text.strip()) < 50:
            return fallback_details
            
        if self.initialized:
            start_time = time.time()
            try:
                prompt = f"""
                You are an expert ATS (Applicant Tracking System) parser and recruiter. Parse the following candidate resume text and extract structured metrics.
                
                Resume Text:
                \"\"\"{resume_text[:4000]}\"\"\"
                
                Analyze the resume and return a valid JSON object matching this schema:
                {{
                  "skills": "Comma-separated list of extracted technical/professional skills",
                  "projects": "Short summary of projects listed in the resume",
                  "experience": "Short summary of work or academic experience listed",
                  "certifications": "Comma-separated list of certifications or courses",
                  "missing_skills": "Top 3-5 standard industry skills that are missing based on the candidate's career track",
                  "ats_score": Integer between 10 and 100 representing how well the resume is written and formatted,
                  "suggestions": "A few detailed bullet points recommending how to improve the resume for applicant tracking systems"
                }}
                
                Do not include markdown code blocks or any introductory/explanatory text. Respond only with the JSON object.
                """
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}]
                )
                duration = time.time() - start_time
                response_text = response.choices[0].message.content.strip()
                
                if response_text.startswith("```"):
                    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response_text)
                    if match:
                        response_text = match.group(1).strip()
                        
                details = json.loads(response_text)
                required_keys = ["skills", "projects", "experience", "certifications", "missing_skills", "ats_score", "suggestions"]
                if all(k in details for k in required_keys):
                    self._log_api_call(provider="groq", endpoint="analyze_resume_details", response_time=duration, is_success=True)
                    try:
                        details["ats_score"] = int(details["ats_score"])
                    except Exception:
                        details["ats_score"] = 70
                    return details
            except Exception as e:
                duration = time.time() - start_time
                self._log_api_call(provider="groq", endpoint="analyze_resume_details", response_time=duration, is_success=False, status_code=500, response_payload=str(e))
                print(f"Groq API resume detailed analysis failed: {e}. Using rule-based fallback.")
                
        # Rule-based fallback parsing
        skills_found = []
        known_skills = ['python', 'javascript', 'html', 'css', 'react', 'node', 'sql', 'sqlite', 'mongodb', 'c++', 'java', 'opencv', 'mediapipe', 'whisper', 'flask', 'django', 'machine learning', 'scikit-learn']
        text_lower = resume_text.lower()
        for skill in known_skills:
            if skill in text_lower:
                skills_found.append(skill.title())
        skills_str = ", ".join(skills_found) if skills_found else "Software Development"
        
        projects = []
        lines = resume_text.split('\n')
        for line in lines:
            if any(p in line.lower() for p in ['project', 'portfolio', 'built', 'developed']):
                if len(line.strip()) > 15:
                    projects.append(line.strip())
        projects_str = "; ".join(projects[:3]) if projects else "General projects found in text"
        
        experience = []
        for line in lines:
            if any(e in line.lower() for e in ['experience', 'intern', 'work', 'job', 'employed', 'position']):
                if len(line.strip()) > 15:
                    experience.append(line.strip())
        experience_str = "; ".join(experience[:3]) if experience else "General experience found in text"

        return {
            "skills": skills_str,
            "projects": projects_str,
            "experience": experience_str,
            "certifications": "Certifications listed in text",
            "missing_skills": "System Design, Cloud Deployments, Microservices",
            "ats_score": 75 if len(skills_found) > 4 else 55,
            "suggestions": "1. Highlight technical achievements with measurable impact.\n2. Add standard industry keywords related to target roles.\n3. Keep formatting clean and consistent."
        }
