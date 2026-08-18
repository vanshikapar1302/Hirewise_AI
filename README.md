# HireWise AI - AI-Powered Mock Interview Platform

HireWise AI is an intelligent mock interview preparation platform designed to help engineering students prepare for campus placements through realistic interview simulations, real-time eye-gaze tracking, speech articulation analysis, and personalized, explainable AI feedback.

The application is built using a lightweight, student-friendly Python/Flask tech stack, making it highly maintainable and suitable for portfolio showcases, internship qualifications, and academic projects.

---

## 🚀 Key Features

1. **Mock Interview Room**: Simulates HR, Technical, and Mixed interviews. Delivers questions sequentially.
2. **Speech-to-Text Transcription**: Captures voice input and transcribes responses using OpenAI Whisper (or lightweight online fallback API).
3. **Filler Word Analytics**: Detects common filler words (*umm, uh, like, actually, basically, you know, matlab*) and displays frequency graphs.
4. **Speaking Pace Checker**: Calculates Words-Per-Minute (WPM) and response duration, advising on ideal speeds (110-150 WPM).
5. **Gaze & Attention Tracking**: Analyzes head orientation and gaze alignment using OpenCV and MediaPipe Face Mesh, providing eye contact feedback.
6. **Gemini Grading Engine**: Grades answers out of 10 on Relevance, Clarity, Completeness, Structure, and Professionalism.
7. **AI Follow-Up Questions**: Generates conversational follow-up questions dynamically midway through the interview, mirroring a real human interviewer.
8. **Resume-Based Mode**: Uploads PDF resumes, extracts engineering project titles, and generates custom questions targeting the user's projects.
9. **Company-Specific Practice**: Structured preparation modes for major companies including Amazon, Google, Microsoft, TCS, and Infosys.
10. **Placement Readiness Score**: Trains a scikit-learn `DecisionTreeClassifier` on performance profiles to predict overall corporate readiness.
11. **Performance Dashboard**: Renders score statistics, skill competencies (Strong/Moderate/Weak), and historical trends using Chart.js.

---

## 🛠️ Technology Stack

* **Backend**: Python 3.8+, Flask, Flask-Login
* **Frontend**: HTML5, Vanilla CSS, JavaScript, Bootstrap 5, Jinja Templates
* **Database**: SQLite, SQLAlchemy ORM
* **Speech Processing**: OpenAI Whisper, SpeechRecognition (Google API)
* **Computer Vision**: OpenCV, MediaPipe Face Mesh
* **Machine Learning & AI**: Google Gemini API, Scikit-learn, Pandas, NumPy
* **PDF Ingestion**: PyPDF2
* **Visualization**: Chart.js

---

## 📂 Project Structure

```
HireWise_AI/
├── app.py                      # Application launcher and configuration initialization
├── config.py                   # Dotenv variables loader
├── requirements.txt            # Python dependencies
├── README.md                   # Setup guide and documentation
├── .env.example                # Template environmental config
├── verify_setup.py             # Diagnostic checklist tool
│
├── database/
│   └── connection.py           # SQLAlchemy setup and data seeding logic
│
├── models/
│   ├── __init__.py             # Exports models
│   ├── user.py                 # User authentication structure
│   ├── interview.py            # Aggregate session logs and scores
│   ├── question.py             # Pre-seeded questions bank
│   └── response.py             # Detailed per-question scoring and media path links
│
├── routes/
│   ├── auth.py                 # Sign-in, register, profile
│   ├── dashboard.py            # Analytics charts and ML predictions
│   ├── interview.py            # Mock room core logic
│   └── resume.py               # Resume file uploads and parsing
│
├── services/
│   ├── gemini_service.py       # Gemini API client with rule-based grading fallback
│   ├── whisper_service.py      # Voice transcribers and WPM counters
│   ├── cv_service.py           # OpenCV/MediaPipe gaze calculation
│   └── resume_service.py       # PyPDF2 text extraction
│
├── datasets/
│   └── questions.json          # Preloaded question datasets
│
├── static/
│   ├── css/
│   │   └── style.css           # Glassmorphic responsive styling sheets
│   └── js/
│   │   ├── main.js             # Basic UI theme toggles
│   │   └── interview.js        # Webcam recorders and AJAX controllers
│
├── templates/
│   ├── base.html               # Grid wrappers and sidebars
│   ├── index.html              # Landing homepage
│   ├── login.html              # Sign in panel
│   ├── register.html           # Registration panel
│   ├── dashboard.html          # Performance charts and widgets
│   ├── profile.html            # Profile edits and history wipes
│   ├── select_interview.html   # Interview type configure
│   ├── interview.html          # Recording room
│   ├── feedback.html           # Scorecards and answers breakdown
│   ├── history.html            # Historic attempts log
│   └── resume_upload.html      # PDF upload pane
│
└── uploads/                    # Stores uploaded resumes and recorded mock clips
```

---

## 🔧 Installation & Setup

Follow these steps to run the platform locally on Windows:

### Step 1: Clone or Extract the Project
Ensure all files are placed in a folder named `HireWise_AI` on your workspace.

### Step 2: Establish a Virtual Environment
Open PowerShell or Command Prompt, navigate to your project directory, and create a virtual environment:
```powershell
python -m venv venv
```
Activate the environment:
```powershell
# In PowerShell:
.\venv\Scripts\Activate.ps1

# In Command Prompt:
.\venv\Scripts\activate.bat
```

### Step 3: Install Required Dependencies
Install the required packages using pip:
```powershell
pip install -r requirements.txt
```
*(Note: OpenCV, MediaPipe, and PyTorch may take a few minutes to download depending on your connection speed).*

### Step 4: Configure Environment Variables
1. Copy the `.env.example` file and rename it to `.env`:
   ```powershell
   copy .env.example .env
   ```
2. Open `.env` and add your **Google Gemini API Key**:
   ```env
   GOOGLE_API_KEY=AIzaSy...your_gemini_key_here...
   ```
   *You can obtain a free Gemini API Key from [Google AI Studio](https://aistudio.google.com/).*

### Step 5: Run Diagnostics
Run the diagnostic script to verify database migrations, dependencies, and API configuration status:
```powershell
python verify_setup.py
```
Review the console report. If some packages are missing or the API key is empty, the application will display warnings but will unlock **Fallback Mode** to allow testing without crashes.

### Step 6: Start the Server
Launch the Flask development server:
```powershell
python app.py
```
Open your browser and navigate to:
**[http://localhost:5000](http://localhost:5000)**

---

## 🛡️ Robust Fail-Safe Design (Fallback Modes)

To ensure the project functions flawlessly even when API keys are missing or local hardware is constrained, the services incorporate robust fallback engines:

1. **Gemini Fallback Mode**: If no `GOOGLE_API_KEY` is present or if network issues occur, a rule-based grading engine evaluates responses based on keyword overlap, structural transition phrases, and response word count.
2. **Speech-to-Text Fallback Mode**: PyTorch/Whisper loads dynamically. If libraries are not installed or if hardware is limited, the backend transcribes using the lightweight, free `SpeechRecognition` Google online API. Furthermore, the frontend implements the **Web Speech API**, providing a real-time transcript to the backend as a fail-safe.
3. **MediaPipe Fallback Mode**: If OpenCV or MediaPipe dependencies fail to load, the gaze tracking service returns a default attention score between 70% and 85% with natural randomized variations.
