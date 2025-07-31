from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from .. import db

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(20), nullable=False, default='user')  # user, shop_owner, delivery, admin
    location_lat = db.Column(db.Float)
    location_lng = db.Column(db.Float)
    address = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    email_notifications = db.Column(db.Boolean, default=True)
    
    # Relationships
    orders = db.relationship('Order', lazy=True, foreign_keys='Order.customer_id')
    shop = db.relationship('Shop', backref='owner', lazy=True, uselist=False)
    deliveries = db.relationship('Order', backref='assigned_delivery_person', lazy=True, 
                               foreign_keys='Order.delivery_person_id')

    def __init__(self, username, email, role='user'):
        self.username = username
        self.email = email
        self.role = role

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def update_location(self, lat, lng, address):
        self.location_lat = lat
        self.location_lng = lng
        self.address = address
        self.updated_at = datetime.utcnow()

    @property
    def is_shop_owner(self):
        return self.role == 'shop_owner'

    @property
    def is_delivery_person(self):
        return self.role == 'delivery'

    @property
    def is_admin(self):
        return self.role == 'admin'

    @property
    def settings(self):
        return {
            'email_notifications': self.email_notifications
        }

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'location': {
                'lat': self.location_lat,
                'lng': self.location_lng,
                'address': self.address
            },
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }