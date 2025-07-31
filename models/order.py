from datetime import datetime, timedelta
from .. import db

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'), nullable=False)
    delivery_person_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    status = db.Column(db.String(20), nullable=False, default='pending')
    total_amount = db.Column(db.Float, nullable=False, default=0.0)
    delivery_fee = db.Column(db.Float, nullable=False, default=5.0)  # Default delivery fee
    delivery_address = db.Column(db.String(200), nullable=False)
    delivery_lat = db.Column(db.Float)
    delivery_lng = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    estimated_delivery_time = db.Column(db.DateTime)
    special_instructions = db.Column(db.Text)
    
    # Relationships
    items = db.relationship('OrderItem', backref='order', lazy=True, cascade='all, delete-orphan')
    customer = db.relationship('User', foreign_keys=[customer_id])
    delivery_person = db.relationship('User', foreign_keys=[delivery_person_id], backref='delivery_orders')
    
    def __init__(self, **kwargs):
        super(Order, self).__init__(**kwargs)
        self.status = 'pending'
        self.total_amount = 0.0

    def assign_delivery_person(self, delivery_person_id):
        self.delivery_person_id = delivery_person_id
        self.status = 'assigned'
        self.updated_at = datetime.utcnow()

    def update_status(self, new_status):
        """Update order status with proper validation and side effects"""
        valid_transitions = {
            'pending': ['confirmed', 'cancelled'],
            'confirmed': ['delivering', 'cancelled'],
            'delivering': ['completed', 'cancelled'],
            'completed': [],  # Final state
            'cancelled': []   # Final state
        }
        
        if new_status not in valid_transitions.get(self.status, []):
            raise ValueError(f'Invalid status transition from {self.status} to {new_status}')
        
        self.status = new_status
        self.updated_at = datetime.utcnow()
        
        if new_status == 'delivering':
            from ..utils.notifications import estimate_delivery_time
            minutes = estimate_delivery_time(self)
            self.estimated_delivery_time = datetime.utcnow() + timedelta(minutes=minutes)
        
        return True

    def calculate_total(self):
        self.total_amount = sum(item.subtotal for item in self.items)
        return self.total_amount

    def to_dict(self):
        return {
            'id': self.id,
            'customer': self.customer.to_dict() if self.customer else None,
            'shop': self.shop.to_dict() if self.shop else None,
            'delivery_person': self.delivery_person.to_dict() if self.delivery_person else None,
            'status': self.status,
            'total_amount': self.total_amount,
            'delivery_address': self.delivery_address,
            'delivery_location': {
                'lat': self.delivery_lat,
                'lng': self.delivery_lng
            } if self.delivery_lat and self.delivery_lng else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'estimated_delivery_time': self.estimated_delivery_time.isoformat() if self.estimated_delivery_time else None,
            'special_instructions': self.special_instructions,
            'items': [item.to_dict() for item in self.items]
        }

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    negotiated_price = db.Column(db.Float)
    
    # Relationships
    product = db.relationship('Product', backref='order_items')
    
    @property
    def subtotal(self):
        return (self.negotiated_price or self.price) * self.quantity

    def to_dict(self):
        return {
            'id': self.id,
            'product': self.product.to_dict(),
            'quantity': self.quantity,
            'price': self.price,
            'negotiated_price': self.negotiated_price,
            'subtotal': self.subtotal
        }