from flask import session, redirect, url_for, request
from functools import wraps
import database as db

def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        if session.get('role') != 'admin':
            return "Access Denied: Admin only", 403
        
        return f(*args, **kwargs)
    return decorated_function

def subuser_required(f):
    """Decorator to require subuser role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        if session.get('role') not in ['admin', 'subuser']:
            return "Access Denied", 403
        
        return f(*args, **kwargs)
    return decorated_function

def authenticate_user(username, password):
    """Authenticate user"""
    user = db.get_user_by_username(username)
    
    if user and user['password'] == password and user['is_active']:
        return user
    
    return None

def login_user(user):
    """Login user - set session"""
    session['user_id'] = user['id']
    session['username'] = user['username']
    session['role'] = user['role']
    session['api_key'] = user['api_key']

def logout_user():
    """Logout user - clear session"""
    session.clear()

def get_current_user():
    """Get current logged in user"""
    if 'user_id' in session:
        return {
            'id': session['user_id'],
            'username': session['username'],
            'role': session['role']
        }
    return None