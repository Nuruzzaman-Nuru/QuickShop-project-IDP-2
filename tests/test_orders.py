import unittest
from datetime import datetime
from ecommerce import create_app, db
from ecommerce.models.user import User
from ecommerce.models.shop import Shop, Product
from ecommerce.models.order import Order, OrderItem
from ecommerce.utils.notifications import send_order_status_update

class OrderTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.client = self.app.test_client()
        
        # Create test users
        self.customer = User(
            username='testcustomer',
            email='customer@test.com',
            role='user'
        )
        self.customer.set_password('password')
        
        self.shop_owner = User(
            username='testshopowner',
            email='owner@test.com',
            role='shop_owner'
        )
        self.shop_owner.set_password('password')
        
        self.delivery_person = User(
            username='testdelivery',
            email='delivery@test.com',
            role='delivery'
        )
        self.delivery_person.set_password('password')
        
        # Create test shop
        self.shop = Shop(
            name='Test Shop',
            description='Test shop description',
            owner_id=2,  # Will be set after commit
            location_lat=40.7128,
            location_lng=-74.0060,
            address='123 Test St'
        )
        
        # Create test product
        self.product = Product(
            name='Test Product',
            description='Test product description',
            price=10.00,
            stock=100,
            shop_id=1,  # Will be set after commit
            min_price=8.00,
            max_discount_percentage=20.0
        )
        
        # Add to database
        db.session.add(self.customer)
        db.session.add(self.shop_owner)
        db.session.add(self.delivery_person)
        db.session.commit()
        
        self.shop.owner_id = self.shop_owner.id
        db.session.add(self.shop)
        db.session.commit()
        
        self.product.shop_id = self.shop.id
        db.session.add(self.product)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_create_order(self):
        order = Order(
            customer_id=self.customer.id,
            shop_id=self.shop.id,
            delivery_address='456 Delivery St',
            delivery_lat=40.7129,
            delivery_lng=-74.0061
        )
        db.session.add(order)
        db.session.commit()
        
        self.assertIsNotNone(order.id)
        self.assertEqual(order.status, 'pending')
        self.assertEqual(order.total_amount, 0.0)

    def test_add_order_items(self):
        order = Order(
            customer_id=self.customer.id,
            shop_id=self.shop.id,
            delivery_address='456 Delivery St',
            delivery_lat=40.7129,
            delivery_lng=-74.0061
        )
        db.session.add(order)
        db.session.commit()
        
        item = OrderItem(
            order_id=order.id,
            product_id=self.product.id,
            quantity=2,
            price=self.product.price
        )
        db.session.add(item)
        db.session.commit()
        
        order.calculate_total()
        db.session.commit()
        
        self.assertEqual(order.total_amount, 20.00)
        self.assertEqual(len(order.items), 1)

    def test_assign_delivery_person(self):
        order = Order(
            customer_id=self.customer.id,
            shop_id=self.shop.id,
            delivery_address='456 Delivery St',
            delivery_lat=40.7129,
            delivery_lng=-74.0061
        )
        db.session.add(order)
        db.session.commit()
        
        order.assign_delivery_person(self.delivery_person.id)
        db.session.commit()
        
        self.assertEqual(order.delivery_person_id, self.delivery_person.id)
        self.assertEqual(order.status, 'in_delivery')

    def test_order_status_updates(self):
        order = Order(
            customer_id=self.customer.id,
            shop_id=self.shop.id,
            delivery_address='456 Delivery St',
            delivery_lat=40.7129,
            delivery_lng=-74.0061
        )
        db.session.add(order)
        db.session.commit()
        
        # Test status transitions
        order.assign_delivery_person(self.delivery_person.id)
        self.assertEqual(order.status, 'in_delivery')
        
        order.status = 'delivered'
        db.session.commit()
        self.assertEqual(order.status, 'delivered')