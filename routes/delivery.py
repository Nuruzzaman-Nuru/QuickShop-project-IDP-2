from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func
from datetime import datetime, timedelta
from ..models.order import Order
from ..models.user import User
from ..utils.notifications import notify_customer_order_status, notify_admin_order_status
from functools import wraps
from .. import db

delivery_bp = Blueprint('delivery', __name__, url_prefix='/delivery')

def delivery_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.role == 'delivery':
            flash('Access denied. Delivery person privileges required.', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

@delivery_bp.route('/dashboard')
@login_required
@delivery_required
def dashboard():
    # Get current active delivery
    current_delivery = Order.query.filter_by(
        delivery_person_id=current_user.id,
        status='delivering'
    ).first()
    
    # Get all active deliveries
    active_deliveries = Order.query.filter_by(
        delivery_person_id=current_user.id
    ).filter(Order.status.in_(['confirmed', 'delivering'])).all()
    
    # Get available orders (confirmed but no delivery person assigned)
    available_orders = Order.query.filter_by(
        status='confirmed',
        delivery_person_id=None
    ).all()
    
    # Calculate distances for available orders if delivery person has location
    if current_user.location_lat and current_user.location_lng:
        for order in available_orders:
            if order.delivery_lat and order.delivery_lng:
                order.distance = calculate_distance(
                    current_user.location_lat,
                    current_user.location_lng,
                    order.delivery_lat,
                    order.delivery_lng
                )
            else:
                order.distance = float('inf')
        available_orders.sort(key=lambda x: x.distance)
    
    # Get completed deliveries
    completed_deliveries = Order.query.filter_by(
        delivery_person_id=current_user.id,
        status='completed'
    ).order_by(Order.updated_at.desc()).limit(10).all()
    
    # Get today's stats
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    completed_today = Order.query.filter(
        Order.delivery_person_id == current_user.id,
        Order.status == 'completed',
        Order.updated_at >= today_start
    ).count()
    
    # Calculate total earnings
    total_earnings = db.session.query(func.sum(Order.delivery_fee))\
        .filter(Order.delivery_person_id == current_user.id,
                Order.status == 'completed')\
        .scalar() or 0.0
    
    return render_template('delivery/dashboard.html',
                         current_delivery=current_delivery,
                         active_deliveries=active_deliveries,
                         active_deliveries_count=len(active_deliveries),
                         available_orders=available_orders,
                         completed_deliveries=completed_deliveries,
                         completed_today=completed_today,
                         total_earnings=total_earnings)

@delivery_bp.route('/accept/<int:order_id>', methods=['POST'])
@login_required
@delivery_required
def accept_delivery(order_id):
    order = Order.query.get_or_404(order_id)
    
    # Check if order is available
    if order.status != 'confirmed' or order.delivery_person_id is not None:
        return jsonify({
            'status': 'error',
            'message': 'This order is not available for delivery'
        }), 400
    
    # Check if delivery person already has active deliveries
    active_count = Order.query.filter_by(
        delivery_person_id=current_user.id,
        status='delivering'
    ).count()
    
    if active_count >= 3:  # Limit concurrent deliveries
        return jsonify({
            'status': 'error',
            'message': 'You cannot accept more deliveries at this time'
        }), 400
    
    order.delivery_person_id = current_user.id
    order.status = 'delivering'
    order.estimated_delivery_time = datetime.now() + timedelta(hours=1)  # Default 1 hour estimate
    db.session.commit()
    
    # Send notifications
    notify_customer_order_status(order)
    notify_admin_order_status(order)
    
    return jsonify({'status': 'success'})

@delivery_bp.route('/delivery/<int:order_id>/update-status', methods=['POST'])
@login_required
@delivery_required
def update_delivery_status(order_id):
    order = Order.query.get_or_404(order_id)
    
    if order.delivery_person_id != current_user.id:
        return jsonify({
            'status': 'error',
            'message': 'You are not assigned to this delivery'
        }), 403
    
    data = request.get_json()
    new_status = data.get('status')
    
    try:
        # Update order status with validation
        if order.update_status(new_status):
            # Update location for delivering orders
            if new_status == 'delivering':
                current_user.location_lat = data.get('lat')
                current_user.location_lng = data.get('lng')
                
            db.session.commit()
            
            # Send notifications
            notify_customer_order_status(order)
            notify_admin_order_status(order)
            
            return jsonify({
                'status': 'success',
                'message': f'Order status updated to {new_status}'
            })
            
    except ValueError as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': 'An error occurred while updating order status'
        }), 500

@delivery_bp.route('/delivery/<int:order_id>/details')
@login_required
@delivery_required
def delivery_details(order_id):
    order = Order.query.get_or_404(order_id)
    
    if order.delivery_person_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('delivery.dashboard'))
        
    return render_template('delivery/delivery_details.html', order=order)

@delivery_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@delivery_required
def settings():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        address = request.form.get('address')
        lat = request.form.get('latitude')
        lng = request.form.get('longitude')
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        # Update basic info
        if username and email:
            current_user.username = username
            current_user.email = email
        
        # Update address and coordinates
        if address:
            current_user.address = address
            try:
                if lat and lng:
                    current_user.location_lat = float(lat)
                    current_user.location_lng = float(lng)
                else:
                    current_user.location_lat = None
                    current_user.location_lng = None
            except ValueError:
                flash('Invalid coordinates provided.', 'error')
                return redirect(url_for('delivery.settings'))
        
        # Update password if provided
        if current_password and new_password and confirm_password:
            if not current_user.check_password(current_password):
                flash('Current password is incorrect.', 'error')
                return redirect(url_for('delivery.settings'))
                
            if new_password != confirm_password:
                flash('New passwords do not match.', 'error')
                return redirect(url_for('delivery.settings'))
                
            current_user.set_password(new_password)
        
        try:
            db.session.commit()
            flash('Settings updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Error updating settings.', 'error')
            
    return render_template('delivery/settings.html')

@delivery_bp.route('/update-location', methods=['POST'])
@login_required
@delivery_required
def update_location():
    """Update delivery person's current location"""
    data = request.get_json()
    lat = data.get('lat')
    lng = data.get('lng')
    
    if not all([lat, lng]):
        return jsonify({
            'status': 'error',
            'message': 'Coordinates are required'
        }), 400
    
    try:
        current_user.location_lat = float(lat)
        current_user.location_lng = float(lng)
        current_user.location_updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Location updated successfully'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two points in kilometers using Haversine formula"""
    from math import radians, sin, cos, sqrt, atan2
    
    R = 6371  # Earth's radius in kilometers
    
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    distance = R * c
    
    return distance