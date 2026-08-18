import os
import re
from config import Config
from services.transcription_service import transcribe_audio

SR_INSTALLED = False
try:
    import speech_recognition as sr
    SR_INSTALLED = True
except ImportError:
    print("speech_recognition not installed. Falling back to browser-side transcription.")

class WhisperService:
    def __init__(self):
        self.model = None
        self.model_name = Config.WHISPER_MODEL_NAME

    def transcribe(self, audio_path, browser_transcript_fallback=None):
        """
        Transcribes the given audio file using:
        1. Groq Whisper Cloud API (via transcription_service)
        2. Google Web Speech API via SpeechRecognition (as online fallback)
        3. Browser-provided transcript (fallback passed from client)
        """
        audio_path = str(audio_path)
        
        if not os.path.exists(audio_path):
            print(f"Audio file not found: {audio_path}")
            return browser_transcript_fallback or "Audio file missing."
            
        # 1. Try Groq Whisper Cloud transcription
        try:
            text = transcribe_audio(audio_path)
            if text:
                return text
        except Exception as e:
            print(f"Groq Cloud transcription failed: {e}. Trying secondary methods.")
                    
        # 2. Try SpeechRecognition (Google API - online & lightweight)
        if SR_INSTALLED:
            try:
                r = sr.Recognizer()
                with sr.AudioFile(audio_path) as source:
                    audio_data = r.record(source)
                text = r.recognize_google(audio_data)
                if text:
                    return text.strip()
            except Exception as e:
                print(f"Google speech recognition fallback failed: {e}. Using browser fallback.")
                
        # 3. Fall back to frontend browser transcript if present
        if browser_transcript_fallback:
            return browser_transcript_fallback.strip()
            
        return "[Unable to transcribe audio response. Please check microphone settings or check internet connectivity.]"

    def analyze_speech(self, transcript, duration):
        """
        Calculates:
        - Words Per Minute (WPM)
        - Count of specific filler words (umm, uh, like, actually, basically, you know, matlab)
        - Fluency tips and feedback
        """
        if not transcript or duration <= 0:
            return {
                "word_count": 0,
                "wpm": 0,
                "filler_count": 0,
                "filler_details": {},
                "duration": duration,
                "suggestions": "No speech detected. Try speaking closer to your microphone."
            }
            
        words = transcript.lower().split()
        word_count = len(words)
        
        # Calculate WPM
        wpm = int((word_count / duration) * 60)
        
        # Filler word list
        fillers = ["umm", "uh", "like", "actually", "basically", "you know", "matlab", "um", "uhh"]
        filler_details = {f: 0 for f in fillers}
        total_fillers = 0
        
        # Clean text for word matching
        cleaned_text = re.sub(r'[^\w\s]', '', transcript.lower())
        
        # Check standard words
        for word in cleaned_text.split():
            if word in filler_details:
                filler_details[word] += 1
                total_fillers += 1
                
        # Handle compound phrase "you know" separately
        yk_count = cleaned_text.count("you know")
        if yk_count > 0:
            filler_details["you know"] = yk_count
            total_fillers += yk_count
            # Adjust if single words "you" and "know" were somehow counted (usually not an issue)
            
        # Filter details to show only occurred fillers
        active_fillers = {k: v for k, v in filler_details.items() if v > 0}
        
        # Evaluate speech rate
        # Professional standard: 120 - 150 WPM
        rate_feedback = ""
        if wpm < 80:
            rate_feedback = "Your speaking speed is very slow (below 80 WPM). Try to speak more fluently and confidently."
        elif 80 <= wpm < 110:
            rate_feedback = "Your speaking speed is slightly slow. Try to pick up the pace slightly."
        elif 110 <= wpm <= 150:
            rate_feedback = "Excellent! Your speaking speed is in the ideal range of 110-150 WPM."
        else:
            rate_feedback = "Your speaking speed is very fast (above 150 WPM). Take deep breaths and slow down to maintain clarity."
            
        # Evaluate fillers
        filler_ratio = total_fillers / (word_count / 100) if word_count > 0 else 0
        filler_feedback = ""
        if total_fillers == 0:
            filler_feedback = "Great job! You did not use any common filler words. This shows high articulation."
        elif filler_ratio < 3:
            filler_feedback = "You kept filler words minimal. Good control over pauses."
        else:
            filler_feedback = f"Filler words represent {filler_ratio:.1f}% of your speech. Try replacing words like '{', '.join(active_fillers.keys())}' with silent pauses."
            
        suggestions = f"{rate_feedback} {filler_feedback}"
        
        return {
            "word_count": word_count,
            "wpm": wpm,
            "filler_count": total_fillers,
            "filler_details": active_fillers,
            "duration": round(duration, 1),
            "suggestions": suggestions
        }
