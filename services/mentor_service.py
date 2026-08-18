import os
import json
import re
import random
import requests
from config import Config
import time

# Try to import groq, handle import error gracefully
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    print("WARNING: groq is not installed. Using rule-based fallback evaluations.")

# Global store for telemetry
LAST_DEBUG_INFO = {}

class MentorService:
    TEMPLATES = {
        "Concept Tutor": (
            "You are Concept Tutor, an intelligent placement preparation assistant. "
            "Explain concepts with examples, analogies, and a technical interview perspective. "
            "Use clear formatting, write clean Python code blocks if relevant, and analyze time/space complexity. "
            "Always ask a single relevant follow-up question to test understanding."
        ),
        "Interview Coach": (
            "You are Interview Coach, a recruiter guiding candidates for placement interviews. "
            "Help candidates prepare by generating structured questions, suggesting roadmaps, "
            "and outlining target company criteria (e.g. Leadership Principles for Amazon). "
            "Offer strategies and review response structures."
        ),
        "Resume Mentor": (
            "You are Resume Mentor, an ATS optimizer and project coach. "
            "Review candidate projects and technical skills. Suggest formatting accomplishments "
            "using the Google X-Y-Z formula (Accomplished [X] as measured by [Y] by doing [Z]). "
            "Tailor project improvements to the exact technologies mentioned in their profile."
        ),
        "Coding Mentor": (
            "You are Coding Mentor, a software engineer. Solve programming and algorithmic problems, "
            "debug code blocks, design clean schemas, and optimize space/time complexity. "
            "Explain the logic step-by-step and provide clean, annotated code."
        ),
        "Behavioral Mentor": (
            "You are Behavioral Mentor, a soft skills and communication guide. "
            "Help candidates answer behavioral queries using the STAR method (Situation, Task, Action, Result). "
            "Teach the candidate how to speak clearly, aiming for 110-150 Words Per Minute (WPM), "
            "and minimizing filler words (like 'um', 'like', 'you know')."
        ),
        "Mock Interviewer": (
            "You are Mock Interviewer, a strict technical lead. "
            "Conduct a turn-based mock interview. Ask exactly one question at a time and wait for the response. "
            "Evaluate candidate answers stringently, show ideal answers/code, and ask the next sequential question."
        )
    }

    def __init__(self):
        self.groq_key = Config.GROQ_API_KEY
        self.claude_key = Config.CLAUDE_API_KEY
        self.model_name = "llama-3.3-70b-versatile"
        
        # 1. Print Key Detection Logs
        if self.groq_key:
            print("[INFO] GROQ_API_KEY detected.")
        else:
            print("[WARNING] GROQ_API_KEY missing.")
            
        if self.claude_key:
            print("[INFO] CLAUDE_API_KEY detected.")
        else:
            print("[WARNING] CLAUDE_API_KEY missing.")
            
        # 2. Verify Groq integration
        self.groq_initialized = False
        if GROQ_AVAILABLE and self.groq_key:
            try:
                self.client = Groq(api_key=self.groq_key)
                self.groq_initialized = True
                print("[INFO] Groq initialized successfully.")
            except Exception as e:
                print(f"[ERROR] Groq initialization failed:\n{e}")
                self.groq_initialized = False
                
        # 3. Print Running Mode
        if self.groq_initialized:
            print("[INFO] Running in Groq Mode")
        elif self.claude_key:
            print("[INFO] Running in Claude Mode")
        else:
            print("[INFO] Running in Fallback Mode")

    def _log_api_call(self, provider, endpoint, response_time, is_success, status_code=200, response_payload=None):
        """Helper to write diagnostic and operational API logs to database"""
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
            print(f"Failed to write API Log: {ex}")

    def _classify_intent(self, query, history):
        """Classifies user queries into semantic intents."""
        query_lower = query.lower().strip()
        
        # 1. Profile Context
        if any(k in query_lower for k in ["i know", "my skills", "learned", "experience in", "comfortable with", "java", "flask", "python", "javascript", "c++"]):
            if "what is" not in query_lower and "explain" not in query_lower and "question" not in query_lower and "roadmap" not in query_lower and "prepare" not in query_lower:
                return "Profile Context"
                
        # 2. Roadmap
        if any(k in query_lower for k in ["roadmap", "prepare for", "study plan", "how to prepare", "preparation path"]):
            return "Roadmap"
            
        # 3. Interview Questions
        if any(k in query_lower for k in ["interview question", "ask me questions", "ask question", "generate questions", "give me questions"]):
            return "Interview Questions"
            
        # 4. Mock Interview Mode
        if any(k in query_lower for k in ["mock interview", "conduct a mock", "start mock", "interview me"]):
            return "Mock Interview Mode"

        # 5. Soft Skills Guidance
        if any(k in query_lower for k in ["communicate", "soft skills", "speaking", "filler", "tell me about yourself", "how should i answer"]):
            return "Soft Skills Guidance"

        # 6. Concept Explanation (default for technical terms)
        if any(k in query_lower for k in ["what is", "explain", "how does", "why does", "tell me about", "concept", "array", "linked list", "stack", "queue", "binary search", "recursion", "dynamic programming"]):
            return "Concept Explanation"
            
        return "Concept Explanation"

    def _evaluate_response_quality(self, query, reply, history):
        """Evaluates whether the response is relevant, non-repetitive, and sufficient."""
        # 1. Length Check
        if len(query.split()) > 3 and len(reply) < 100:
            return False, "Length check failed: response is too short."

        # 2. Repetition check against history
        last_ai_replies = [m["content"] for m in history if m["sender"] in ("ai", "assistant")]
        if last_ai_replies:
            last_reply = last_ai_replies[-1].strip()
            if reply.strip() == last_reply:
                return False, "Repetition check failed: exact copy of previous response."
                
            words_last = set(re.findall(r'\b\w+\b', last_reply.lower()))
            words_new = set(re.findall(r'\b\w+\b', reply.lower()))
            if len(words_last) > 10 and len(words_new) > 10:
                intersection = words_last.intersection(words_new)
                similarity = len(intersection) / max(len(words_last), len(words_new))
                if similarity > 0.85:
                    return False, f"Repetition check failed: high word overlap ({similarity:.2f}) with previous response."
                    
        # 3. Relevance Check
        query_words = set(re.findall(r'\b\w+\b', query.lower()))
        important_subjects = {"array", "stack", "queue", "linked list", "recursion", "binary search", "dynamic programming", "amazon", "google", "microsoft", "java", "flask"}
        matched_subjects = query_words.intersection(important_subjects)
        
        if matched_subjects:
            reply_lower = reply.lower()
            if not any(s in reply_lower for s in matched_subjects):
                return False, f"Relevance check failed: response does not contain query subjects: {matched_subjects}"

        return True, "Quality check passed."

    def _get_system_prompt(self, template_name):
        return self.TEMPLATES.get(template_name, self.TEMPLATES["Concept Tutor"])

    def _prepare_groq_history(self, messages, system_prompt):
        """Prepares history format suitable for Groq chat completions."""
        contents = [{"role": "system", "content": system_prompt}]
        for msg in messages:
            role = "user" if msg["sender"] == "user" else "assistant"
            contents.append({"role": role, "content": msg["content"]})
        return contents

    def _call_claude_api(self, system_prompt, messages):
        """Calls Anthropic Claude Messages API via requests library."""
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.claude_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        
        formatted_messages = []
        for msg in messages:
            formatted_messages.append({
                "role": "user" if msg["sender"] == "user" else "assistant",
                "content": msg["content"]
            })
            
        if not formatted_messages:
            formatted_messages.append({"role": "user", "content": "Hello"})
            
        body = {
            "model": "claude-3-5-sonnet-20241022",
            "max_tokens": 1024,
            "system": system_prompt,
            "messages": formatted_messages
        }
        
        response = requests.post(url, headers=headers, json=body, timeout=15)
        if response.status_code == 200:
            data = response.json()
            return data["content"][0]["text"].strip()
        else:
            print(f"Claude API Error: {response.status_code} - {response.text}")
            return None

    def _local_fallback_response_dynamic(self, intent, query, history, user_profile, resume_skills):
        """Dynamically generates fallback responses without static templates."""
        query_lower = query.lower().strip()
        name = user_profile.get("full_name", "Student")
        
        topics = []
        if "array" in query_lower:
            topics.append("Arrays")
        if "linked list" in query_lower:
            topics.append("Linked Lists")
        if "stack" in query_lower:
            topics.append("Stacks")
        if "queue" in query_lower:
            topics.append("Queues")
        if "binary search" in query_lower:
            topics.append("Binary Search")
        if "recursion" in query_lower:
            topics.append("Recursion")
        if "dynamic programming" in query_lower or "dp" in query_lower:
            topics.append("Dynamic Programming")
        if "tree" in query_lower:
            topics.append("Trees")
        if "graph" in query_lower:
            topics.append("Graphs")
        if "sorting" in query_lower or "sort" in query_lower:
            topics.append("Sorting Algorithms")
            
        topic = topics[0] if topics else "Placement Preparation"
        
        if intent == "Profile Context":
            skills_str = ", ".join(resume_skills) if resume_skills else "Java and Flask"
            if "java" in query_lower or "flask" in query_lower:
                skills_str = "Java and Flask"
            return f"""### Profile Context Saved

Hello {name}! I have updated your mentor profile. I now remember that you are comfortable working with **{skills_str}**.

To align with this profile, I will tailor our coding, DSA, and project review discussions to focus on backend architecture, REST API design in Flask, and object-oriented principles in Java.

What would you like to prepare next using **{skills_str}**?"""

        elif intent == "Roadmap":
            company = "Amazon" if "amazon" in query_lower else "Google" if "google" in query_lower else "Microsoft" if "microsoft" in query_lower else "Tier-1 Tech"
            return f"""### Placement Preparation Roadmap: Targeting {company}

To successfully crack a technical role at **{company}**, follow this structured preparation roadmap:

1. **Step 1: Core Language & Fundamentals**:
   - Master language concepts (e.g. Java, Python, or C++ object-oriented designs).
2. **Step 2: High-Frequency Data Structures**:
   - Practice operations on Arrays, Strings, Hashing, and Linked Lists.
3. **Step 3: Advanced Algorithms**:
   - Cover Binary Search, BFS/DFS, Heaps, and Dynamic Programming (extremely high frequency for {company}).
4. **Step 4: Company-Specific Focus**:
   - Focus on {company}'s design philosophy (e.g., Leadership Principles for Amazon, system scalability for Google).

Would you like to practice a specific sample question for {company} now?"""

        elif intent == "Interview Questions":
            if "array" in query_lower:
                return f"""### Interview Questions on Arrays

Here are three high-frequency interview questions focusing on Arrays:

1. **Two Sum**: Find two numbers in a sorted array that add up to a target sum. (Complexity: $O(N)$ time, $O(N)$ space using a Hash Map).
2. **Maximum Subarray**: Find the contiguous subarray within a 1D array of numbers which has the largest sum (Kadane's Algorithm: $O(N)$ time, $O(1)$ space).
3. **Merge Intervals**: Given a collection of intervals, merge all overlapping intervals ($O(N \\log N)$ time due to sorting).

Which of these would you like to solve or discuss in detail?"""
            else:
                return f"""### Technical Interview Questions: {topic}

Here are some standard interview questions for **{topic}**:

1. Explain the underlying mechanism of {topic} and how it manages data in memory.
2. Outline the typical time and space complexities for core operations in {topic}.
3. Describe a real-world system or application where {topic} is preferred over alternative structures.

How would you answer the first question? I can evaluate your response!"""

        # Concept Explanation (default)
        if "binary search" in query_lower:
            return r"""### Concept Tutor: Binary Search

#### Definition
Binary Search is an efficient search algorithm used to find the position of a target value within a **sorted array**. It works by repeatedly dividing the search space in half.

#### Time & Space Complexity
*   **Time Complexity**: $O(\log N)$ average and worst-case, as the search interval is halved at each step.
*   **Space Complexity**: $O(1)$ for the iterative approach.

#### Example (Python)
```python
def binary_search(arr, target):
    low, high = 0, len(arr) - 1
    while low <= high:
        mid = (low + high) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            low = mid + 1
        else:
            high = mid - 1
    return -1
```

Would you like to write an implementation of Binary Search, or analyze how it compares to Linear Search?"""

        elif "array" in query_lower:
            return r"""### Concept Tutor: Arrays

#### Definition
An Array is a sequential data structure that stores elements of the same type at contiguous memory locations. It is the most fundamental structure in computer science.

#### Time & Space Complexity
| Operation | Time Complexity | Space Complexity |
| :--- | :--- | :--- |
| **Access** | $O(1)$ | $O(1)$ |
| **Search** | $O(N)$ | $O(1)$ |
| **Insertion** | $O(N)$ | $O(1)$ |
| **Deletion** | $O(N)$ | $O(1)$ |

#### Python Representation
```python
# Creating an array in Python
arr = [10, 20, 30, 40]
print(arr[2])  # Output: 30 (O(1) access)
```

Can you explain why search in an unsorted array takes $O(N)$ time complexity?"""

        else:
            return f"""### Concept Tutor: {topic}

#### Overview
{topic} is a key concept in computer science and placement interviews.

#### Core Principles
- **Efficiency**: Designed to optimize execution speed or memory constraints.
- **Application**: Crucial for building complex algorithms.

#### Real-world Use Case
Used in backend databases, routing algorithms, or application state management.

Would you like to practice a coding problem on {topic}, or check standard interview questions for this topic?"""

    def _generate_suggestions(self, topic, text):
        """Generates 3 contextual suggested follow-up questions for the user."""
        text_lower = text.lower()
        if "dsa" in topic or "concept" in topic:
            if "binary search" in text_lower:
                return ["Explain Binary Search complexity", "Show Python code for Binary Search", "Learn about Merge Sort next"]
            elif "recursion" in text_lower:
                return ["Explain recursion vs iteration", "Show code for Fibonacci series", "Learn about Stack data structure"]
            elif "linked list" in text_lower:
                return ["Show Python code for Linked List Node", "Difference between Singly and Doubly lists", "What are common Linked List questions?"]
            elif "array" in text_lower:
                return ["Show coding questions on arrays", "Difference between array and list", "What is binary search?"]
            else:
                return ["Explain Binary Search", "Explain Recursion", "Give me a 30-day DSA roadmap"]
        elif "resume" in topic or "profile" in topic:
            return ["Give me resume formatting tips", "How to write the Google X-Y-Z bullet", "Review project section details"]
        elif "interview" in topic:
            return ["Practice teammate conflict question", "Explain the STAR method", "How to answer strength & weakness?"]
        elif "skills" in topic or "behavioral" in topic:
            return ["How to speak at 130 WPM?", "How to reduce filler words?", "Explain active listening tips"]
        elif "roadmap" in topic:
            return ["Give me a 30-day DSA roadmap", "How to split prep daily?", "Tips to handle interview stress"]
        else:
            return ["Explain arrays", "Explain recursion", "How to improve communication?"]

    def generate_response(self, mode, history_messages, system_context=None):
        """Generates contextual turn-based chatbot response."""
        import traceback
        
        # 1. Resolve user ID for debug telemetry
        user_id = None
        try:
            from flask_login import current_user
            if current_user and current_user.is_authenticated:
                user_id = current_user.id
        except Exception:
            pass

        # 2. Extract current user message (last message in list)
        user_msg = ""
        for m in reversed(history_messages):
            if m["sender"] == "user":
                user_msg = m["content"].strip()
                break

        # 3. Retrieve historical context (last 15 messages excluding current one)
        previous_history = [m for m in history_messages[:-1]]
        history_to_use = previous_history[-15:] if len(previous_history) > 15 else previous_history

        # 4. Intent Classification
        intent = self._classify_intent(user_msg, history_to_use)
        
        # Determine prompt template
        template_name = "Concept Tutor"
        if intent == "Interview Questions":
            template_name = "Interview Coach"
        elif intent == "Profile Context":
            template_name = "Resume Mentor"
        elif intent == "Roadmap":
            template_name = "Interview Coach"
        elif intent == "Mock Interview Mode":
            template_name = "Mock Interviewer"
        elif intent == "Soft Skills Guidance":
            template_name = "Behavioral Mentor"

        # 5. Load User Profile & Resume Context
        user_profile = {}
        try:
            from flask_login import current_user
            if current_user and current_user.is_authenticated:
                user_profile = {
                    "username": current_user.username,
                    "full_name": current_user.full_name or current_user.username,
                    "skill_level": current_user.skill_level or "Beginner",
                    "average_score": current_user.average_score or 0.0,
                    "highest_score": current_user.highest_score or 0.0
                }
        except Exception as e:
            print(f"Error loading user profile: {e}")

        resume_context = "No resume uploaded yet."
        resume_skills = []
        try:
            from flask_login import current_user
            if current_user and current_user.is_authenticated:
                from models.resume_upload import ResumeUpload
                resume = ResumeUpload.query.filter_by(user_id=current_user.id).order_by(ResumeUpload.created_at.desc()).first()
                if resume:
                    resume_context = f"Skills Extracted: {resume.skills_extracted}\nProjects: {resume.projects}"
                    if resume.skills_extracted:
                        resume_skills = [s.strip() for s in resume.skills_extracted.split(",") if s.strip()]
        except Exception as e:
            print(f"Error loading resume: {e}")

        # 6. Compose system instructions
        base_prompt = self._get_system_prompt(template_name)
        context_prompt = f"""{base_prompt}

You are HireWise Mentor, an intelligent placement preparation assistant.
You remember previous messages.
You answer only according to the current query.
You ask follow-up questions when necessary.
You avoid repetitive responses.
You explain concepts with examples and interview perspective.

Current User Profile:
- Name: {user_profile.get('full_name', 'Student')}
- Skill Level: {user_profile.get('skill_level', 'Beginner')}
- Average Interview Score: {user_profile.get('average_score', 0.0)}%
- Highest Interview Score: {user_profile.get('highest_score', 0.0)}%

User Resume Details:
{resume_context}

Classified User Intent: {intent}
"""

        # Prepare generation variables
        provider = "local"
        model = "rule-based-agent"
        reply_text = ""
        prompt_tokens = 0
        fallback_triggered = True
        fallback_reason = "No API keys available"
        error_msg = ""
        start_time = time.time()

        # Track exceptions for diagnostics
        caught_exception = None
        caught_traceback = ""

        # 7. Call LLM Providers (Groq Priority)
        if self.groq_initialized:
            provider = "groq"
            model = self.model_name
            fallback_triggered = False
            fallback_reason = "N/A"
            
            for attempt in range(2):
                try:
                    enhanced_system_prompt = context_prompt
                    if attempt > 0:
                        enhanced_system_prompt += "\n\nCRITICAL: Your previous response failed quality checks (too short, repetitive, or irrelevant). Please write a completely unique, comprehensive, and detail-oriented answer addressing the user query, and avoid repeating previous answers."
                        
                    messages = self._prepare_groq_history(history_to_use, enhanced_system_prompt)
                    messages.append({"role": "user", "content": user_msg})
                    
                    try:
                        response = self.client.chat.completions.create(
                            model=self.model_name,
                            messages=messages
                        )
                        model_used = self.model_name
                    except Exception as rate_err:
                        error_str = str(rate_err)
                        if "429" in error_str or "rate_limit" in error_str:
                            print("[INFO] Rate limit hit on 70B model. Retrying with llama-3.1-8b-instant...")
                            response = self.client.chat.completions.create(
                                model="llama-3.1-8b-instant",
                                messages=messages
                            )
                            model_used = "llama-3.1-8b-instant"
                        else:
                            raise rate_err
                            
                    prompt_tokens = response.usage.prompt_tokens if hasattr(response, 'usage') and response.usage else 0
                    reply_text = response.choices[0].message.content.strip()
                    
                    # Quality Check
                    is_ok, quality_msg = self._evaluate_response_quality(user_msg, reply_text, history_to_use)
                    if is_ok:
                        model = model_used
                        break
                    else:
                        print(f"[QUALITY ALERT] Groq Attempt {attempt+1} failed check: {quality_msg}")
                        error_msg = quality_msg
                        if attempt == 1:
                            reply_text = ""
                            fallback_triggered = True
                            fallback_reason = f"Quality check failed: {quality_msg}"
                except Exception as e:
                    error_msg = str(e)
                    caught_exception = e
                    caught_traceback = traceback.format_exc()
                    print(f"[ERROR] Groq API call crashed: {e}")
                    fallback_triggered = True
                    fallback_reason = "Groq API Exception"
                    reply_text = ""
                    break

        # Fallback to Claude if Groq failed/not available
        if (not reply_text or fallback_triggered):
            # Print Mentor Debug before fallback
            print("========== MENTOR DEBUG ==========")
            print("User message:", user_msg)
            print("Provider:", provider)
            print("Groq initialized:", self.groq_initialized)
            print("Exception:", caught_exception)
            print(caught_traceback.strip())
            print("=================================")

            if self.claude_key:
                provider = "claude"
                model = "claude-3-5-sonnet-20241022"
                fallback_triggered = False
                fallback_reason = "N/A"
                
                for attempt in range(2):
                    try:
                        enhanced_system_prompt = context_prompt
                        if attempt > 0:
                            enhanced_system_prompt += "\n\nCRITICAL: Avoid repetition and write a detailed response."
                            
                        messages_to_send = history_to_use + [{"sender": "user", "content": user_msg}]
                        reply_text = self._call_claude_api(enhanced_system_prompt, messages_to_send)
                        
                        if reply_text:
                            is_ok, quality_msg = self._evaluate_response_quality(user_msg, reply_text, history_to_use)
                            if is_ok:
                                break
                            else:
                                print(f"[QUALITY ALERT] Claude Attempt {attempt+1} failed check: {quality_msg}")
                                error_msg = quality_msg
                                if attempt == 1:
                                    reply_text = ""
                                    fallback_triggered = True
                                    fallback_reason = f"Quality check failed: {quality_msg}"
                    except Exception as e:
                        error_msg = str(e)
                        caught_exception = e
                        caught_traceback = traceback.format_exc()
                        print(f"[ERROR] Claude API call crashed: {e}")
                        fallback_triggered = True
                        fallback_reason = "Claude API Exception"
                        reply_text = ""
                        break

        # Baseline: Local Fallback
        if not reply_text:
            # Print Mentor Debug before fallback
            print("========== MENTOR DEBUG ==========")
            print("User message:", user_msg)
            print("Provider:", provider)
            print("Groq initialized:", self.groq_initialized)
            print("Exception:", caught_exception)
            print(caught_traceback.strip())
            print("=================================")

            provider = "local"
            model = "rule-based-agent"
            fallback_triggered = True
            reply_text = self._local_fallback_response_dynamic(intent, user_msg, history_to_use, user_profile, resume_skills)

        duration = time.time() - start_time
        suggestions = self._generate_suggestions(intent.lower(), reply_text)

        # 8. Store Debug Telemetry
        if user_id:
            # Reconstruct sent prompt payload summary
            prompt_summary = f"System Instruction: {context_prompt}\nHistory Injected Count: {len(history_to_use)}\nUser Query: {user_msg}"
            LAST_DEBUG_INFO[user_id] = {
                "current_provider": provider,
                "model": model,
                "prompt_sent": prompt_summary,
                "history_count": len(history_to_use),
                "generated_response": reply_text,
                "fallback_reason": fallback_reason if fallback_triggered else "N/A",
                "errors": error_msg or "None"
            }

        # 9. Custom Console Logging (Task 7)
        print("\n" + "="*50)
        print(f"User Query: {user_msg}")
        print(f"Intent: {intent}")
        print(f"History Count: {len(history_to_use)}")
        print(f"Provider: {provider}")
        print(f"Model: {model}")
        print(f"Prompt: {user_msg}")
        print(f"Response: {reply_text}")
        print(f"Errors: {error_msg or 'None'}")
        print("="*50 + "\n")

        # Log to DB APILog
        self._log_api_call(provider=provider, endpoint=model, response_time=duration, is_success=not fallback_triggered)

        return reply_text, provider, suggestions
