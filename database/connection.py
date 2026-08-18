import json
from pathlib import Path
from flask_sqlalchemy import SQLAlchemy

# Instantiate the SQLAlchemy object
db = SQLAlchemy()

def init_db(app):
    """Initialize database and create all tables if they don't exist."""
    db.init_app(app)
    
    with app.app_context():
        # Import models so they are registered with SQLAlchemy
        from models.user import User
        from models.interview import InterviewSession
        from models.question import Question
        from models.response import Response
        from models.role import Role
        from models.admin_user import AdminUser
        from models.admin_notification import AdminNotification
        from models.email_log import EmailLog
        from models.skill_state import SessionSkillState, SessionSkillHistory
        from models.admin_log import AdminLog
        from models.settings import Settings
        from models.resume import Resume
        from models.interview_response import InterviewResponse

        
        # Drop legacy unused tables if their columns mismatch the new schema
        try:
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            if 'interview_responses' in tables:
                cols = [c['name'] for c in inspector.get_columns('interview_responses')]
                if 'session_id' in cols or 'question_text' in cols or 'transcript' in cols:
                    db.session.execute(db.text("DROP TABLE interview_responses"))
                    db.session.commit()
                    print("Dropped legacy unused interview_responses table.")
            if 'resumes' in tables:
                cols = [c['name'] for c in inspector.get_columns('resumes')]
                if 'filename' in cols or 'created_at' in cols or 'parsed_text' in cols:
                    db.session.execute(db.text("DROP TABLE resumes"))
                    db.session.commit()
                    print("Dropped legacy unused resumes table.")
        except Exception as e_migration:
            db.session.rollback()
            print(f"Error during legacy table cleanup: {e_migration}")

        # Create all tables
        db.create_all()
        print("Database tables created successfully.")
        
        # Auto-migrations using SQLAlchemy Inspector for robustness
        try:
            inspector = db.inspect(db.engine)
            
            def add_column_if_missing(table_name, col_name, col_type):
                try:
                    existing_cols = [c['name'] for c in inspector.get_columns(table_name)]
                    if col_name not in existing_cols:
                        db.session.execute(db.text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}"))
                        db.session.commit()
                        print(f"Successfully added column {col_name} to {table_name} table.")
                    else:
                        print(f"Column {col_name} already exists in {table_name} table.")
                except Exception as ex:
                    db.session.rollback()
                    print(f"Error adding column {col_name} to {table_name}: {ex}")

            # 1. resume_uploads table
            add_column_if_missing("resume_uploads", "custom_questions", "TEXT")

            # 2. questions table research columns
            add_column_if_missing("questions", "skill", "VARCHAR(50) DEFAULT NULL")
            add_column_if_missing("questions", "subtopic", "VARCHAR(50) DEFAULT NULL")
            add_column_if_missing("questions", "prerequisite_skills", "TEXT DEFAULT '[]'")

            # 3. interview_sessions table progression columns
            columns_to_add = [
                ("question_ids", "TEXT DEFAULT '[]'"),
                ("current_index", "INTEGER DEFAULT 0"),
                ("asked_follow_up", "BOOLEAN DEFAULT FALSE"),
                ("last_question_id", "INTEGER DEFAULT NULL"),
                ("last_question_text", "TEXT DEFAULT NULL"),
                ("pending_follow_up", "TEXT DEFAULT NULL"),
                ("experiment_mode", "VARCHAR(50) DEFAULT 'fixed'"),
                ("decision_log", "TEXT DEFAULT '[]'"),
                ("competency_map", "TEXT DEFAULT '{}'")
            ]
            for col_name, col_type in columns_to_add:
                add_column_if_missing("interview_sessions", col_name, col_type)

            # 4. responses table scoring/CV columns
            responses_cols = [
                ("head_stability_score", "FLOAT DEFAULT 0.0"),
                ("attention_duration_score", "FLOAT DEFAULT 0.0"),
                ("confidence_score", "FLOAT DEFAULT 0.0"),
                ("correctness_score", "FLOAT DEFAULT 0.0"),
                ("depth_score", "FLOAT DEFAULT 0.0"),
                ("communication_quality_score", "FLOAT DEFAULT 0.0"),
                ("answer_score", "FLOAT DEFAULT 0.0")
            ]
            for col_name, col_type in responses_cols:
                add_column_if_missing("responses", col_name, col_type)

            # 5. users table preference columns
            preferences_cols = [
                ("login_emails_enabled", "BOOLEAN DEFAULT TRUE"),
                ("security_alerts_enabled", "BOOLEAN DEFAULT TRUE"),
                ("interview_reports_enabled", "BOOLEAN DEFAULT TRUE"),
                ("resume_notifications_enabled", "BOOLEAN DEFAULT TRUE"),
                ("marketing_emails_enabled", "BOOLEAN DEFAULT FALSE"),
                ("role", "VARCHAR(50) DEFAULT 'user'")
            ]
            for col_name, col_type in preferences_cols:
                add_column_if_missing("users", col_name, col_type)

            # 6. chat_messages table memory columns
            chat_msg_cols = [
                ("user_id", "INTEGER DEFAULT NULL"),
                ("message_role", "VARCHAR(50) DEFAULT NULL"),
                ("message_content", "TEXT DEFAULT NULL"),
                ("timestamp", "DATETIME DEFAULT NULL")
            ]
            for col_name, col_type in chat_msg_cols:
                add_column_if_missing("chat_messages", col_name, col_type)

        except Exception as e:
            print(f"Error during auto-migration database inspection: {e}")
        
        # Check table existence before seeding or query diagnostics to allow clean migrations
        try:
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
        except Exception:
            tables = []

        if 'roles' in tables and 'users' in tables:
            # Seed default roles
            user_role = Role.query.filter_by(name='USER').first()
            if not user_role:
                user_role = Role(name='USER')
                db.session.add(user_role)
                
            admin_role = Role.query.filter_by(name='ADMIN').first()
            if not admin_role:
                admin_role = Role(name='ADMIN')
                db.session.add(admin_role)
                
            db.session.commit()
            
            # Seed default admin user
            admin_user = User.query.filter_by(username='admin').first()
            if not admin_user:
                admin_user = User(
                    username='admin',
                    email='admin@hirewise.ai',
                    role_id=admin_role.id,
                    is_active=True
                )
                admin_user.set_password('AdminPassword123')
                db.session.add(admin_user)
                db.session.commit()
                
                # Seed associated AdminUser profile
                admin_profile = AdminUser(
                    user_id=admin_user.id,
                    department='Management'
                )
                db.session.add(admin_profile)
                db.session.commit()
                print("Successfully seeded default roles and admin user.")

        if 'questions' in tables:
            # Preload initial questions if database is empty
            preload_questions()

        if 'users' in tables and 'chat_sessions' in tables:
            # Database verification printing
            db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
            db_file = db_uri.replace('sqlite:///', '') if db_uri.startswith('sqlite:///') else db_uri
            
            # Use relative path if configured relative, else resolve it relative to base
            if not Path(db_file).is_absolute():
                db_exists = (Path(app.config.get('BASE_DIR', '.')) / db_file).exists()
            else:
                db_exists = Path(db_file).exists()
            
            try:
                total_users = User.query.count()
            except Exception:
                total_users = 0
                
            try:
                from models.chat import ChatSession
                total_chats = ChatSession.query.count()
            except Exception:
                total_chats = 0

            try:
                total_interviews = InterviewSession.query.count()
            except Exception:
                total_interviews = 0
                
            from urllib.parse import urlparse
            try:
                parsed = urlparse(db_uri)
                db_host = parsed.hostname or "localhost"
                db_engine = "SQLite" if db_uri.startswith("sqlite") else "PostgreSQL"
                db_name = parsed.path.lstrip('/')
                if db_engine == "SQLite":
                    db_name = Path(db_name).name
            except Exception:
                db_host = "localhost"
                db_engine = "SQLite"
                db_name = "hirewise.db"

            masked_db_uri = db_uri
            if "@" in db_uri:
                try:
                    prefix, rest = db_uri.split("://", 1)
                    credentials, host_info = rest.split("@", 1)
                    if ":" in credentials:
                        user, password = credentials.split(":", 1)
                        masked_db_uri = f"{prefix}://{user}:*****@{host_info}"
                except Exception:
                    pass

            ai_provider = "Groq (Llama 3.3)" if app.config.get("GROQ_API_KEY") else "Fallback (Rule-Based)"
            trans_provider = "Groq Whisper API" if app.config.get("GROQ_API_KEY") else "Google SpeechRecognition"

            print(f"AI Provider: {ai_provider}")
            print(f"Transcription Provider: {trans_provider}")
            print(f"Database Engine: {db_engine}")
            print(f"Database Host: {db_host}")
            print(f"Database Name: {db_name}")
            print(f"SQLALCHEMY_DATABASE_URI: {masked_db_uri}")
            print(f"Total Users: {total_users}")
            print(f"Total Chats: {total_chats}")
            print(f"Total Interviews: {total_interviews}")
            
            # Check and create daily backup at startup
            check_and_create_daily_backup(app)

def preload_questions():
    """Load default questions from datasets/questions.json into the DB if empty."""
    from models.question import Question
    
    # Check if we already have questions with skills
    has_skills = Question.query.filter(Question.skill != None).first() is not None
    if has_skills:
        print("Questions with skills already exist in the database. Skipping preloading.")
        return
        
    print("Structured questions with skills missing. Refreshing questions table...")
    try:
        # Clear existing ones to populate new ones
        db.session.query(Question).delete()
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error resetting questions: {e}")
        
    datasets_dir = Path(__file__).resolve().parent.parent / "datasets"
    questions_file = datasets_dir / "questions.json"
    
    if not questions_file.exists():
        print(f"Dataset file not found at {questions_file}. Initializing default structure.")
        return
        
    try:
        with open(questions_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        count = 0
        for item in data.get("questions", []):
            q = Question()

            q.text = item["text"]
            q.category = item["category"]
            q.company = item.get("company")
            q.difficulty = item.get("difficulty", "Medium")
            q.expected_keywords = json.dumps(item.get("expected_keywords", []))
            q.skill = item.get("skill")
            q.subtopic = item.get("subtopic")
            q.prerequisite_skills = json.dumps(item.get("prerequisite_skills", []))
            
            db.session.add(q)
            count += 1
            
        db.session.commit()
        print(f"Preloaded {count} questions with skills into the database.")
    except Exception as e:
        db.session.rollback()
        print(f"Error preloading questions: {e}")

def check_and_create_daily_backup(app):
    """Automatically backup database every day."""
    try:
        from datetime import datetime
        import shutil
        
        # Get database path from config
        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI')
        if not db_uri or not db_uri.startswith('sqlite:///'):
            return
            
        db_path = Path(db_uri.replace('sqlite:///', ''))
        if not db_path.is_absolute():
            db_path = Path(app.config.get('BASE_DIR', '.')) / db_path
        if not db_path.exists():
            return
            
        backups_dir = db_path.parent / 'backups'
        backups_dir.mkdir(parents=True, exist_ok=True)
        
        today_str = datetime.utcnow().strftime('%Y_%m_%d')
        backup_filename = f"hirwise_backup_{today_str}.db"
        backup_path = backups_dir / backup_filename
        
        if not backup_path.exists():
            # Perform backup copy
            shutil.copy2(db_path, backup_path)
            print(f"[ BACKUP ] Daily backup created successfully: {backup_path}")
            
            # Log backup event in system log
            from models.system_log import SystemLog
            try:
                log = SystemLog(
                    level="INFO",
                    module="database",
                    message=f"Auto daily backup created: {backup_filename}"
                )
                db.session.add(log)
                db.session.commit()
            except Exception as ex:
                db.session.rollback()
                print(f"[ BACKUP LOG ERROR ] Failed to log auto daily backup: {ex}")
    except Exception as e:
        print(f"[ BACKUP ERROR ] Failed to create daily backup: {e}")

