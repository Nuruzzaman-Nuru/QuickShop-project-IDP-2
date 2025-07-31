from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, session
from flask_login import login_required, current_user
from sqlalchemy import func, or_, and_, desc, asc, cast, String, case
from ..models.order import Order, OrderItem
from ..models.shop import Shop, Product
from ..models.user import User
from ..models.cart import CartItem
from ..models.negotiation import Negotiation
from ..utils.notifications import notify_customer_order_status, notify_admin_order_status
from ..utils.ai.negotiation_bot import process_negotiation
from datetime import datetime
from .. import db
from ..routes.auth import customer_required

user_bp = Blueprint('user', __name__, url_prefix='/user')

@user_bp.route('/dashboard')
@login_required
def dashboard():
    # Get active orders (pending, confirmed, delivering)
    active_orders = Order.query.filter(
        Order.customer_id == current_user.id,
        Order.status.in_(['pending', 'confirmed', 'delivering'])
    ).order_by(Order.created_at.desc()).all()

    # Get recent orders
    recent_orders = Order.query.filter_by(
        customer_id=current_user.id
    ).order_by(Order.created_at.desc()).limit(5).all()

    # Initialize cart and get cart items count
    if 'cart' not in session:
        session['cart'] = {}
    cart_items_count = sum(item['quantity'] for item in session['cart'].values())
        
    # Get pending negotiations
    pending_negotiations = Negotiation.query.filter_by(
        customer_id=current_user.id,
        status='pending'
    ).count()

    return render_template('user/dashboard.html',
                         active_orders=active_orders,
                         active_orders_count=len(active_orders),
                         cart_items_count=cart_items_count,
                         pending_negotiations=pending_negotiations,
                         recent_orders=recent_orders)

@user_bp.route('/orders')
@login_required
@customer_required
def orders():
    # Get search and filter parameters
    search_query = request.args.get('q', '')
    status = request.args.get('status')
    sort = request.args.get('sort', 'newest')
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    # Base query
    query = Order.query.filter_by(customer_id=current_user.id)
    
    # Apply search filter
    if search_query:
        query = query.join(Order.shop).join(Order.items).join(OrderItem.product).filter(
            or_(
                Order.id.cast(String).ilike(f'%{search_query}%'),
                Shop.name.ilike(f'%{search_query}%'),
                Product.name.ilike(f'%{search_query}%')
            )
        ).distinct()
    
    # Get counts for status tabs before applying status filter
    status_counts = {
        'all': query.count(),
        'pending': query.filter(Order.status == 'pending').count(),
        'confirmed': query.filter(Order.status == 'confirmed').count(),
        'delivering': query.filter(Order.status == 'delivering').count(),
        'completed': query.filter(Order.status == 'completed').count(),
        'cancelled': query.filter(Order.status == 'cancelled').count()
    }
    
    # Apply status filter
    if status:
        query = query.filter_by(status=status)
    
    # Apply sorting
    if sort == 'oldest':
        query = query.order_by(Order.created_at.asc())
    elif sort == 'highest':
        query = query.order_by(Order.total_amount.desc())
    elif sort == 'lowest':
        query = query.order_by(Order.total_amount.asc())
    else:  # newest
        query = query.order_by(Order.created_at.desc())
    
    # Paginate results
    pagination = query.paginate(page=page, per_page=per_page)
    orders = pagination.items
    
    return render_template('user/orders.html', 
                         orders=orders,
                         pagination=pagination,
                         status_counts=status_counts,
                         current_status=status,
                         current_sort=sort,
                         search_query=search_query)

@user_bp.route('/order/<int:order_id>')
@login_required
@customer_required
def order_detail(order_id):
    order = Order.query.get_or_404(order_id)
    if order.customer_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('user.orders'))
    return render_template('user/order_detail.html', order=order)

@user_bp.route('/track-order/<int:order_id>')
@login_required
@customer_required
def track_order(order_id):
    order = Order.query.get_or_404(order_id)
    if order.customer_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('user.orders'))
    return render_template('user/track_order.html', order=order)

@user_bp.route('/negotiations')
@login_required
def negotiations():
    # Get search and filter parameters
    search_query = request.args.get('q', '').strip()
    status = request.args.get('status')
    sort = request.args.get('sort', 'newest')
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    # Base query - eager load product and shop to avoid N+1 queries
    query = Negotiation.query.join(Negotiation.product).join(Product.shop)
    
    # Filter by current user
    query = query.filter(Negotiation.customer_id == current_user.id)
    
    # Apply search filter
    if search_query:
        query = query.filter(
            or_(
                Product.name.ilike(f'%{search_query}%'),
                Shop.name.ilike(f'%{search_query}%'),
                Product.category.ilike(f'%{search_query}%')
            )
        )
    
    # Apply status filter
    if status:
        query = query.filter(Negotiation.status == status)
    
    # Apply sorting
    if sort == 'oldest':
        query = query.order_by(Negotiation.created_at.asc())
    elif sort == 'highest_offer':
        query = query.order_by(Negotiation.offered_price.desc())
    elif sort == 'lowest_offer':
        query = query.order_by(Negotiation.offered_price.asc())
    else:  # newest
        query = query.order_by(Negotiation.created_at.desc())
    
    # Paginate results
    pagination = query.paginate(page=page, per_page=per_page)
    negotiations = pagination.items
    
    return render_template('user/negotiations.html',
                         negotiations=negotiations,
                         pagination=pagination)

@user_bp.route('/negotiation/<int:nego_id>')
@login_required
def negotiation_detail(nego_id):
    negotiation = Negotiation.query.get_or_404(nego_id)
    if negotiation.customer_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('user.negotiations'))
    return render_template('user/negotiation_detail.html', negotiation=negotiation)

@user_bp.route('/negotiation/<int:nego_id>/counter', methods=['POST'])
@login_required
def make_counter_offer(nego_id):
    negotiation = Negotiation.query.get_or_404(nego_id)
    if negotiation.customer_id != current_user.id:
        return jsonify({
            'status': 'error',
            'message': 'Access denied'
        }), 403
    
    if negotiation.status not in ['pending', 'counter_offer']:
        return jsonify({
            'status': 'error',
            'message': 'This negotiation is no longer active'
        }), 400
    
    try:
        offered_price = float(request.json.get('offered_price'))
        if offered_price <= 0:
            raise ValueError()
    except (TypeError, ValueError):
        return jsonify({
            'status': 'error',
            'message': 'Invalid offer amount'
        }), 400
    
    negotiation.offered_price = offered_price
    negotiation.rounds += 1
    
    # Process with negotiation bot
    decision, counter_offer, message = process_negotiation(negotiation)
    
    if decision == 'accept':
        negotiation.status = 'accepted'
        negotiation.final_price = offered_price
    elif decision == 'reject':
        negotiation.status = 'rejected'
    else:
        negotiation.status = 'counter_offer'
        negotiation.counter_price = counter_offer
    
    db.session.commit()
    
    return jsonify({
        'status': 'success',
        'decision': decision,
        'counter_offer': counter_offer,
        'message': message
    })

@user_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        address = request.form.get('address')
        lat = request.form.get('latitude')
        lng = request.form.get('longitude')
        email_notifications = 'email_notifications' in request.form
        
        if username and email:  # Basic validation
            current_user.username = username
            current_user.email = email
            current_user.address = address
            current_user.location_lat = float(lat) if lat else None
            current_user.location_lng = float(lng) if lng else None
            current_user.email_notifications = email_notifications
            
            try:
                db.session.commit()
                flash('Settings updated successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash('Error updating settings.', 'error')
                
    return render_template('user/settings.html', user=current_user)