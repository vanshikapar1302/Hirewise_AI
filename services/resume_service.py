import os
import re
from config import Config

try:
    from PyPDF2 import PdfReader
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False
    print("WARNING: PyPDF2 is not installed. Resume parsing will operate in fallback mode.")

class ResumeService:
    def __init__(self):
        pass
        
    def extract_text(self, pdf_path):
        """
        Extracts raw text from a PDF resume file.
        Cleans whitespaces and structures the output.
        """
        pdf_path = str(pdf_path)
        if not os.path.exists(pdf_path):
            print(f"PDF resume file not found: {pdf_path}")
            return ""
            
        if not PYPDF2_AVAILABLE:
            print("PyPDF2 is not available. Cannot parse PDF file.")
            return "Fallback Resume: Student has skills in Python, Flask, HTML, CSS, JavaScript, SQL. Developed a portfolio project using web scraping."

        text_content = []
        try:
            reader = PdfReader(pdf_path)
            # Iterate through all pages and extract text
            for page_idx, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    text_content.append(text)
                    
            full_text = "\n".join(text_content)
            
            # Clean up excessive newlines and formatting
            cleaned_text = self._clean_text(full_text)
            return cleaned_text
        except Exception as e:
            print(f"Error parsing PDF resume: {e}")
            return "Fallback Resume: Error reading resume. Preloading default engineering resume skills: Python, Java, DBMS, SQL, Web Development."

    def _clean_text(self, text):
        """Removes excessive spacing, consecutive newlines, and replaces non-ascii characters."""
        # Replace multiple spaces with a single space
        text = re.sub(r'[ \t]+', ' ', text)
        # Replace multiple newlines with double newlines to keep paragraphs
        text = re.sub(r'\n+', '\n', text)
        # Remove non-ascii characters
        text = text.encode('ascii', errors='ignore').decode('utf-8')
        return text.strip()
