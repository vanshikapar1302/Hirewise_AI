import sys
import unittest
from pathlib import Path
from flask import url_for

# Add project root to path
PROJECT_ROOT = Path("c:/Users/aggar/OneDrive/Desktop/hirwise ai").resolve()
sys.path.append(str(PROJECT_ROOT))

from app import create_app
from database.connection import db
from models.user import User
from models.role import Role

class TestAdminAuth(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

        # Build testing user
        self.student_username = 'test_student_unique'
        self.student_email = 'test_student_unique@example.com'
        self.student_password = 'TestPassword123'
        
        # Check if test student exists, clean up first
        existing = User.query.filter_by(username=self.student_username).first()
        if existing:
            db.session.delete(existing)
            db.session.commit()
            
        user_role = Role.query.filter_by(name='USER').first()
        self.student_user = User(
            username=self.student_username,
            email=self.student_email,
            role_id=user_role.id if user_role else None,
            is_active=True
        )
        self.student_user.set_password(self.student_password)
        db.session.add(self.student_user)
        db.session.commit()

    def tearDown(self):
        # Clean up test user
        student = User.query.filter_by(username=self.student_username).first()
        if student:
            db.session.delete(student)
            db.session.commit()
        self.app_context.pop()

    def test_anonymous_admin_route_redirect(self):
        """Test 1: Anonymous access to admin dashboard should redirect to login"""
        response = self.client.get('/admin/dashboard')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login', response.location)
        print("[PASS] Test 1: Anonymous user redirected from /admin/dashboard successfully.")

    def test_student_admin_route_forbidden(self):
        """Test 2: Logged-in student access to admin dashboard should raise 403 Forbidden"""
        # Log in student
        login_res = self.client.post('/login', data={
            'email_or_username': self.student_username,
            'password': self.student_password
        }, follow_redirects=True)
        
        # Try accessing admin route
        response = self.client.get('/admin/dashboard')
        self.assertEqual(response.status_code, 403)
        print("[PASS] Test 2: Logged-in student blocked from /admin/dashboard with 403 Forbidden.")

    def test_admin_dashboard_success(self):
        """Test 3: Logged-in Admin access to admin dashboard should return 200 OK"""
        # Log in default admin
        login_res = self.client.post('/admin/login', data={
            'email_or_username': 'admin',
            'password': 'AdminPassword123'
        }, follow_redirects=True)
        
        response = self.client.get('/admin/dashboard')
        self.assertEqual(response.status_code, 200)
        print("[PASS] Test 3: Logged-in Admin successfully accessed /admin/dashboard with 200 OK.")

    def test_suspended_user_login_lockout(self):
        """Test 4: Suspended users should be blocked from logging in"""
        # Suspend student
        student = User.query.filter_by(username=self.student_username).first()
        student.is_active = False
        db.session.commit()
        
        # Try logging in
        login_res = self.client.post('/login', data={
            'email_or_username': self.student_username,
            'password': self.student_password
        }, follow_redirects=False)
        
        # Login should reload the login page or flash error instead of redirecting to user dashboard
        self.assertNotIn('/dashboard', login_res.location or '')
        print("[PASS] Test 4: Suspended student user successfully blocked from logging in.")

    def test_student_account_self_deletion(self):
        """Test 5: Students should be able to delete their own account"""
        # Log in student
        self.client.post('/login', data={
            'email_or_username': self.student_username,
            'password': self.student_password
        }, follow_redirects=True)
        
        # Post self deletion action to profile
        response = self.client.post('/profile', data={
            'action': 'delete_account'
        }, follow_redirects=True)
        
        # Verify student is removed from database
        deleted_student = User.query.filter_by(username=self.student_username).first()
        self.assertIsNone(deleted_student)
        print("[PASS] Test 5: Student account successfully self-deleted and cleaned from database.")

    def test_admin_failed_login_notifications(self):
        """Test 6: 3 failed admin logins should trigger a security alert email log"""
        from models.email_log import EmailLog
        
        # Clear existing logs for admin
        admin_user = User.query.filter_by(username='admin').first()
        if admin_user:
            EmailLog.query.filter_by(user_id=admin_user.id).delete()
            db.session.commit()
        
        # Trigger 3 failed logins on admin login page
        for _ in range(3):
            self.client.post('/admin/login', data={
                'email_or_username': 'admin',
                'password': 'WrongPassword123'
            })
            
        # Verify a security alert email was logged (with a brief polling wait for the async background thread)
        if admin_user:
            import time
            logs = []
            for _ in range(20):
                # We need to query in a fresh transaction / clear session to see background thread changes in SQLite
                db.session.rollback()
                logs = EmailLog.query.filter_by(user_id=admin_user.id, event_type='security_alert').all()
                if len(logs) >= 1:
                    break
                time.sleep(0.05)
            self.assertTrue(len(logs) >= 1)
            print("[PASS] Test 6: 3 failed admin logins triggered security alert email successfully.")

    def test_admin_successful_login_notifications(self):
        """Test 7: Successful admin login should trigger login alert email log"""
        from models.email_log import EmailLog
        
        admin_user = User.query.filter_by(username='admin').first()
        if admin_user:
            EmailLog.query.filter_by(user_id=admin_user.id).delete()
            # Let's mock preferences so we are sure alerts are enabled
            admin_user.login_emails_enabled = True
            admin_user.security_alerts_enabled = True
            db.session.commit()
            
        # First successful login
        self.client.post('/admin/login', data={
            'email_or_username': 'admin',
            'password': 'AdminPassword123'
        }, headers={'User-Agent': 'AdminTestBrowser1'})
        
        # Second successful login from a new user agent (new device)
        self.client.post('/admin/login', data={
            'email_or_username': 'admin',
            'password': 'AdminPassword123'
        }, headers={'User-Agent': 'AdminTestBrowser2'})
        
        if admin_user:
            # Verify logs with brief polling wait
            import time
            logs = []
            for _ in range(20):
                db.session.rollback()
                logs = EmailLog.query.filter_by(user_id=admin_user.id).all()
                if len(logs) >= 1:
                    break
                time.sleep(0.05)
            self.assertTrue(len(logs) >= 1)
            print("[PASS] Test 7: Successful admin login triggered email alert log successfully.")

if __name__ == '__main__':
    unittest.main()
