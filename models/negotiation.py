from datetime import datetime
from .. import db

class Negotiation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    initial_price = db.Column(db.Float, nullable=False)  # Original product price
    offered_price = db.Column(db.Float, nullable=False)  # Customer's offered price
    counter_price = db.Column(db.Float)  # AI/Shop counter offer
    final_price = db.Column(db.Float)  # Final agreed price
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending, counter_offer, accepted, rejected
    rounds = db.Column(db.Integer, default=0)  # Number of negotiation rounds
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    product = db.relationship('Product', backref='negotiations')
    customer = db.relationship('User', backref='negotiations')
    
    def __init__(self, product_id, customer_id, initial_price, offered_price):
        self.product_id = product_id
        self.customer_id = customer_id
        self.initial_price = initial_price
        self.offered_price = offered_price
        self.rounds = 1
    
    def add_counter_offer(self, price):
        """Add a counter offer from the AI/shop"""
        self.counter_price = price
        self.rounds += 1
        self.status = 'counter_offer'
        
    def accept_offer(self, price):
        """Accept an offer and set it as final price"""
        self.final_price = price
        self.status = 'accepted'
        
    def reject_offer(self):
        """Reject the current offer"""
        self.status = 'rejected'
        
    def to_dict(self):
        """Convert negotiation to dictionary"""
        return {
            'id': self.id,
            'product': self.product.to_dict(),
            'initial_price': self.initial_price,
            'offered_price': self.offered_price,
            'counter_price': self.counter_price,
            'final_price': self.final_price,
            'status': self.status,
            'rounds': self.rounds,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class DeliveryNegotiation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    initial_fee = db.Column(db.Float, nullable=False)  # Original delivery fee
    offered_fee = db.Column(db.Float, nullable=False)  # Customer's offered fee
    counter_fee = db.Column(db.Float)  # AI counter offer
    final_fee = db.Column(db.Float)  # Final agreed fee
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending, counter_offer, accepted, rejected
    rounds = db.Column(db.Integer, default=0)  # Number of negotiation rounds
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    order = db.relationship('Order', backref='delivery_negotiations')
    customer = db.relationship('User', backref='delivery_negotiations')

    def __init__(self, order_id, customer_id, initial_fee, offered_fee):
        self.order_id = order_id
        self.customer_id = customer_id
        self.initial_fee = initial_fee
        self.offered_fee = offered_fee
        self.rounds = 1

    def add_counter_offer(self, fee):
        """Add a counter offer from the AI"""
        self.counter_fee = fee
        self.rounds += 1
        self.status = 'counter_offer'
        
    def accept_offer(self, fee):
        """Accept an offer and set it as final fee"""
        self.final_fee = fee
        self.status = 'accepted'
        
    def reject_offer(self):
        """Reject the current offer"""
        self.status = 'rejected'