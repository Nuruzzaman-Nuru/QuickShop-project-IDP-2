import unittest
from ecommerce.models.shop import Product
from ecommerce.utils.ai.negotiation_bot import NegotiationBot, create_negotiation_session

class NegotiationTestCase(unittest.TestCase):
    def setUp(self):
        self.product = Product(
            name='Test Product',
            price=100.00,
            min_price=80.00,
            max_discount_percentage=20.0
        )
        self.negotiation_bot = create_negotiation_session(self.product)

    def test_acceptable_offer(self):
        # Test an offer within acceptable range
        decision, counter_offer, message = self.negotiation_bot.evaluate_offer(85.00)
        self.assertEqual(decision, 'accept')
        self.assertIsNone(counter_offer)
        self.assertTrue('deal' in message.lower())

    def test_too_low_offer(self):
        # Test an offer below minimum price
        decision, counter_offer, message = self.negotiation_bot.evaluate_offer(75.00)
        self.assertEqual(decision, 'reject')
        self.assertIsNone(counter_offer)
        self.assertTrue('too low' in message.lower())

    def test_counter_offer(self):
        # Test an offer that requires negotiation
        decision, counter_offer, message = self.negotiation_bot.evaluate_offer(82.00)
        self.assertEqual(decision, 'counter')
        self.assertIsNotNone(counter_offer)
        self.assertTrue(counter_offer > 82.00)
        self.assertTrue(counter_offer <= self.product.price)

    def test_multiple_rounds_negotiation(self):
        # Test negotiation behavior over multiple rounds
        initial_offer = 82.00
        
        # First round
        decision1, counter1, _ = self.negotiation_bot.evaluate_offer(initial_offer)
        self.assertEqual(decision1, 'counter')
        
        # Second round with slightly higher offer
        decision2, counter2, _ = self.negotiation_bot.evaluate_offer(counter1 - 5)
        self.assertEqual(decision2, 'counter')
        
        # Verify counter offers are getting closer
        self.assertTrue(counter2 < counter1)
        
        # Third round
        decision3, counter3, _ = self.negotiation_bot.evaluate_offer(counter2 - 2)
        self.assertTrue(decision3 in ['accept', 'counter'])  # Might accept by now

    def test_negotiation_bounds(self):
        # Test that counter offers stay within bounds
        for i in range(10):  # Multiple rounds
            decision, counter, _ = self.negotiation_bot.evaluate_offer(81.00)
            if counter:
                self.assertGreaterEqual(counter, self.product.min_price)
                self.assertLessEqual(counter, self.product.price)

if __name__ == '__main__':
    unittest.main()