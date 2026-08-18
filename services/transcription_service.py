import os
import time
from config import Config

# Initialize Groq client
GROQ_API_KEY = getattr(Config, 'GROQ_API_KEY', '') or os.environ.get("GROQ_API_KEY", "")
GROQ_WHISPER_MODEL = os.environ.get("GROQ_WHISPER_MODEL", "whisper-large-v3")

client = None
if GROQ_API_KEY:
    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        print("[INFO] Groq client initialized in transcription service.")
    except Exception as e:
        print(f"[ERROR] Failed to initialize Groq client in transcription service: {e}")

def transcribe_file(file_path: str, retries: int = 3, timeout_secs: float = 30.0) -> str:
    """Sends audio/video file to Groq Whisper API with retry logic and rate limit handling."""
    if not file_path or not os.path.exists(file_path):
        print(f"[WARNING] Transcription failed: File not found at '{file_path}'")
        return ""

    if not client:
        print("[WARNING] Groq transcription client is not initialized.")
        return ""

    # Supported audio/video formats for Groq Whisper
    filename = os.path.basename(file_path)
    ext = os.path.splitext(filename)[1].lower()
    supported_exts = {".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm"}
    if ext not in supported_exts:
        print(f"[WARNING] Extension '{ext}' might not be supported by Groq Whisper API.")

    backoff = 2.0
    for attempt in range(retries):
        try:
            with open(file_path, "rb") as file:
                # Call Groq audio transcription API
                transcription = client.audio.transcriptions.create(
                    file=(filename, file.read()),
                    model=GROQ_WHISPER_MODEL,
                    response_format="json",
                    temperature=0.0
                )
                text = getattr(transcription, 'text', '').strip()
                if text:
                    return text
        except Exception as e:
            error_str = str(e)
            print(f"[ERROR] Groq Whisper API error (Attempt {attempt + 1}/{retries}): {error_str}")
            
            # Check rate limits (HTTP 429)
            if "429" in error_str or "rate_limit_exceeded" in error_str:
                # Sleep and retry with longer backoff
                sleep_time = backoff * (attempt + 1)
                print(f"[INFO] Rate limit hit. Retrying in {sleep_time} seconds...")
                time.sleep(sleep_time)
            elif "401" in error_str or "invalid_api_key" in error_str:
                # Do not retry on auth failures
                break
            else:
                # For other errors, sleep slightly and retry
                time.sleep(1.0)
                
    return ""

def transcribe_audio(file_path: str) -> str:
    """Transcribes an audio file (e.g. .wav, .webm, .mp3) using Groq Whisper API."""
    print(f"[INFO] Transcribing audio file: {file_path}")
    return transcribe_file(file_path)

def transcribe_video(file_path: str) -> str:
    """Transcribes a video file (e.g. .mp4, .webm) using Groq Whisper API."""
    print(f"[INFO] Transcribing video file: {file_path}")
    return transcribe_file(file_path)
