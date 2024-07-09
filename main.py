from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import stripe

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///shop.db'
app.config['STRIPE_PUBLIC_KEY'] = 'pk_test_51FeMfIG3Ks4CHLRJvYOjBLY05dmeTT9oZLxqTspUtTlGyNv3EQDbyBPPRMY9vf72LOE4ZEWZMP5I5uoULSG49IPe00tasHNr6j'
app.config['STRIPE_SECRET_KEY'] = 'sk_test_RXHltS2OKzISvxWQ7NmRN57i001oa6x7o4'

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

stripe.api_key = app.config['STRIPE_SECRET_KEY']

# User model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

# Product model
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(200), nullable=True)


def create_sample_products():
    products = [
        Product(name='Product 1', price=19.99, description='This is product 1',
                image_url='images/product1.jpg'),
        Product(name='Product 2', price=29.99, description='This is product 2',
                image_url='images/product2.jpg'),
        Product(name='Product 3', price=39.99, description='This is product 3',
                image_url='images/product3.jpg'),
    ]

    for product in products:
        existing_product = Product.query.filter_by(name=product.name).first()
        if not existing_product:
            db.session.add(product)

    db.session.commit()

def get_cart():
    if 'cart' not in session:
        session['cart'] = {}
    return session['cart']


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/')
def home():
    products = Product.query.all()
    return render_template('home.html', products=products)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.password == request.form['password']:
            login_user(user)
            return redirect(url_for('home'))
        flash('Invalid username or password')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user = User(username=request.form['username'], password=request.form['password'])
        db.session.add(user)
        db.session.commit()
        flash('Registration successful. Please log in.')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/product/<int:product_id>')
def product(product_id):
    product = Product.query.get_or_404(product_id)
    return render_template('product.html', product=product)


@app.route('/add_to_cart/<int:product_id>')
def add_to_cart(product_id):
    cart = get_cart()
    cart[str(product_id)] = cart.get(str(product_id), 0) + 1
    session['cart'] = cart
    flash('Product added to cart!')
    return redirect(url_for('product', product_id=product_id))


@app.route('/cart')
def view_cart():
    cart = get_cart()
    cart_items = []
    total = 0
    for product_id, quantity in cart.items():
        product = Product.query.get(int(product_id))
        if product:
            item_total = product.price * quantity
            cart_items.append({
                'product': product,
                'quantity': quantity,
                'total': item_total
            })
            total += item_total
    return render_template('cart.html', cart_items=cart_items, total=total)


@app.route('/remove_from_cart/<int:product_id>')
def remove_from_cart(product_id):
    cart = get_cart()
    if str(product_id) in cart:
        del cart[str(product_id)]
        session['cart'] = cart
        flash('Product removed from cart!')
    return redirect(url_for('view_cart'))


@app.route('/create-checkout-session', methods=['POST'])
@login_required
def create_checkout_session():
    cart = get_cart()
    line_items = []

    for product_id, quantity in cart.items():
        product = Product.query.get(int(product_id))
        if product:
            line_items.append({
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': product.name,
                    },
                    'unit_amount': int(product.price * 100),  # Stripe uses cents
                },
                'quantity': quantity,
            })

    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=line_items,
            mode='payment',
            success_url=url_for('order_success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=url_for('order_cancel', _external=True),
        )
    except Exception as e:
        return jsonify(error=str(e)), 403

    return jsonify(id=checkout_session.id)


@app.route('/order/success')
@login_required
def order_success():
    session_id = request.args.get('session_id')
    if session_id:
        # Here you would typically save the order details to your database
        session['cart'] = {}  # Clear the cart
        flash('Your order was successful!')
    return redirect(url_for('home'))


@app.route('/order/cancel')
def order_cancel():
    flash('Your order was cancelled.')
    return redirect(url_for('view_cart'))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_sample_products()
    app.run(debug=True)
