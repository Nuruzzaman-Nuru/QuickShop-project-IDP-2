from flask import Blueprint, jsonify, request, session, url_for
from flask_login import login_required, current_user
from ..models.user import User
from ..models.shop import Shop, Product
from ..models.order import Order, OrderItem
from ..models.negotiation import Negotiation, DeliveryNegotiation
from ..models.cart import Cart, CartItem  # Add this line
from ..utils.ai.negotiation_bot import create_negotiation_session, create_delivery_negotiation_session, process_delivery_negotiation
from ..utils.notifications import (
    notify_shop_owner_new_order,
    notify_customer_order_status,
    notify_admin_order_status
)
from ..utils.distance import calculate_distance
from .. import db
from sqlalchemy import or_, and_
from ..routes.auth import customer_required

api_bp = Blueprint('api', __name__, url_prefix='/api')

def init_cart():
    """Initialize cart in session if it doesn't exist"""
    if 'cart' not in session:
        session['cart'] = {}
        session.modified = True
    return session['cart']

@api_bp.route('/delivery/location/<int:delivery_person_id>')
def get_delivery_location(delivery_person_id):
    """Get the current location of a delivery person"""
    delivery_person = User.query.get_or_404(delivery_person_id)
    
    if not delivery_person.is_delivery_person:
        return jsonify({
            'status': 'error',
            'message': 'Invalid delivery person ID'
        }), 404
    
    # Get the active delivery for this person
    active_delivery = Order.query.filter_by(
        delivery_person_id=delivery_person_id,
        status='delivering'
    ).first()
    
    if not active_delivery:
        return jsonify({
            'status': 'error',
            'message': 'No active delivery found'
        }), 404
    
    # Get the latest location
    location = {
        'lat': delivery_person.location_lat,
        'lng': delivery_person.location_lng,
        'last_updated': delivery_person.location_updated_at.isoformat() if delivery_person.location_updated_at else None
    }
    
    return jsonify({
        'status': 'success',
        'location': location
    })

@api_bp.route('/admin/delivery-status')
@login_required
def delivery_status():
    if not current_user.is_admin:
        return jsonify({
            'status': 'error',
            'message': 'Admin access required'
        }), 403
    
    delivery_persons = User.query.filter_by(role='delivery').all()
    status_data = []
    
    for person in delivery_persons:
        current_order = Order.query.filter_by(
            delivery_person_id=person.id,
            status='in_delivery'
        ).first()
        
        status_data.append({
            'username': person.username,
            'status': 'active' if current_order else 'available',
            'currentOrder': f'#{current_order.id}' if current_order else None,
            'lastUpdated': person.updated_at.isoformat() if hasattr(person, 'updated_at') else None
        })
    
    return jsonify({
        'status': 'success',
        'deliveryPersons': status_data
    })

@api_bp.route('/admin/dashboard-stats')
@login_required
def dashboard_stats():
    if not current_user.is_admin:
        return jsonify({
            'status': 'error',
            'message': 'Admin access required'
        }), 403
    
    try:
        # Get current stats
        pending_orders = Order.query.filter_by(status='pending').count()
        active_deliveries = Order.query.filter_by(status='in_delivery').count()
        
        # Get recent orders
        recent_orders = Order.query.order_by(Order.created_at.desc()).limit(10).all()
        
        return jsonify({
            'status': 'success',
            'pending_orders': pending_orders,
            'active_deliveries': active_deliveries,
            'recent_orders': [order.to_dict() for order in recent_orders]
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@api_bp.route('/add', methods=['POST'])
@login_required
@customer_required
def add_to_cart():
    try:
        init_cart()
        data = request.get_json()
        
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'Invalid request data'
            }), 400

        product_id = str(data.get('product_id'))
        quantity = int(data.get('quantity', 1))
        
        # Validate product exists
        product = Product.query.get_or_404(product_id)
        
        # Validate product is in stock
        if not product.stock:
            return jsonify({
                'status': 'error',
                'message': 'Product is out of stock'
            }), 400
        
        # Calculate total quantity including what's already in cart
        current_quantity = session['cart'].get(product_id, {}).get('quantity', 0)
        total_quantity = current_quantity + quantity
        
        # Validate stock availability
        if product.stock < total_quantity:
            return jsonify({
                'status': 'error',
                'message': f'Only {product.stock} items available'
            }), 400
            
        # Update or add cart item
        session['cart'][product_id] = {
            'quantity': total_quantity,
            'price': float(product.price),
            'name': product.name,
            'shop_id': product.shop_id,
            'shop_name': product.shop.name
        }
        session.modified = True
        
        # Calculate total items in cart
        cart_count = sum(item['quantity'] for item in session['cart'].values())
        
        return jsonify({
            'status': 'success',
            'message': 'Product added to cart',
            'cart_count': cart_count
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@api_bp.route('/update', methods=['POST'])
@login_required
@customer_required
def update_cart():
    try:
        data = request.get_json()
        product_id = str(data.get('product_id'))
        quantity = int(data.get('quantity', 0))
        
        if quantity <= 0:
            if product_id in session['cart']:
                del session['cart'][product_id]
                session.modified = True
        else:
            product = Product.query.get_or_404(product_id)
            if product.stock < quantity:
                return jsonify({
                    'status': 'error',
                    'message': f'Only {product.stock} items available'
                }), 400
                
            if product_id in session['cart']:
                session['cart'][product_id]['quantity'] = quantity
                session.modified = True
        
        cart_total = sum(item['quantity'] * item['price'] for item in session['cart'].values())
        cart_count = sum(item['quantity'] for item in session['cart'].values())
        
        return jsonify({
            'status': 'success',
            'message': 'Cart updated',
            'cart_total': cart_total,
            'cart_count': cart_count
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@api_bp.route('/remove', methods=['POST'])
@login_required
@customer_required
def remove_from_cart():
    data = request.get_json()
    product_id = str(data.get('product_id'))
    
    if product_id in session['cart']:
        del session['cart'][product_id]
        session.modified = True
    
    return jsonify({
        'status': 'success',
        'message': 'Item removed from cart'
    })

@api_bp.route('/checkout', methods=['POST'])
@login_required
@customer_required
def checkout():
    init_cart()
    data = request.get_json()
    selected_items = data.get('selected_items', [])
    
    if not selected_items:
        return jsonify({
            'status': 'error',
            'message': 'No items selected for checkout'
        }), 400
    
    # Get shipping address from session
    shipping = session.get('cart_shipping', {})
    if not shipping:
        return jsonify({
            'status': 'error',
            'message': 'Please select a shipping address'
        }), 400
    
    # Group selected items by shop
    shop_orders = {}
    cart = session['cart']
    
    for item_id in selected_items:
        if item_id not in cart:
            continue
            
        item = cart[item_id]
        product = Product.query.get(item_id)
        if not product or product.stock < item['quantity']:
            return jsonify({
                'status': 'error',
                'message': f'Not enough stock for {product.name}'
            }), 400
            
        if product.shop_id not in shop_orders:
            shop_orders[product.shop_id] = []
            
        shop_orders[product.shop_id].append({
            'product': product,
            'quantity': item['quantity'],
            'price': item['price']
        })
    
    try:
        # Create separate orders for each shop
        orders = []
        for shop_id, items in shop_orders.items():
            order = Order(
                customer_id=current_user.id,
                shop_id=shop_id,
                delivery_address=shipping['address'],
                delivery_lat=shipping['lat'],
                delivery_lng=shipping['lng']
            )
            order.special_instructions = data.get('special_instructions', '')
            db.session.add(order)
            
            # Add items to order
            total_amount = 0
            for item in items:
                order_item = OrderItem(
                    order=order,
                    product_id=item['product'].id,
                    quantity=item['quantity'],
                    price=item['price']
                )
                db.session.add(order_item)
                
                # Update product stock
                item['product'].stock -= item['quantity']
                total_amount += item['quantity'] * item['price']
            
            order.total_amount = total_amount
            orders.append(order)
        
        db.session.commit()
        
        # Remove checked out items from cart
        for item_id in selected_items:
            if item_id in session['cart']:
                del session['cart'][item_id]
        session.modified = True
        
        # Send notifications
        for order in orders:
            notify_shop_owner_new_order(order)
            notify_customer_order_status(order)
            notify_admin_order_status(order, {
                'old': None,
                'new': 'pending',
                'action': 'order_created'
            })
        
        return jsonify({
            'status': 'success',
            'message': 'Orders placed successfully',
            'order_ids': [order.id for order in orders]
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@api_bp.route('/cart/count')
@login_required
@customer_required
def get_cart_count():
    """Get the total number of items in cart (sum of quantities)"""
    cart = init_cart()
    count = sum(item['quantity'] for item in cart.values())
    return jsonify({
        'status': 'success',
        'count': count
    })

@api_bp.route('/cart/items')
@login_required
@customer_required
def get_cart_items():
    cart = init_cart()
    items = []
    total = 0
    
    for product_id, item in cart.items():
        product = Product.query.get(product_id)
        if product:
            price = item['price']
            quantity = item['quantity']
            subtotal = price * quantity
            total += subtotal
            
            items.append({
                'id': product_id,
                'name': product.name,
                'image_url': product.image_url,
                'price': price,
                'quantity': quantity,
                'stock': product.stock,
                'subtotal': subtotal,
                'shop_id': product.shop_id,
                'shop_name': product.shop.name
            })
    
    return jsonify({
        'status': 'success',
        'items': items,
        'total': total,
        'count': sum(item['quantity'] for item in cart.values())
    })

@api_bp.route('/cart/change', methods=['POST'])
@login_required
@customer_required
def notify_cart_change():
    """Notify about cart changes for real-time updates"""
    init_cart()
    data = request.get_json()
    action = data.get('action')
    product_id = str(data.get('product_id', ''))
    
    if action not in ['add', 'remove', 'update', 'clear']:
        return jsonify({
            'status': 'error',
            'message': 'Invalid action'
        }), 400
    
    if action == 'clear':
        session['cart'] = {}
        session.modified = True
    
    count = sum(item['quantity'] for item in session['cart'].values())
    total = sum(item['quantity'] * item['price'] for item in session['cart'].values())
    
    return jsonify({
        'status': 'success',
        'cart': {
            'count': count,
            'total': total,
            'action': action,
            'product_id': product_id
        }
    })

@api_bp.route('/cart/apply-voucher', methods=['POST'])
@login_required
@customer_required
def apply_voucher():
    """Apply a voucher code to the cart"""
    data = request.get_json()
    code = data.get('code')
    
    if not code:
        return jsonify({
            'status': 'error',
            'message': 'Voucher code is required'
        }), 400
    
    # TODO: Add voucher validation logic
    # For now, return error for any code
    return jsonify({
        'status': 'error',
        'message': 'Invalid or expired voucher code'
    }), 400

@api_bp.route('/cart/batch-delete', methods=['POST'])
@login_required
@customer_required
def batch_delete_cart_items():
    """Delete multiple items from cart at once"""
    data = request.get_json()
    item_ids = data.get('item_ids', [])
    
    cart = init_cart()
    for item_id in item_ids:
        if str(item_id) in cart:
            del cart[str(item_id)]
    
    session.modified = True
    
    return jsonify({
        'status': 'success',
        'message': 'Items removed from cart'
    })

@api_bp.route('/cart/shipping-address', methods=['GET', 'POST'])
@login_required
@customer_required
def cart_shipping_address():
    """Get or update shipping address for cart"""
    if request.method == 'POST':
        data = request.get_json()
        address = data.get('address')
        lat = data.get('lat')
        lng = data.get('lng')
        
        if not all([address, lat, lng]):
            return jsonify({
                'status': 'error',
                'message': 'Address and coordinates are required'
            }), 400
        
        session['cart_shipping'] = {
            'address': address,
            'lat': float(lat),
            'lng': float(lng)
        }
        session.modified = True
        
        return jsonify({
            'status': 'success',
            'message': 'Shipping address updated'
        })
    
    # GET request - return current shipping address
    shipping = session.get('cart_shipping', {})
    return jsonify({
        'status': 'success',
        'address': shipping.get('address'),
        'lat': shipping.get('lat'),
        'lng': shipping.get('lng')
    })

@api_bp.route('/product/<int:product_id>/negotiate', methods=['POST'])
@login_required
def negotiate_price(product_id):
    product = Product.query.get_or_404(product_id)
    data = request.get_json()
    
    # Check if product allows negotiation
    if not product.is_negotiable():
        return jsonify({
            'status': 'error',
            'message': 'This product does not support price negotiation'
        }), 400
    
    # Get or create negotiation
    negotiation = Negotiation.query.filter_by(
        product_id=product_id,
        customer_id=current_user.id,
        status='pending'
    ).first()
    
    if not negotiation:
        negotiation = Negotiation(
            product_id=product_id,
            customer_id=current_user.id,
            initial_price=product.price,
            offered_price=data['offered_price']
        )
        db.session.add(negotiation)
    else:
        # Check if further negotiation is allowed
        if negotiation.status == 'counter_offer' and not product.allow_continue_iteration():
            return jsonify({
                'status': 'error',
                'message': 'Further negotiation is not allowed for this product'
            }), 400
        
        negotiation.offered_price = data['offered_price']
        negotiation.rounds += 1
    
    # Check if price is acceptable
    if product.can_negotiate_price(data['offered_price']):
        negotiation.status = 'accepted'
        negotiation.final_price = data['offered_price']
    else:
        # Calculate counter offer
        discount = (product.price - product.min_price) * 0.7  # Allow 70% of maximum possible discount
        counter_price = max(product.price - discount, product.min_price)
        
        negotiation.status = 'counter_offer'
        negotiation.counter_price = counter_price
    
    try:
        db.session.commit()
        return jsonify({
            'status': 'success',
            'negotiation': {
                'status': negotiation.status,
                'counter_price': negotiation.counter_price,
                'final_price': negotiation.final_price
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': 'Error processing negotiation'
        }), 500

@api_bp.route('/negotiation/<int:negotiation_id>/accept', methods=['POST'])
@login_required
def accept_negotiation(negotiation_id):
    negotiation = Negotiation.query.get_or_404(negotiation_id)
    
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
    
    # Accept the last counter offer
    if negotiation.counter_price:
        # Update negotiation status
        negotiation.accept_offer(negotiation.counter_price)
        
        # Add item to cart with negotiated price
        cart = Cart.query.filter_by(user_id=current_user.id).first()
        if not cart:
            cart = Cart(user_id=current_user.id)
            db.session.add(cart)
        
        # Check if product already in cart
        cart_item = CartItem.query.filter_by(
            cart_id=cart.id,
            product_id=negotiation.product_id
        ).first()
        
        if cart_item:
            cart_item.negotiated_price = negotiation.final_price
        else:
            cart_item = CartItem(
                cart_id=cart.id,
                product_id=negotiation.product_id,
                quantity=1,
                negotiated_price=negotiation.final_price
            )
            db.session.add(cart_item)
        
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Negotiation accepted and item added to cart',
            'final_price': negotiation.final_price
        })
    else:
        return jsonify({
            'status': 'error',
            'message': 'No counter offer available'
        }), 400

@api_bp.route('/negotiate/delivery/<int:order_id>', methods=['POST'])
@login_required
def negotiate_delivery_fee(order_id):
    """Start or continue a delivery fee negotiation"""
    order = Order.query.get_or_404(order_id)
    
    if order.customer_id != current_user.id:
        return jsonify({
            'status': 'error',
            'message': 'Access denied'
        }), 403
    
    data = request.get_json()
    offered_fee = float(data.get('offered_fee'))
    
    # Get existing negotiation or create new one
    negotiation = DeliveryNegotiation.query.filter_by(
        order_id=order_id,
        customer_id=current_user.id,
        status='pending'
    ).first()
    
    if not negotiation:
        # Calculate base delivery fee based on distance
        from ..utils.distance import calculate_distance
        distance = calculate_distance(
            order.shop.location_lat,
            order.shop.location_lng,
            order.delivery_lat,
            order.delivery_lng
        )
        base_fee = max(5.00, 3.00 + (distance * 0.75))  # $3 base + $0.75 per km
        
        negotiation = DeliveryNegotiation(
            order_id=order_id,
            customer_id=current_user.id,
            initial_fee=base_fee,
            offered_fee=offered_fee
        )
        db.session.add(negotiation)
    else:
        negotiation.offered_fee = offered_fee
        negotiation.rounds += 1
    
    # Process with AI negotiation bot
    bot = create_delivery_negotiation_session(order)
    decision, counter_fee, message = bot.evaluate_offer(offered_fee)
    
    if decision == 'accept':
        negotiation.accept_offer(offered_fee)
        # Update order with negotiated delivery fee
        order.delivery_fee = offered_fee
    elif decision == 'reject':
        negotiation.reject_offer()
    else:  # counter
        negotiation.add_counter_offer(counter_fee)
        
    db.session.commit()
    
    return jsonify({
        'status': 'success',
        'decision': decision,
        'message': message,
        'counter_fee': counter_fee,
        'negotiation': {
            'id': negotiation.id,
            'initial_fee': negotiation.initial_fee,
            'offered_fee': negotiation.offered_fee,
            'counter_fee': negotiation.counter_fee,
            'final_fee': negotiation.final_fee,
            'status': negotiation.status,
            'rounds': negotiation.rounds
        }
    })

@api_bp.route('/negotiate/delivery/<int:negotiation_id>/accept', methods=['POST'])
@login_required
def accept_delivery_negotiation(negotiation_id):
    """Accept a delivery fee counter-offer"""
    negotiation = DeliveryNegotiation.query.get_or_404(negotiation_id)
    
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
    
    # Accept the last counter offer
    if negotiation.counter_fee:
        negotiation.accept_offer(negotiation.counter_fee)
        # Update order with negotiated delivery fee
        negotiation.order.delivery_fee = negotiation.counter_fee
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Delivery fee negotiation accepted',
            'final_fee': negotiation.final_fee
        })
    else:
        return jsonify({
            'status': 'error',
            'message': 'No counter offer available'
        }), 400

@api_bp.route('/search/suggestions')
def search_suggestions():
    query = request.args.get('q', '')
    shop_id = request.args.get('shop_id', type=int)
    
    if not query or len(query) < 2:
        return jsonify([])
    
    # Base product query
    product_query = Product.query
    
    # If shop_id is provided, limit to that shop's products
    if shop_id:
        product_query = product_query.filter(Product.shop_id == shop_id)
    else:
        # Only show products from active shops
        product_query = product_query.filter(Product.shop.has(Shop.is_active == True))
    
    # Get matching products
    products = product_query.filter(
        or_(
            Product.name.ilike(f'%{query}%'),
            Product.description.ilike(f'%{query}%'),
            Product.category.ilike(f'%{query}%')
        )
    ).limit(5).all()
    
    # Get matching shops if not searching within a specific shop
    shops = []
    if not shop_id:
        shops = Shop.query.filter(
            and_(
                Shop.is_active == True,
                or_(
                    Shop.name.ilike(f'%{query}%'),
                    Shop.description.ilike(f'%{query}%')
                )
            )
        ).limit(3).all()
    
    # Format suggestions
    results = []
    
    # Add product suggestions
    for product in products:
        results.append({
            'name': product.name,
            'type': 'product',
            'url': url_for('shop.view', shop_id=product.shop_id, highlight=product.id),
            'category': product.category,
            'price': float(product.price)
        })
    
    # Add shop suggestions
    for shop in shops:
        results.append({
            'name': shop.name,
            'type': 'shop',
            'url': url_for('shop.view', shop_id=shop.id)
        })
    
    # Deduplicate and limit results while preserving order
    seen = set()
    unique_results = []
    for item in results:
        if item['name'] not in seen:
            seen.add(item['name'])
            unique_results.append(item)
    
    return jsonify(unique_results[:5])

@api_bp.route('/calculate-shipping', methods=['POST'])
@login_required
def calculate_shipping():
    data = request.get_json()
    lat = data.get('lat')
    lng = data.get('lng')
    
    if not all([lat, lng]):
        return jsonify({
            'status': 'error',
            'message': 'Coordinates are required'
        }), 400
    
    # Get shop coordinates from the cart items' shops
    cart = session.get('cart', {})
    shop_distances = []
    
    for product_id in cart:
        product = Product.query.get(product_id)
        if product and product.shop:
            shop = product.shop
            if shop.location_lat and shop.location_lng:
                distance = calculate_distance(
                    shop.location_lat,
                    shop.location_lng,
                    float(lat),
                    float(lng)
                )
                shop_distances.append(distance)
    
    if not shop_distances:
        return jsonify({
            'status': 'error',
            'message': 'Unable to calculate shipping - shop location not available'
        }), 400
    
    # Use the maximum distance to calculate base shipping fee
    max_distance = max(shop_distances)
    base_fee = max(5.00, 3.00 + (max_distance * 0.75))  # $3 base + $0.75 per km
    
    return jsonify({
        'status': 'success',
        'shipping_fee': base_fee,
        'distance': max_distance,
        'is_negotiable': True
    })