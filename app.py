import os
import sys
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables and set python path at application startup
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
load_dotenv(BASE_DIR / ".env")

from flask import Flask, send_from_directory, request, render_template
from flask_login import LoginManager
from flask_migrate import Migrate
from config import Config
from database.connection import db, init_db
from models.user import User

def create_app():
    # Instantiate Flask app with instance_path set to project root
    app = Flask(__name__, instance_path=str(BASE_DIR))
    
    # Load configuration
    app.config.from_object(Config)
    
    # Ensure all upload/database folders exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['UPLOAD_FOLDER'] / "resumes", exist_ok=True)
    os.makedirs(app.config['UPLOAD_FOLDER'] / "profile_images", exist_ok=True)
    os.makedirs(app.config['UPLOAD_FOLDER'] / "interview_audio", exist_ok=True)
    os.makedirs(app.config['UPLOAD_FOLDER'] / "interview_video", exist_ok=True)
    
    # Initialize SQLite Database & SQLAlchemy
    init_db(app)
    
    # Initialize Flask-Migrate
    migrate = Migrate(app, db)
    
    # Register daily backup request hook
    @app.before_request
    def check_daily_backup():
        if request.endpoint == 'static':
            return
        from datetime import datetime
        current_date = datetime.utcnow().date()
        if not hasattr(app, '_last_backup_date') or app._last_backup_date != current_date:
            from database.connection import check_and_create_daily_backup
            check_and_create_daily_backup(app)
            app._last_backup_date = current_date
            
    # Configure Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = "Please sign in to access HireWise AI."
    login_manager.login_message_category = "warning"
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
        
    # Expose upload routing to serve recorded audio and video review clips
    @app.route('/uploads/<path:filename>')
    def serve_upload(filename):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
        
    # Register Route Blueprints
    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.interview import interview_bp
    from routes.resume import resume_bp
    from routes.mentor import mentor_bp
    from routes.admin import admin_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(interview_bp)
    app.register_blueprint(resume_bp)
    app.register_blueprint(mentor_bp)
    app.register_blueprint(admin_bp)
    
    # Context processor to inject active navigation class helpers into templates
    @app.context_processor
    def inject_helpers():
        return dict(active_nav=lambda route: 'active' if request.path.startswith(route) else '')
        
    # Global HTTP error handlers to prevent crashes and present polished templates
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('base.html', error_title="Page Not Found (404)", 
                               error_msg="The page you are looking for does not exist or has been relocated."), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        try:
            import traceback
            from datetime import datetime
            from flask import url_for
            from services.email_service import EmailService
            
            tb = traceback.format_exc()
            admin_url = url_for('admin.dashboard', _external=True)
            EmailService.send_email_async(
                to_email=app.config.get('ADMIN_EMAIL', 'admin@hirewise.ai'),
                subject="Admin Alert: Critical System Error (500)",
                template_name="admin_notification.html",
                context={
                    "notification_type": "error",
                    "message": f"Critical server error (500) encountered: {str(e)}",
                    "timestamp": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                    "username": "System Handler",
                    "extra_details": {
                        "Request URL": request.url,
                        "Request Method": request.method,
                        "Client IP": request.remote_addr,
                        "Traceback": tb[:1500]
                    },
                    "admin_url": admin_url
                },
                event_type="admin_notification",
                ip_address=request.remote_addr
            )
        except Exception as ex:
            print(f"Error dispatching system failure email: {ex}")
            
        return render_template('base.html', error_title="Server Error (500)", 
                               error_msg="An unexpected error occurred. Please try again or check logs."), 500
    @app.route("/debug-db")
    def debug_db():
        return {
            "db": app.config["SQLALCHEMY_DATABASE_URI"]
        }              
    return app

app = create_app()

if __name__ == '__main__':
    # Launch application locally on port 5000
    print("Launching HireWise AI on http://localhost:5000 ...")
    use_reloader = os.environ.get("FLASK_USE_RELOADER", "True").lower() in ("true", "1", "yes")
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=use_reloader)
