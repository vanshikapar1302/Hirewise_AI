import os
import requests
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, session, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from database.connection import db
from models.user import User
from services.email_service import EmailService

auth_bp = Blueprint('auth', __name__)

# Verify Supabase configuration is loaded correctly from environment
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_ANON_KEY = os.environ.get('SUPABASE_ANON_KEY') or os.environ.get('SUPABASE_KEY')

if not SUPABASE_URL:
    print("[WARNING] SUPABASE_URL is missing from environment. Supabase integration may fail.")
else:
    print(f"[INFO] SUPABASE_URL loaded from environment: {SUPABASE_URL}")

if not SUPABASE_ANON_KEY:
    print("[WARNING] SUPABASE_ANON_KEY is missing from environment. Supabase REST API requests will fail.")
else:
    masked_key = SUPABASE_ANON_KEY[:10] + "..." if len(SUPABASE_ANON_KEY) > 10 else "loaded"
    print(f"[INFO] SUPABASE_ANON_KEY loaded from environment: {masked_key}")

def verify_supabase_password(email, password):
    supabase_url = SUPABASE_URL or "https://bkdhoauhxavbernvkvgn.supabase.co"
    supabase_key = SUPABASE_ANON_KEY
    
    headers = {}
    if supabase_key:
        headers["apikey"] = supabase_key
        headers["Authorization"] = f"Bearer {supabase_key}"
        
    try:
        payload = {
            "email": email,
            "password": password
        }
        res = requests.post(f"{supabase_url}/auth/v1/token?grant_type=password", json=payload, headers=headers, timeout=5)
        if res.status_code == 200:
            return True, res.json()
        return False, res.text
    except Exception as e:
        return False, str(e)

def signup_supabase_user(email, password):
    supabase_url = SUPABASE_URL or "https://bkdhoauhxavbernvkvgn.supabase.co"
    supabase_key = SUPABASE_ANON_KEY
    
    headers = {}
    if supabase_key:
        headers["apikey"] = supabase_key
        
    try:
        payload = {
            "email": email,
            "password": password
        }
        res = requests.post(f"{supabase_url}/auth/v1/signup", json=payload, headers=headers, timeout=5)
        if res.status_code in [200, 201]:
            return True, res.json()
        return False, res.text
    except Exception as e:
        return False, str(e)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.home'))
        
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        
        if not username or not email or not password:
            flash('All fields are required.', 'danger')
            return render_template('register.html')
            
        # Check if user already exists
        user_by_username = db.session.query(User).filter_by(username=username).first()
        if user_by_username:
            flash('Username is already taken.', 'danger')
            return render_template('register.html')
            
        user_by_email = db.session.query(User).filter_by(email=email).first()
        if user_by_email:
            flash('Email is already registered.', 'danger')
            return render_template('register.html')
            
        # Try to sign up user in Supabase Auth first
        signup_supabase_user(email, password)

        # Create new user
        from models.role import Role
        user_role = Role.query.filter_by(name='USER').first()
        new_user = User(
            username=username,
            email=email,
            role_id=user_role.id if user_role else None,
            is_active=True
        )
        new_user.set_password(password)
        
        try:
            db.session.add(new_user)
            db.session.commit()
            
            # Trigger Admin Notification
            from models.admin_notification import AdminNotification
            reg_notif = AdminNotification(
                type='registration',
                message=f"New candidate registered: {username} ({email})"
            )
            db.session.add(reg_notif)
            db.session.commit()
            
            # Trigger Welcome Email to Candidate
            dashboard_url = url_for('dashboard.home', _external=True)
            EmailService.send_email_async(
                to_email=new_user.email,
                subject="Welcome to HireWise AI",
                template_name="welcome_email.html",
                context={"name": new_user.name, "dashboard_url": dashboard_url},
                user_id=new_user.id,
                event_type="welcome",
                ip_address=request.remote_addr
            )

            # Trigger Admin Notification Email
            from flask import current_app
            admin_url = url_for('admin.dashboard', _external=True)
            EmailService.send_email_async(
                to_email=current_app.config.get('ADMIN_EMAIL', 'admin@hirewise.ai'),
                subject="Admin Alert: New User Registration",
                template_name="admin_notification.html",
                context={
                    "notification_type": "registration",
                    "message": f"New candidate registered: {username} ({email})",
                    "timestamp": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                    "username": username,
                    "admin_url": admin_url
                },
                event_type="admin_notification",
                ip_address=request.remote_addr
            )
            
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred during registration. Please try again.', 'danger')
            print(f"Registration DB Error: {e}")
            
    return render_template('register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.home'))
        
    if request.method == 'POST':
        email_or_username = request.form.get('email_or_username', '').strip()
        password = request.form.get('password', '')
        remember = True if request.form.get('remember') else False
        
        if not email_or_username or not password:
            flash('Please enter your credentials.', 'danger')
            return render_template('login.html')
            
        # Look up by email first, then username
        user = db.session.query(User).filter((User.email == email_or_username) | (User.username == email_or_username)).first()
        
        authenticated = False
        if user:
            # Try Supabase Auth first
            success, _ = verify_supabase_password(user.email, password)
            if success:
                authenticated = True
            elif user.check_password(password):
                # Fallback to local password checking for backward compatibility
                authenticated = True
                
        if not user or not authenticated:
            failed_key = f"failed_logins_{email_or_username}"
            session[failed_key] = session.get(failed_key, 0) + 1
            if session[failed_key] >= 3:
                if user and user.security_alerts_enabled:
                    reset_url = url_for('auth.forgot_password', _external=True)
                    EmailService.send_email_async(
                        to_email=user.email,
                        subject="Security Alert: Multiple Failed Login Attempts - HireWise AI",
                        template_name="login_alert.html",
                        context={
                            "name": user.name,
                            "security_warning": True,
                            "ip_address": request.remote_addr,
                            "device": request.headers.get('User-Agent', 'Unknown Device'),
                            "browser": request.user_agent.browser or 'Unknown Browser',
                            "location": "Local/Intranet" if request.remote_addr in ('127.0.0.1', '::1') else "Unknown Location",
                            "timestamp": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                            "reset_url": reset_url
                        },
                        user_id=user.id,
                        event_type="security_alert",
                        ip_address=request.remote_addr
                    )
            flash('Invalid username/email or password.', 'danger')
            return render_template('login.html')
            
        if not user.is_active:
            flash('Your account has been suspended. Please contact support.', 'danger')
            return render_template('login.html')
            
        # Clear failed logins
        session[f"failed_logins_{email_or_username}"] = 0
        
        from datetime import datetime
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        # Check if login is from a new device/IP
        from models.user_session import UserSession
        prev_sessions = db.session.query(UserSession).filter_by(user_id=user.id).all()
        is_new_device = False
        is_new_location = False
        user_agent = request.headers.get('User-Agent', '')
        ip_address = request.remote_addr
        
        if prev_sessions:
            ips_seen = {s.ip_address for s in prev_sessions}
            uas_seen = {s.user_agent for s in prev_sessions}
            if ip_address not in ips_seen:
                is_new_location = True
            if user_agent not in uas_seen:
                is_new_device = True
                
        # Send security alert or login confirmation
        if user.security_alerts_enabled and (is_new_device or is_new_location):
            reset_url = url_for('auth.forgot_password', _external=True)
            EmailService.send_email_async(
                to_email=user.email,
                subject="Security Alert: Login from New Device/Location - HireWise AI",
                template_name="login_alert.html",
                context={
                    "name": user.name,
                    "security_warning": True,
                    "ip_address": ip_address,
                    "device": user_agent,
                    "browser": request.user_agent.browser or 'Unknown Browser',
                    "location": "Local/Intranet" if ip_address in ('127.0.0.1', '::1') else "Unknown Location",
                    "timestamp": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                    "reset_url": reset_url
                },
                user_id=user.id,
                event_type="security_alert",
                ip_address=ip_address
            )
        elif user.login_emails_enabled:
            EmailService.send_email_async(
                to_email=user.email,
                subject="New Login Detected - HireWise AI",
                template_name="login_alert.html",
                context={
                    "name": user.name,
                    "security_warning": False,
                    "ip_address": ip_address,
                    "device": user_agent,
                    "browser": request.user_agent.browser or 'Unknown Browser',
                    "location": "Local/Intranet" if ip_address in ('127.0.0.1', '::1') else "Unknown Location",
                    "timestamp": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                },
                user_id=user.id,
                event_type="login_alert",
                ip_address=ip_address
            )
            
        login_user(user, remember=remember)
        
        # Log User Session
        try:
            session_log = UserSession(
                user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent
            )
            db.session.add(session_log)
            db.session.commit()
        except Exception as e:
            print(f"Error logging session: {e}")
            db.session.rollback()

        next_page = request.args.get('next')
        if user.is_admin:
            return redirect(next_page or url_for('admin.dashboard'))
        return redirect(next_page or url_for('dashboard.home'))
        
    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    # Update active UserSession
    try:
        from datetime import datetime
        from models.user_session import UserSession
        active_sess = db.session.query(UserSession).filter_by(
            user_id=current_user.id, logout_time=None
        ).order_by(UserSession.login_time.desc()).first()
        if active_sess:
            active_sess.logout_time = datetime.utcnow()
            db.session.commit()
    except Exception as e:
        print(f"Error updating logout session: {e}")
        db.session.rollback()

    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'update_profile':
            username = request.form.get('username', '').strip()
            email = request.form.get('email', '').strip()
            full_name = request.form.get('full_name', '').strip()
            profile_photo_file = request.files.get('profile_photo')
            
            if not username or not email:
                flash('Username and email cannot be empty.', 'danger')
                return redirect(url_for('auth.profile'))
                
            # Check duplicates
            existing_user = db.session.query(User).filter(User.username == username, User.id != current_user.id).first()
            if existing_user:
                flash('Username is already taken.', 'danger')
                return redirect(url_for('auth.profile'))
                
            existing_email = db.session.query(User).filter(User.email == email, User.id != current_user.id).first()
            if existing_email:
                flash('Email is already registered by another user.', 'danger')
                return redirect(url_for('auth.profile'))
                
            # Save photo if uploaded
            if profile_photo_file and profile_photo_file.filename != '':
                from werkzeug.utils import secure_filename
                ext = secure_filename(profile_photo_file.filename).split('.')[-1].lower()
                if ext in {'png', 'jpg', 'jpeg', 'gif'}:
                    filename = f"user_{current_user.id}_avatar.{ext}"
                    from flask import current_app
                    dest = current_app.config['UPLOAD_FOLDER'] / filename
                    profile_photo_file.save(str(dest))
                    current_user.profile_photo = filename
                else:
                    flash('Invalid profile photo format. Use PNG, JPG, or GIF.', 'warning')
                    
            current_user.username = username
            current_user.email = email
            current_user.full_name = full_name
            db.session.commit()
            flash('Profile updated successfully.', 'success')
            
        elif action == 'change_password':
            old_password = request.form.get('old_password', '')
            new_password = request.form.get('new_password', '')
            
            if not current_user.check_password(old_password):
                flash('Incorrect current password.', 'danger')
                return redirect(url_for('auth.profile'))
                
            if len(new_password) < 6:
                flash('New password must be at least 6 characters long.', 'danger')
                return redirect(url_for('auth.profile'))
                
            current_user.set_password(new_password)
            db.session.commit()
            flash('Password changed successfully.', 'success')
            
        elif action == 'update_notifications':
            current_user.login_emails_enabled = 'login_emails_enabled' in request.form
            current_user.security_alerts_enabled = 'security_alerts_enabled' in request.form
            current_user.interview_reports_enabled = 'interview_reports_enabled' in request.form
            current_user.resume_notifications_enabled = 'resume_notifications_enabled' in request.form
            current_user.marketing_emails_enabled = 'marketing_emails_enabled' in request.form
            db.session.commit()
            flash('Notification preferences updated successfully.', 'success')
            
        elif action == 'delete_history':
            # Clear all user's mock interview sessions
            try:
                from models.interview import InterviewSession
                sessions_deleted = db.session.query(InterviewSession).filter_by(user_id=current_user.id).delete()
                db.session.commit()
                flash(f'Successfully deleted {sessions_deleted} interview attempts from history.', 'success')
            except Exception as e:
                db.session.rollback()
                flash('Failed to delete history.', 'danger')
                print(e)
                
        elif action == 'delete_account':
            user_id = current_user.id
            logout_user()
            user_to_delete = db.session.query(User).get(user_id)
            if user_to_delete:
                db.session.delete(user_to_delete)
                db.session.commit()
            flash('Your account has been successfully deleted.', 'success')
            return redirect(url_for('dashboard.index'))
                
        return redirect(url_for('auth.profile'))
        
    return render_template('profile.html')

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.home'))
        
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        if email:
            user = db.session.query(User).filter_by(email=email).first()
            if user:
                from itsdangerous import URLSafeTimedSerializer
                from flask import current_app
                serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
                token = serializer.dumps(user.email, salt='password-reset-salt')
                
                reset_url = url_for('auth.reset_password', token=token, _external=True)
                EmailService.send_email_async(
                    to_email=user.email,
                    subject="Reset Your Password - HireWise AI",
                    template_name="password_reset.html",
                    context={"name": user.name, "reset_url": reset_url},
                    user_id=user.id,
                    event_type="password_reset",
                    ip_address=request.remote_addr
                )
            flash('If the email is registered in our database, a password reset link has been dispatched.', 'success')
            return redirect(url_for('auth.login'))
        else:
            flash('Email address is required.', 'danger')
            
    return render_template('forgot_password.html')

@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.home'))
        
    from itsdangerous import URLSafeTimedSerializer
    from flask import current_app
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    
    try:
        # Link valid for 15 minutes = 900 seconds
        email = serializer.loads(token, salt='password-reset-salt', max_age=900)
    except Exception:
        flash('The password reset link is invalid or has expired.', 'danger')
        return redirect(url_for('auth.forgot_password'))
        
    if request.method == 'POST':
        password = request.form.get('password')
        if not password or len(password) < 6:
            flash('Password must be at least 6 characters long.', 'danger')
            return render_template('reset_password.html', token=token)
            
        user = db.session.query(User).filter_by(email=email).first()
        if user:
            user.set_password(password)
            db.session.commit()
            flash('Your password has been successfully updated. Please login.', 'success')
            return redirect(url_for('auth.login'))
        else:
            flash('User account not found.', 'danger')
            return redirect(url_for('auth.forgot_password'))
            
    return render_template('reset_password.html', token=token)

@auth_bp.route('/auth/oauth/google', defaults={'provider': 'google'})
@auth_bp.route('/auth/oauth/github', defaults={'provider': 'github'})
def oauth_login(provider):
    if not SUPABASE_URL:
        print("[WARNING] SUPABASE_URL is missing. OAuth redirect cannot be performed.")
        flash('OAuth is not configured on this server.', 'danger')
        return redirect(url_for('auth.login'))
        
    callback_url = url_for('auth.oauth_callback', _external=True)
    authorize_url = f"{SUPABASE_URL}/auth/v1/authorize?provider={provider}&redirect_to={callback_url}"
    return redirect(authorize_url)

@auth_bp.route('/auth/callback')
def oauth_callback():
    return render_template('oauth_callback.html')

@auth_bp.route('/auth/token-login', methods=['POST'])
def token_login():
    data = request.get_json() or {}
    access_token = data.get('access_token')
    if not access_token:
        print("[ERROR] Token login attempt with missing access token.")
        return jsonify({"success": False, "error": "Access token missing."}), 400
        
    if not SUPABASE_URL:
        print("[WARNING] SUPABASE_URL is missing. Token validation failed.")
        return jsonify({"success": False, "error": "OAuth configuration (SUPABASE_URL) is missing on the server."}), 500
        
    if not SUPABASE_ANON_KEY:
        print("[WARNING] SUPABASE_ANON_KEY is missing. Token validation failed.")
        return jsonify({"success": False, "error": "OAuth configuration (SUPABASE_ANON_KEY) is missing on the server."}), 500
        
    headers = {
        "Authorization": f"Bearer {access_token}",
        "apikey": SUPABASE_ANON_KEY
    }
        
    try:
        response = requests.get(f"{SUPABASE_URL}/auth/v1/user", headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"[ERROR] Supabase token validation failed. Status: {response.status_code}, Body: {response.text}")
            return jsonify({"success": False, "error": "Invalid token or user not authenticated by Supabase."}), 401
            
        user_data = response.json()
        email = user_data.get("email")
        if not email:
            print("[ERROR] Email address not found in Supabase user token payload.")
            return jsonify({"success": False, "error": "Email address not found in Supabase token payload."}), 400
            
        # Parse provider from app_metadata.provider or identities[].provider
        app_metadata = user_data.get("app_metadata", {})
        provider = app_metadata.get("provider")
        if not provider:
            identities = user_data.get("identities", [])
            if identities and isinstance(identities, list):
                provider = identities[0].get("provider")
        if not provider or provider == 'email':
            provider = 'google' # Default/fallback if not resolvable
            
        # Find user in our local DB or create one
        user = db.session.query(User).filter_by(email=email).first()
        if not user:
            # Generate username safely
            base_username = email.split('@')[0]
            # Ensure base fits within 64 chars even after adding suffixes
            base_username = base_username[:55]
            username = base_username
            
            # loop to ensure uniqueness
            suffix_counter = 1
            while db.session.query(User).filter_by(username=username).first():
                username = f"{base_username}_{suffix_counter}"
                suffix_counter += 1
                
            from models.role import Role
            user_role = Role.query.filter_by(name='USER').first()
            
            user = User(
                username=username,
                email=email,
                role_id=user_role.id if user_role else None,
                is_active=True
            )
            # Never store passwords locally for social login users
            user.set_password(os.urandom(16).hex())
            
            db.session.add(user)
            db.session.commit()
            
            # Trigger Admin Notification and Welcome Email to Candidate
            try:
                # Trigger Admin Notification
                from models.admin_notification import AdminNotification
                reg_notif = AdminNotification(
                    type='registration',
                    message=f"New social login user registered: {username} ({email}) via {provider}"
                )
                db.session.add(reg_notif)
                db.session.commit()
                
                # Send Welcome Email
                dashboard_url = url_for('dashboard.home', _external=True)
                EmailService.send_email_async(
                    to_email=user.email,
                    subject="Welcome to HireWise AI",
                    template_name="welcome_email.html",
                    context={"name": user.name, "dashboard_url": dashboard_url},
                    user_id=user.id,
                    event_type="welcome",
                    ip_address=request.remote_addr
                )
                
                # Send Admin Notification Email
                from flask import current_app
                admin_url = url_for('admin.dashboard', _external=True)
                EmailService.send_email_async(
                    to_email=current_app.config.get('ADMIN_EMAIL', 'admin@hirewise.ai'),
                    subject="Admin Alert: New User Registration",
                    template_name="admin_notification.html",
                    context={
                        "notification_type": "registration",
                        "message": f"New social login user registered: {username} ({email}) via {provider}",
                        "timestamp": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                        "username": username,
                        "admin_url": admin_url
                    },
                    event_type="admin_notification",
                    ip_address=request.remote_addr
                )
            except Exception as e_notify:
                print(f"[WARNING] Social login notification failed: {e_notify}")
        else:
            # Existing user found by email - backward compatible identification
            pass
        
        if not user.is_active:
            print(f"[WARNING] Inactive user email: {email} tried to login via OAuth.")
            return jsonify({"success": False, "error": "Your account has been suspended."}), 403
            
        login_user(user, remember=True)
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        # Log User Session
        try:
            from models.user_session import UserSession
            session_log = UserSession(
                user_id=user.id,
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent', '')
            )
            db.session.add(session_log)
            db.session.commit()
        except Exception as e_sess:
            print(f"[ERROR] Error logging user session: {e_sess}")
            db.session.rollback()
            
        return jsonify({"success": True})
    except Exception as e:
        print(f"[ERROR] Token login exception: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
