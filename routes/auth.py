from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from flask_wtf.csrf import generate_csrf
from werkzeug.security import generate_password_hash
from functools import wraps
from ..models.user import User
from .. import db
import secrets
from datetime import datetime, timedelta

auth_bp = Blueprint('auth', __name__)

# Helper functions
def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role not in roles:
                flash('Access denied.', 'error')
                return redirect(url_for('auth.login'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def admin_required(f):
    return role_required('admin')(f)

def shop_owner_required(f):
    return role_required('shop_owner')(f)

def delivery_required(f):
    return role_required('delivery')(f)

def customer_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'user':
            flash('Access denied. This feature is only available for customers.', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

def get_role_dashboard(role):
    """Helper function to redirect users to their appropriate dashboard"""
    dashboards = {
        'admin': 'admin.dashboard',
        'shop_owner': 'shop.dashboard',
        'delivery': 'delivery.dashboard',
        'user': 'user.dashboard'
    }
    return url_for(dashboards.get(role, 'main.index'))

def send_password_reset_email(user):
    """Helper function to send password reset email"""
    token = secrets.token_urlsafe(32)
    user.reset_token = token
    user.reset_token_expiry = datetime.utcnow() + timedelta(hours=1)
    db.session.commit()
    # In a real application, send an actual email here
    flash(f'Password reset link: {url_for("auth.reset_password", token=token, _external=True)}', 'info')

# Routes
@auth_bp.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin.dashboard'))
        flash('Access denied. This login is for administrators only.', 'error')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email, role='admin').first()
        
        if not user or not user.check_password(password):
            flash('Invalid admin credentials.', 'error')
            return render_template('admin/login.html')
            
        login_user(user)
        return redirect(url_for('admin.dashboard'))
        
    return render_template('admin/login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role', 'user')  # Default role is 'user'
        
        # Validate role selection
        allowed_roles = ['user', 'shop_owner', 'delivery']
        if role not in allowed_roles:
            flash('Invalid role selected.', 'error')
            return redirect(url_for('auth.register'))

        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'error')
            return redirect(url_for('auth.register'))
            
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'error')
            return redirect(url_for('auth.register'))

        user = User(username=username, email=email, role=role)
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('auth.login'))
        
    return render_template('auth/register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(get_role_dashboard(current_user.role))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = request.form.get('remember', False) == 'on'
        
        user = User.query.filter_by(username=username).first()
        
        if not user or not user.check_password(password):
            flash('Invalid username or password.', 'error')
            return render_template('auth/login.html')
            
        login_user(user, remember=remember)
        next_page = request.args.get('next')
        
        if not next_page or not next_page.startswith('/'):
            next_page = get_role_dashboard(user.role)
            
        return redirect(next_page)
        
    return render_template('auth/login.html')

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        
        if user:
            send_password_reset_email(user)
            flash('Password reset instructions have been sent to your email.', 'success')
            return redirect(url_for('auth.login'))
        
        flash('No account found with that email address.', 'error')
    return render_template('auth/forgot_password.html')

@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = User.query.filter_by(reset_token=token).first()
    
    if not user or not user.reset_token_expiry or user.reset_token_expiry < datetime.utcnow():
        flash('Invalid or expired reset link.', 'error')
        return redirect(url_for('auth.login'))
        
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('auth/reset_password.html')
            
        user.set_password(password)
        user.reset_token = None
        user.reset_token_expiry = None
        db.session.commit()
        
        flash('Your password has been reset successfully.', 'success')
        return redirect(url_for('auth.login'))
        
    return render_template('auth/reset_password.html')

@auth_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    if not current_user.check_password(current_password):
        flash('Current password is incorrect.', 'error')
        return redirect(url_for('auth.profile'))
        
    if new_password != confirm_password:
        flash('New passwords do not match.', 'error')
        return redirect(url_for('auth.profile'))
        
    current_user.set_password(new_password)
    db.session.commit()
    flash('Password updated successfully.', 'success')
    return redirect(url_for('auth.profile'))

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.index'))

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        lat = request.form.get('latitude')
        lng = request.form.get('longitude')
        address = request.form.get('address')
        
        if not address:
            flash('Address is required', 'error')
            return redirect(url_for('auth.profile'))
            
        try:
            lat_float = float(lat) if lat else None
            lng_float = float(lng) if lng else None
            
            if lat_float is not None and lng_float is not None:
                current_user.update_location(lat_float, lng_float, address)
            else:
                current_user.address = address
                current_user.location_lat = None
                current_user.location_lng = None
            
            db.session.commit()
            flash('Profile updated successfully!', 'success')
            
        except ValueError:
            flash('Invalid coordinates provided', 'error')
        
    return render_template('auth/profile.html')