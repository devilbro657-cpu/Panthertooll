import sqlite3
from datetime import datetime
import os

DB_PATH = 'panther.db'

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database tables"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'subuser',
            api_key TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1
        )
    ''')
    
    # Activity log table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            action TEXT,
            app_name TEXT,
            phone TEXT,
            otp TEXT,
            status TEXT,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Account registrations table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            app_name TEXT,
            phone TEXT,
            password TEXT,
            device_id TEXT,
            account_balance REAL,
            otp_used TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    conn.commit()
    conn.close()
    
    # Create default admin if not exists
    create_default_admin()

def create_default_admin():
    """Create default admin user"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE username = ?', ('admin',))
    if not cursor.fetchone():
        cursor.execute('''
            INSERT INTO users (username, password, role, api_key)
            VALUES (?, ?, ?, ?)
        ''', ('admin', 'admin123', 'admin', 'admin_key_123'))
        conn.commit()
    
    conn.close()

# User Management Functions
def create_user(username, password, role='subuser', api_key=None):
    """Create new user"""
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO users (username, password, role, api_key)
            VALUES (?, ?, ?, ?)
        ''', (username, password, role, api_key))
        conn.commit()
        return True, "User created successfully"
    except sqlite3.IntegrityError:
        return False, "Username already exists"
    finally:
        conn.close()

def get_all_users():
    """Get all users"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users ORDER BY created_at DESC')
    users = cursor.fetchall()
    conn.close()
    return users

def get_user_by_username(username):
    """Get user by username"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    conn.close()
    return user

def update_user(user_id, **kwargs):
    """Update user"""
    conn = get_db()
    cursor = conn.cursor()
    
    updates = []
    values = []
    
    for key, value in kwargs.items():
        updates.append(f"{key} = ?")
        values.append(value)
    
    values.append(user_id)
    
    cursor.execute(f'''
        UPDATE users SET {', '.join(updates)} WHERE id = ?
    ''', values)
    
    conn.commit()
    conn.close()

def delete_user(user_id):
    """Delete user"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()

# Activity Log Functions
def log_activity(user_id, username, action, app_name=None, phone=None, otp=None, status=None, details=None):
    """Log user activity"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO activity_log (user_id, username, action, app_name, phone, otp, status, details)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, username, action, app_name, phone, otp, status, details))
    
    conn.commit()
    conn.close()

def get_activity_logs(user_id=None, limit=100):
    """Get activity logs"""
    conn = get_db()
    cursor = conn.cursor()
    
    if user_id:
        cursor.execute('''
            SELECT * FROM activity_log WHERE user_id = ?
            ORDER BY created_at DESC LIMIT ?
        ''', (user_id, limit))
    else:
        cursor.execute('''
            SELECT * FROM activity_log
            ORDER BY created_at DESC LIMIT ?
        ''', (limit,))
    
    logs = cursor.fetchall()
    conn.close()
    return logs

# Registration Functions
def log_registration(user_id, username, app_name, phone, password, device_id, account_balance, otp_used):
    """Log successful registration"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO registrations (user_id, username, app_name, phone, password, device_id, account_balance, otp_used)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, username, app_name, phone, password, device_id, account_balance, otp_used))
    
    conn.commit()
    conn.close()

def get_registrations(user_id=None, limit=100):
    """Get registrations"""
    conn = get_db()
    cursor = conn.cursor()
    
    if user_id:
        cursor.execute('''
            SELECT * FROM registrations WHERE user_id = ?
            ORDER BY created_at DESC LIMIT ?
        ''', (user_id, limit))
    else:
        cursor.execute('''
            SELECT * FROM registrations
            ORDER BY created_at DESC LIMIT ?
        ''', (limit,))
    
    registrations = cursor.fetchall()
    conn.close()
    return registrations

def get_user_stats(user_id):
    """Get user statistics"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Total registrations
    cursor.execute('SELECT COUNT(*) as total FROM registrations WHERE user_id = ?', (user_id,))
    total = cursor.fetchone()['total']
    
    # Registrations by app
    cursor.execute('''
        SELECT app_name, COUNT(*) as count
        FROM registrations WHERE user_id = ?
        GROUP BY app_name ORDER BY count DESC
    ''', (user_id,))
    by_app = cursor.fetchall()
    
    # Today's registrations
    cursor.execute('''
        SELECT COUNT(*) as today_count FROM registrations
        WHERE user_id = ? AND DATE(created_at) = DATE('now')
    ''', (user_id,))
    today = cursor.fetchone()['today_count']
    
    conn.close()
    
    return {
        'total': total,
        'today': today,
        'by_app': by_app
    }

def get_all_users_stats():
    """Get all users statistics"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT u.id, u.username, u.created_at,
               COUNT(r.id) as total_registrations,
               SUM(CASE WHEN DATE(r.created_at) = DATE('now') THEN 1 ELSE 0 END) as today_registrations
        FROM users u
        LEFT JOIN registrations r ON u.id = r.user_id
        WHERE u.role = 'subuser'
        GROUP BY u.id
        ORDER BY total_registrations DESC
    ''')
    
    stats = cursor.fetchall()
    conn.close()
    return stats

# Initialize database on import
init_db()