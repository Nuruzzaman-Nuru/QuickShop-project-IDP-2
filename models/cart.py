from datetime import datetime
from .. import db

class Cart(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    items = db.relationship('CartItem', backref='cart', lazy=True)
    user = db.relationship('User', backref='cart')

    def __init__(self, user_id):
        self.user_id = user_id
    
    @property
    def total_amount(self):
        """Calculate total amount for all items in cart"""
        return sum(item.total_price for item in self.items)
    
    def to_dict(self):
        """Convert cart to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'items': [item.to_dict() for item in self.items],
            'total_amount': self.total_amount,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cart_id = db.Column(db.Integer, db.ForeignKey('cart.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    negotiated_price = db.Column(db.Float)  # Price after successful negotiation
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    product = db.relationship('Product', backref='cart_items')
    
    def __init__(self, cart_id, product_id, quantity=1, negotiated_price=None):
        self.cart_id = cart_id
        self.product_id = product_id
        self.quantity = quantity
        self.negotiated_price = negotiated_price
    
    @property
    def total_price(self):
        """Calculate total price for this cart item"""
        unit_price = self.negotiated_price or self.product.price
        return unit_price * self.quantity
    
    def to_dict(self):
        """Convert cart item to dictionary"""
        return {
            'id': self.id,
            'product': self.product.to_dict(),
            'quantity': self.quantity,
            'unit_price': self.negotiated_price or self.product.price,
            'total_price': self.total_price,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }