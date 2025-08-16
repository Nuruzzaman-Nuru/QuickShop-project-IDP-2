# QuickShop QuickShop – Local shop  Web Application
A comprehensive e-commerce solution featuring role-based access control, smart price negotiations, and real-time delivery tracking.

## Features

- **Multi-Role System**
  - Customer: Browse products, negotiate prices, track orders
  - Shop Owner: Manage inventory, handle orders, customize shop settings
  - Delivery Person: Accept deliveries, update order status
  - Admin: Overall platform management

- **AI-Powered Price Negotiations**
  - Smart negotiation bot for automated price discussions
  - Customizable negotiation parameters for shop owners
  - Real-time chat interface for price discussions

- **Real-Time Delivery Tracking**
  - Live tracking of delivery personnel
  - Automated delivery assignments
  - Status updates and notifications

- **Shop Management**
  - Inventory management
  - Order processing
  - Analytics and reporting
  - Shop settings customization

- **User Features**
  - Local shop discovery
  - Shopping cart management
  - Order history
  - Real-time notifications

## Technology Stack

- **Backend**
  - Python
  - Flask
  - SQLAlchemy
  - Flask-Login for authentication
  - Flask-Mail for notifications

- **Frontend**
  - HTML/CSS
  - Bootstrap
  - JavaScript
  - Google Maps API for location services

- **Database**
  - SQLite (Development)
  - Supports PostgreSQL (Production)

## Installation

1. Clone the repository
2. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Set up environment variables in `.env`:
   ```
   SECRET_KEY=your-secret-key
   DATABASE_URL=your-database-url
   GOOGLE_MAPS_API_KEY=your-google-maps-api-key
   MAIL_USERNAME=your-email
   MAIL_PASSWORD=your-email-password
   ```
5. Initialize the database:
   ```
   python migrate.py
   ```

## Running the Application

Development mode:
```
python run.py
```
The application will be available at `http://localhost:4000`

## Project Structure

```
ecommerce/
├── __init__.py          # App initialization
├── config.py            # Configuration settings
├── models/              # Database models
├── routes/              # Route handlers
├── static/              # Static files (CSS, JS, images)
├── templates/           # HTML templates
└── utils/              # Utility functions
    ├── ai/             # AI negotiation systems
    ├── distance.py     # Distance calculations
    └── notifications.py # Notification system
```

## Testing

Run tests using:
```
python -m pytest tests/
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License


This project is licensed under the MIT License.

