from flask import Flask, render_template, request, jsonify, session, redirect, url_for, Response
import requests
import time
import csv
import io
import os
import re
from datetime import datetime
import config
import database as db
import auth

app = Flask(__name__)
app.secret_key = config.FLASK_SECRET_KEY

# In-memory task storage
active_tasks = {}
success_counter = {app: 0 for app in config.AVAILABLE_APPS}

# Initialize database tables
db.init_db()


def make_api_request(endpoint, method='GET', data=None, params=None):
    """Make API request to Panther backend"""
    url = f"{config.API_BASE_URL}{endpoint}"
    headers = {
        'X-API-Key': config.API_KEY,
        'Content-Type': 'application/json'
    }
    
    try:
        if method == 'GET':
            response = requests.get(url, headers=headers, params=params, timeout=10)
        else:
            response = requests.post(url, headers=headers, json=data, params=params, timeout=10)
        return response.json()
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


# ==================== LOGIN ROUTES ====================

@app.route('/login')
def login():
    """Login page"""
    if 'user_id' in session:
        if session.get('role') == 'admin':
            return redirect(url_for('admin_panel'))
        return redirect(url_for('index'))
    return render_template('login.html')


@app.route('/api/login', methods=['POST'])
def api_login():
    """API login endpoint"""
    data = request.json
    username = data.get('username', '')
    password = data.get('password', '')
    
    if not username or not password:
        return jsonify({'success': False, 'message': 'Username and password required'})
    
    user = auth.authenticate_user(username, password)
    
    if user:
        auth.login_user(user)
        db.log_activity(user['id'], user['username'], 'login', status='success')
        
        return jsonify({
            'success': True,
            'role': user['role'],
            'username': user['username']
        })
    else:
        return jsonify({
            'success': False,
            'message': 'Invalid username or password'
        })


@app.route('/logout')
def logout():
    """Logout"""
    if 'user_id' in session:
        db.log_activity(session['user_id'], session['username'], 'logout')
    auth.logout_user()
    return redirect(url_for('login'))


# ==================== ADMIN ROUTES ====================

@app.route('/admin')
@auth.admin_required
def admin_panel():
    """Admin panel - Records Tracker + User Management + Config"""
    return render_template('admin.html')


@app.route('/api/admin/current_user')
def get_current_user_api():
    """Get current logged in user"""
    if 'user_id' in session:
        return jsonify({
            'success': True,
            'user': {
                'id': session['user_id'],
                'username': session['username'],
                'role': session['role']
            }
        })
    return jsonify({'success': False})


@app.route('/api/admin/users', methods=['GET'])
@auth.admin_required
def get_users():
    """Get all users"""
    users = db.get_all_users()
    return jsonify({
        'success': True,
        'users': [dict(u) for u in users]
    })


@app.route('/api/admin/create_user', methods=['POST'])
@auth.admin_required
def create_user():
    """Create new user"""
    data = request.json
    username = data.get('username', '')
    password = data.get('password', '')
    
    if not username or not password:
        return jsonify({'success': False, 'message': 'Username and password required'})
    
    success, message = db.create_user(username, password, 'subuser')
    
    if success:
        db.log_activity(session['user_id'], session['username'], 'create_user', 
                       details=f'Created user: {username}')
        return jsonify({'success': True, 'message': message})
    else:
        return jsonify({'success': False, 'message': message})


@app.route('/api/admin/delete_user', methods=['POST'])
@auth.admin_required
def delete_user():
    """Delete user"""
    data = request.json
    user_id = data.get('user_id')
    
    if user_id:
        db.delete_user(user_id)
        db.log_activity(session['user_id'], session['username'], 'delete_user', 
                       details=f'Deleted user ID: {user_id}')
        return jsonify({'success': True})
    
    return jsonify({'success': False})


@app.route('/api/admin/registrations')
@auth.admin_required
def admin_registrations():
    """Get all registrations"""
    user_id = request.args.get('user_id')
    limit = request.args.get('limit', 100)
    
    registrations = db.get_registrations(
        user_id=int(user_id) if user_id else None, 
        limit=int(limit)
    )
    
    return jsonify({
        'success': True,
        'registrations': [dict(r) for r in registrations]
    })


@app.route('/api/admin/activity')
@auth.admin_required
def admin_activity():
    """Get activity logs"""
    user_id = request.args.get('user_id')
    limit = request.args.get('limit', 100)
    
    logs = db.get_activity_logs(
        user_id=int(user_id) if user_id else None, 
        limit=int(limit)
    )
    
    return jsonify({
        'success': True,
        'logs': [dict(l) for l in logs]
    })


@app.route('/api/admin/stats')
@auth.admin_required
def admin_stats():
    """Get admin statistics"""
    users = db.get_all_users_stats()
    
    total_users = len(users)
    total_registrations = sum(u['total_registrations'] for u in users)
    today_registrations = sum(u['today_registrations'] for u in users)
    
    return jsonify({
        'success': True,
        'stats': {
            'total_users': total_users,
            'total_registrations': total_registrations,
            'today_registrations': today_registrations,
            'users': users
        }
    })


# ==================== SUBUSER ROUTES ====================

@app.route('/')
@auth.login_required
def index():
    """Main tool page for subusers"""
    return render_template('index.html')


@app.route('/api/available_apps')
@auth.login_required
def available_apps():
    """Get available apps"""
    return jsonify({
        'success': True,
        'apps': config.AVAILABLE_APPS
    })


@app.route('/api/send_otp', methods=['POST'])
@auth.login_required
def send_otp():
    """Send OTP for registration"""
    data = request.json
    app_name = data.get('app_name', '')
    phone = data.get('phone', '')
    
    if not app_name or not phone:
        return jsonify({'success': False, 'message': 'App name and phone required'})
    
    result = make_api_request('/v1/account/send_otp', method='POST', data={
        'app_name': app_name,
        'phone': phone
    })
    
    if result.get('status') == 'success':
        db.log_activity(session['user_id'], session['username'], 'send_otp',
                       app_name=app_name, phone=phone, status='success')
    else:
        db.log_activity(session['user_id'], session['username'], 'send_otp',
                       app_name=app_name, phone=phone, status='failed',
                       details=result.get('message', ''))
    
    return jsonify(result)


@app.route('/api/register', methods=['POST'])
@auth.login_required
def register():
    """Complete registration"""
    data = request.json
    app_name = data.get('app_name', '')
    phone = data.get('phone', '')
    password = data.get('password', '')
    otp = data.get('otp', '')
    device_id = data.get('device_id', '')
    
    if not all([app_name, phone, password, otp]):
        return jsonify({'success': False, 'message': 'All fields required'})
    
    result = make_api_request('/v1/account/register', method='POST', data={
        'app_name': app_name,
        'phone': phone,
        'password': password,
        'otp': otp,
        'device_id': device_id
    })
    
    if result.get('status') == 'success':
        db.log_activity(session['user_id'], session['username'], 'register',
                       app_name=app_name, phone=phone, otp=otp, status='success')
        db.save_registration(
            session['user_id'], session['username'],
            app_name, phone, password, device_id,
            result.get('data', {}).get('account_balance', 0),
            otp
        )
    else:
        db.log_activity(session['user_id'], session['username'], 'register',
                       app_name=app_name, phone=phone, otp=otp, status='failed',
                       details=result.get('message', ''))
    
    return jsonify(result)


@app.route('/api/get_balance')
@auth.login_required
def get_balance():
    """Get account balance"""
    app_name = request.args.get('app_name', '')
    phone = request.args.get('phone', '')
    
    if not app_name or not phone:
        return jsonify({'success': False, 'message': 'App name and phone required'})
    
    result = make_api_request('/v1/account/balance', params={
        'app_name': app_name,
        'phone': phone
    })
    
    return jsonify(result)


@app.route('/api/get_counters')
@auth.login_required
def get_counters():
    """Get success counters"""
    return jsonify({'status': 'success', 'counters': success_counter})


@app.route('/api/registrations')
@auth.login_required
def get_registrations():
    """Get recent registrations from backend"""
    limit = request.args.get('limit', 10)
    result = make_api_request('/v1/account/registrations', params={'limit': limit})
    return jsonify(result)


# ==================== RUN SERVER (COMMENTED OUT FOR GUNICORN) ====================

# if __name__ == '__main__':
#     # Initialize database
#     db.init_db()
#     
#     print(f"\n{'='*50}")
#     print(f"   PANTHER TOOL with Admin Panel")
#     print(f"{'='*50}")
#     print(f"\n🔐 Default Admin Login:")
#     print(f"   Username: admin")
#     print(f"   Password: admin123")
#     print(f"\n🌐 URLs:")
#     print(f"   Login:    http://localhost:{config.FLASK_PORT}/login")
#     print(f"   Tool:     http://localhost:{config.FLASK_PORT}/")
#     print(f"   Admin:    http://localhost:{config.FLASK_PORT}/admin")
#     print(f"{'='*50}")
#     print(f"\nPress CTRL+C to stop\n")
#     
#     import os
#     port = int(os.getenv('PORT', 5001))
#     
#     app.run(
#         host='0.0.0.0',
#         port=port,
#         debug=False
#     )
