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
            'today_registrations': today_registrations
        },
        'users': [dict(u) for u in users]
    })


@app.route('/api/admin/records')
@auth.admin_required
def get_admin_records():
    """Get records with filters and pagination"""
    date_from = request.args.get('from', '')
    date_to = request.args.get('to', '')
    search = request.args.get('search', '')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    
    conn = db.get_db()
    cursor = conn.cursor()
    
    query = '''
        SELECT r.*, u.username 
        FROM registrations r
        LEFT JOIN users u ON r.user_id = u.id
        WHERE 1=1
    '''
    params = []
    
    if date_from:
        query += ' AND DATE(r.created_at) >= ?'
        params.append(date_from)
    
    if date_to:
        query += ' AND DATE(r.created_at) <= ?'
        params.append(date_to)
    
    if search:
        query += ' AND (r.app_name LIKE ? OR r.phone LIKE ? OR u.username LIKE ?)'
        search_param = f'%{search}%'
        params.extend([search_param, search_param, search_param])
    
    # Get total count
    count_query = query.replace('SELECT r.*, u.username', 'SELECT COUNT(*) as total')
    cursor.execute(count_query, params)
    total = cursor.fetchone()['total']
    
    # Get paginated records
    query += ' ORDER BY r.created_at DESC LIMIT ? OFFSET ?'
    params.extend([per_page, (page - 1) * per_page])
    
    cursor.execute(query, params)
    records = cursor.fetchall()
    
    conn.close()
    
    total_pages = max(1, (total + per_page - 1) // per_page)
    
    return jsonify({
        'success': True,
        'records': [dict(r) for r in records],
        'total': total,
        'page': page,
        'per_page': per_page,
        'total_pages': total_pages
    })


@app.route('/api/admin/download_records')
@auth.admin_required
def download_records():
    """Download records as CSV"""
    date_from = request.args.get('from', '')
    date_to = request.args.get('to', '')
    search = request.args.get('search', '')
    
    conn = db.get_db()
    cursor = conn.cursor()
    
    query = '''
        SELECT r.app_name, u.username, r.phone, r.password, 
               r.device_id, r.account_balance, r.created_at
        FROM registrations r
        LEFT JOIN users u ON r.user_id = u.id
        WHERE 1=1
    '''
    params = []
    
    if date_from:
        query += ' AND DATE(r.created_at) >= ?'
        params.append(date_from)
    if date_to:
        query += ' AND DATE(r.created_at) <= ?'
        params.append(date_to)
    if search:
        query += ' AND (r.app_name LIKE ? OR r.phone LIKE ? OR u.username LIKE ?)'
        search_param = f'%{search}%'
        params.extend([search_param, search_param, search_param])
    
    query += ' ORDER BY r.created_at DESC'
    
    cursor.execute(query, params)
    records = cursor.fetchall()
    conn.close()
    
    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['App', 'User', 'Phone', 'Password', 'Device ID', 'Balance', 'Date'])
    
    for r in records:
        writer.writerow([
            r['app_name'], r['username'], r['phone'], r['password'],
            r['device_id'], r['account_balance'], r['created_at']
        ])
    
    response = Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=panther_records.csv'}
    )
    
    return response


@app.route('/api/admin/config')
@auth.admin_required
def get_config():
    """Get current configuration"""
    return jsonify({
        'success': True,
        'config': {
            'base_url': config.API_BASE_URL,
            'api_key': config.API_KEY,
            'otp_delay': config.OTP_SEND_DELAY
        }
    })


@app.route('/api/admin/save_config', methods=['POST'])
@auth.admin_required
def save_config():
    """Save configuration"""
    data = request.json
    base_url = data.get('base_url', '')
    api_key = data.get('api_key', '')
    otp_delay = data.get('otp_delay', 2)
    
    if not base_url or not api_key:
        return jsonify({'success': False, 'message': 'Base URL and API Key required'})
    
    # Update config file
    try:
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.py')
        
        with open(config_path, 'r') as f:
            content = f.read()
        
        # Replace values using regex
        content = re.sub(r'API_BASE_URL = ".*?"', f'API_BASE_URL = "{base_url}"', content)
        content = re.sub(r'API_KEY = ".*?"', f'API_KEY = "{api_key}"', content)
        content = re.sub(r'OTP_SEND_DELAY = \d+', f'OTP_SEND_DELAY = {otp_delay}', content)
        
        with open(config_path, 'w') as f:
            f.write(content)
        
        # Update runtime config
        config.API_BASE_URL = base_url
        config.API_KEY = api_key
        config.OTP_SEND_DELAY = otp_delay
        
        db.log_activity(session['user_id'], session['username'], 'update_config',
                       details=f'Updated API config: {base_url}')
        
        return jsonify({'success': True, 'message': 'Configuration saved successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


# ==================== TOOL ROUTES (Protected) ====================

@app.route('/')
@auth.subuser_required
def index():
    """Main tool page"""
    return render_template('index.html',
                         colors=config.COLORS,
                         apps=config.AVAILABLE_APPS,
                         app_prices=config.APP_PRICES,
                         title="PANTHER",
                         version="TOOL")


@app.route('/api/account/balance')
@auth.subuser_required
def get_balance():
    """Get account balance"""
    result = make_api_request('/v1/account/balance')
    return jsonify(result)


@app.route('/api/send_otp', methods=['POST'])
@auth.subuser_required
def send_otp():
    """Send OTP for registration"""
    data = request.json
    phone = data.get('phone')
    app_name = data.get('app_name')
    
    if not phone or not app_name:
        return jsonify({'status': 'error', 'message': 'Phone and app_name required'})
    
    # Log activity
    db.log_activity(
        session['user_id'],
        session['username'],
        'send_otp',
        app_name=app_name,
        phone=phone,
        status='pending'
    )
    
    payload = {'phone': phone, 'app_name': app_name}
    result = make_api_request('/v1/register/send_otp', method='POST', data=payload)
    
    if result.get('status') == 'success':
        task_id = result.get('task_id')
        active_tasks[task_id] = {
            'phone': phone,
            'app_name': app_name,
            'created_at': datetime.now(),
            'status': 'pending'
        }
    
    return jsonify(result)


@app.route('/api/send_multiple_otps', methods=['POST'])
@auth.subuser_required
def send_multiple_otps():
    """Send multiple OTPs with delay"""
    data = request.json
    phone = data.get('phone')
    apps = data.get('apps', [])
    delay = data.get('delay', config.OTP_SEND_DELAY)
    
    if not phone or not apps:
        return jsonify({'status': 'error', 'message': 'Phone and apps required'})
    
    results = []
    
    for i, app_name in enumerate(apps):
        if i > 0:
            time.sleep(delay)
        
        payload = {'phone': phone, 'app_name': app_name}
        result = make_api_request('/v1/register/send_otp', method='POST', data=payload)
        
        if result.get('status') == 'success':
            task_id = result.get('task_id')
            active_tasks[task_id] = {
                'phone': phone,
                'app_name': app_name,
                'created_at': datetime.now(),
                'status': 'pending'
            }
        
        results.append({
            'app_name': app_name,
            'status': result.get('status'),
            'task_id': result.get('task_id'),
            'message': result.get('message', '')
        })
    
    return jsonify({'status': 'success', 'results': results, 'total': len(results)})


@app.route('/api/verify_otp', methods=['POST'])
@auth.subuser_required
def verify_otp():
    """Verify OTP and complete registration"""
    global success_counter
    
    data = request.json
    task_id = data.get('task_id')
    otp = data.get('otp')
    
    if not task_id or not otp:
        return jsonify({'status': 'error', 'message': 'task_id and otp required'})
    
    payload = {'task_id': task_id, 'otp': otp}
    result = make_api_request('/v1/register/verify_otp', method='POST', data=payload)
    
    if result.get('status') == 'success' and task_id in active_tasks:
        task = active_tasks[task_id]
        task['status'] = 'completed'
        
        app_name = task['app_name']
        if app_name in success_counter:
            success_counter[app_name] += 1
        
        # Extract registration data
        reg_data = result.get('data', {})
        
        # Log successful registration
        db.log_registration(
            session['user_id'],
            session['username'],
            app_name,
            task['phone'],
            reg_data.get('password', ''),
            reg_data.get('device_id', ''),
            reg_data.get('account_balance', 0),
            otp
        )
        
        # Log activity
        db.log_activity(
            session['user_id'],
            session['username'],
            'verify_otp_success',
            app_name=app_name,
            phone=task['phone'],
            otp=otp,
            status='success'
        )
    
    else:
        # Log failed verification
        if task_id in active_tasks:
            db.log_activity(
                session['user_id'],
                session['username'],
                'verify_otp_failed',
                app_name=active_tasks[task_id]['app_name'],
                phone=active_tasks[task_id]['phone'],
                otp=otp,
                status='failed'
            )
    
    return jsonify(result)


@app.route('/api/cancel_task', methods=['POST'])
@auth.subuser_required
def cancel_task():
    """Cancel a pending task"""
    data = request.json
    task_id = data.get('task_id')
    
    if not task_id:
        return jsonify({'status': 'error', 'message': 'task_id required'})
    
    result = make_api_request('/v1/register/cancel_task', method='POST', data={'task_id': task_id})
    
    if result.get('status') == 'success' and task_id in active_tasks:
        del active_tasks[task_id]
    
    return jsonify(result)


@app.route('/api/get_counters')
@auth.subuser_required
def get_counters():
    """Get success counters"""
    return jsonify({'status': 'success', 'counters': success_counter})


@app.route('/api/registrations')
@auth.subuser_required
def get_registrations():
    """Get recent registrations from backend"""
    limit = request.args.get('limit', 10)
    result = make_api_request('/v1/account/registrations', params={'limit': limit})
    return jsonify(result)


# ==================== RUN SERVER ====================

if __name__ == '__main__':
    # Initialize database
    db.init_db()
    
    print(f"\n{'='*50}")
    print(f"   PANTHER TOOL with Admin Panel")
    print(f"{'='*50}")
    print(f"\n🔐 Default Admin Login:")
    print(f"   Username: admin")
    print(f"   Password: admin123")
    print(f"\n🌐 URLs:")
    print(f"   Login:    http://localhost:{config.FLASK_PORT}/login")
    print(f"   Tool:     http://localhost:{config.FLASK_PORT}/")
    print(f"   Admin:    http://localhost:{config.FLASK_PORT}/admin")
    print(f"{'='*50}")
    print(f"\nPress CTRL+C to stop\n")
    
    app.run(
        host=config.FLASK_HOST,
        port=config.FLASK_PORT,
        debug=config.FLASK_DEBUG
    )