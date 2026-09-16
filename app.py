import os

from dotenv import load_dotenv
from email_validator import EmailNotValidError, validate_email
from flask import Flask, flash, redirect, render_template, request, session, url_for
try:
    import razorpay
except ImportError:
    razorpay = None

from database import (
    add_food,
    dashboard_stats,
    delete_food,
    get_admin_order_detail,
    get_admin_orders,
    get_all_canteens,
    get_all_orders,
    get_all_payments,
    get_food_analytics,
    get_food_by_id,
    get_food_categories,
    get_food_summary,
    get_foods_by_canteen,
    get_order_detail,
    get_orders_for_user,
    get_latest_payment,
    get_latest_payment_by_gateway_order,
    get_user_by_email,
    get_user_by_id,
    get_user_by_phone,
    get_user_count,
    init_db,
    save_order,
    record_gateway_payment,
    set_gateway_order_id,
    submit_payment_reference,
    update_food,
    update_order_status,
    update_payment_for_admin,
    validate_phone_number,
    verify_password,
)
from database import create_user, hash_password

load_dotenv()

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["PAYMENT_MODE"] = os.getenv("PAYMENT_MODE", "test")
app.config["RAZORPAY_KEY_ID"] = os.getenv("RAZORPAY_KEY_ID", "")
app.config["RAZORPAY_KEY_SECRET"] = os.getenv("RAZORPAY_KEY_SECRET", "")
app.config["RAZORPAY_WEBHOOK_SECRET"] = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
app.config["UPI_ID"] = "9642703351-2@ybl"
app.config["QR_FILENAME"] = "images/phonepe_qr.png"

init_db()


@app.context_processor
def inject_defaults():
    return {
        "canteens": get_all_canteens(),
        "user": get_user_by_id(session.get("user_id")) if session.get("user_id") else None,
        "upi_id": app.config["UPI_ID"],
        "qr_filename": app.config["QR_FILENAME"],
        "qr_available": os.path.exists(os.path.join(app.static_folder, app.config["QR_FILENAME"])),
    }


def login_required(role=None):
    def decorator(func):
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                flash("Please log in first.")
                return redirect(url_for("login"))
            user = get_user_by_id(session["user_id"])
            if not user:
                session.clear()
                flash("Session expired.")
                return redirect(url_for("login"))
            if role and user["role"] != role:
                if user["role"] == "admin":
                    return redirect(url_for("admin_dashboard"))
                return redirect(url_for("student_dashboard"))
            return func(*args, **kwargs)

        wrapper.__name__ = func.__name__
        return wrapper

    return decorator


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        if not all([name, email, password]):
            flash('Name, email, and password are required.')
            return render_template('register.html')
        try:
            email = validate_email(email, check_deliverability=False).normalized
        except EmailNotValidError:
            flash('Enter a valid email address.')
            return render_template('register.html')
        if password != confirm:
            flash('Passwords do not match.')
            return render_template('register.html')
        if get_user_by_email(email):
            flash('This email is already registered.')
            return render_template('register.html')

        user_id = create_user(name, email, password, None, role='student')
        if not user_id:
            flash('This email is already registered.')
            return render_template('register.html')
        flash('Registration successful. Please log in.')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('user_id'):
        user = get_user_by_id(session['user_id'])
        if user and user['role'] == 'admin':
            return redirect(url_for('admin_dashboard'))
        if user:
            return redirect(url_for('student_dashboard'))
        session.clear()
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        user = get_user_by_email(email)
        if user and verify_password(password, user['password']):
            session['user_id'] = user['id']
            session['role'] = user['role']
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('student_dashboard'))
        flash('Invalid email or password.')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        user = get_user_by_email(email)
        if user and user['role'] == 'admin' and verify_password(password, user['password']):
            session['user_id'] = user['id']
            session['role'] = 'admin'
            return redirect(url_for('admin_dashboard'))
        flash('Admin credentials are invalid.')
    return render_template('admin_login.html')


@app.route('/admin')
def admin_index():
    if 'user_id' in session and get_user_by_id(session['user_id']) and get_user_by_id(session['user_id'])['role'] == 'admin':
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('admin_login'))


@app.route('/admin/dashboard')
@login_required(role='admin')
def admin_dashboard():
    stats = dashboard_stats()
    orders = get_all_orders()[:5]
    dashboard = {
        'orders': stats.get('orders', 0),
        'revenue': stats.get('revenue', 0),
        'users': get_user_count(),
        'best_item': 'N/A',
    }
    return render_template('admin_dashboard.html', dashboard=dashboard, stats=stats, recent_orders=orders)


@app.route('/admin/food', methods=['GET', 'POST'])
@login_required(role='admin')
def admin_food():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        category = request.form.get('category', '').strip()
        description = request.form.get('description', '').strip()
        price = request.form.get('price', '0')
        stock = request.form.get('stock', '0')
        image = request.form.get('image', '')
        if name and category and price:
            add_food(1, name, category, description, price, stock, image, True)
            flash('Food item added successfully.')
    foods = get_food_summary()
    categories = get_food_categories()
    return render_template('admin_food.html', foods=foods, categories=categories)


@app.route('/admin/food/edit/<int:food_id>', methods=['GET', 'POST'])
@login_required(role='admin')
def admin_edit_food(food_id):
    food = get_food_by_id(food_id)
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        category = request.form.get('category', '').strip()
        description = request.form.get('description', '').strip()
        price = request.form.get('price', '0')
        stock = request.form.get('stock', '0')
        available = request.form.get('available') == 'on'
        if name and category:
            update_food(food_id, name, category, description, price, stock, available)
            flash('Food updated.')
            return redirect(url_for('admin_food'))
    return render_template('admin_edit_food.html', food=food)


@app.route('/admin/food/delete/<int:food_id>')
@login_required(role='admin')
def admin_delete_food(food_id):
    delete_food(food_id)
    flash('Food item deleted.')
    return redirect(url_for('admin_food'))


@app.route('/admin/orders')
@login_required(role='admin')
def admin_orders():
    search = request.args.get('search', '').strip()
    orders = get_admin_orders(search=search)
    return render_template('admin_orders.html', orders=orders, search=search)


@app.route('/admin/order/<int:order_id>')
@login_required(role='admin')
def admin_order_detail(order_id):
    order, items = get_admin_order_detail(order_id)
    if not order:
        flash('Order not found.')
        return redirect(url_for('admin_orders'))
    return render_template('admin_order_detail.html', order=order, items=items)


@app.route('/admin/order/<int:order_id>/status', methods=['POST'])
@login_required(role='admin')
def admin_update_status(order_id):
    status = (request.form.get('status', 'PLACED') or 'PLACED').upper()
    allowed_statuses = {'PENDING', 'PLACED', 'CONFIRMED', 'PREPARING', 'READY', 'COMPLETED', 'CANCELLED'}
    if status not in allowed_statuses:
        flash('Invalid order status.')
        return redirect(url_for('admin_order_detail', order_id=order_id))
    update_order_status(order_id, status)
    flash('Order status updated.')
    return redirect(url_for('admin_order_detail', order_id=order_id))


@app.route('/admin/payment/<int:order_id>/status', methods=['POST'])
@login_required(role='admin')
def admin_update_payment(order_id):
    status = (request.form.get('payment_status', '') or '').strip().upper()
    allowed_statuses = {'PAID', 'REJECTED', 'FAILED', 'REFUNDED', 'PENDING VERIFICATION', 'CASH / PENDING'}
    if status not in allowed_statuses:
        flash('Invalid payment status.')
        return redirect(url_for('admin_order_detail', order_id=order_id))
    update_payment_for_admin(order_id, status)
    flash('Payment status updated.')
    return redirect(url_for('admin_order_detail', order_id=order_id))


@app.route('/admin/payments')
@login_required(role='admin')
def admin_payments():
    filter_value = request.args.get('status', 'all').strip().lower()
    payments = get_all_payments(filter_value=filter_value)
    return render_template('admin_payments.html', payments=payments, filter_value=filter_value)


@app.route('/admin/inventory')
@login_required(role='admin')
def admin_inventory():
    foods = get_food_summary()
    return render_template('inventory.html', foods=foods)


@app.route('/admin/analytics')
@login_required(role='admin')
def admin_analytics():
    analytics = get_food_analytics()
    stats = dashboard_stats()
    return render_template('analytics.html', analytics=analytics, stats=stats)


@app.route('/student/dashboard')
@login_required(role='student')
def student_dashboard():
    orders = get_orders_for_user(session['user_id'])
    return render_template('student_dashboard.html', orders=orders)


@app.route('/student/menu')
def student_menu():
    canteen_id = request.args.get('canteen_id', 1, type=int)
    category = request.args.get('category', 'All')
    search = request.args.get('search', '')
    canteens = get_all_canteens()
    categories = ['All'] + get_food_categories()
    foods = get_foods_by_canteen(canteen_id, category=category, search=search)
    return render_template('menu.html', foods=foods, categories=categories, canteens=canteens, selected_canteen_id=canteen_id, search=search, category=category)


@app.route('/student/cart')
def student_cart():
    cart = session.get('cart', {})
    items = []
    total = 0.0
    for food_id, qty in cart.items():
        food = get_food_by_id(int(food_id))
        if food:
            subtotal = float(food['price']) * int(qty)
            total += subtotal
            items.append({**food, 'quantity': int(qty), 'subtotal': subtotal})
    return render_template('cart.html', items=items, total=total)


@app.route('/student/cart/add', methods=['POST'])
def add_to_cart():
    food_id = request.form.get('food_id')
    qty = int(request.form.get('quantity', 1))
    if not food_id:
        flash('Food item missing.')
        return redirect(url_for('student_menu'))
    cart = session.setdefault('cart', {})
    cart[str(food_id)] = cart.get(str(food_id), 0) + qty
    session['cart'] = cart
    flash('Item added to cart.')
    return redirect(url_for('student_menu'))


@app.route('/student/cart/update', methods=['POST'])
def update_cart():
    food_id = request.form.get('food_id')
    qty = int(request.form.get('quantity', 1))
    cart = session.get('cart', {})
    if qty <= 0:
        cart.pop(str(food_id), None)
    else:
        cart[str(food_id)] = qty
    session['cart'] = cart
    return redirect(url_for('student_cart'))


@app.route('/student/cart/remove/<food_id>')
def remove_from_cart(food_id):
    cart = session.get('cart', {})
    cart.pop(str(food_id), None)
    session['cart'] = cart
    return redirect(url_for('student_cart'))


@app.route('/student/checkout', methods=['GET', 'POST'])
@login_required(role='student')
def student_checkout():
    if request.method == 'POST':
        pickup_time = request.form.get('pickup_time', '')
        payment_method = request.form.get('payment_method', '').strip().upper()
        cart = session.get('cart', {})
        if not cart:
            flash('Your cart is empty.')
            return redirect(url_for('student_cart'))
        if not pickup_time:
            flash('Please select a pickup time.')
            return redirect(url_for('student_checkout'))
        if payment_method not in {'CASH', 'UPI'}:
            flash('Please select Cash or UPI / Online Payment.')
            return redirect(url_for('student_checkout'))
        payment_status = 'CASH / PENDING' if payment_method == 'CASH' else 'PENDING VERIFICATION'
        result = save_order(session['user_id'], 1, cart, pickup_time, payment_method, payment_status=payment_status, payment_id=None)
        if result is None:
            flash('One or more food items are unavailable or out of stock.')
            return redirect(url_for('student_cart'))
        order_id, generated_order_id, token = result[0], result[1], result[2]
        session['cart'] = {}
        if payment_method == 'UPI':
            flash('Order created. Complete UPI payment and submit the reference ID for admin verification.')
            return redirect(url_for('student_payment', order_id=order_id))
        flash('Cash order created. Payment is pending at pickup.')
        return redirect(url_for('student_order_detail', order_id=order_id))

    cart = session.get('cart', {})
    items = []
    total = 0.0
    for food_id, qty in cart.items():
        food = get_food_by_id(int(food_id))
        if food:
            subtotal = float(food['price']) * int(qty)
            total += subtotal
            items.append({**food, 'quantity': qty, 'subtotal': subtotal})
    return render_template('checkout.html', items=items, total=total)


@app.route('/student/place-order', methods=['POST'])
def student_place_order():
    return redirect(url_for('student_checkout'))


@app.route('/student/orders')
@login_required(role='student')
def student_orders():
    orders = get_orders_for_user(session['user_id'])
    return render_template('orders.html', orders=orders)


@app.route('/student/order/<int:order_id>')
@login_required(role='student')
def student_order_detail(order_id):
    order, items = get_order_detail(order_id)
    if not order or order['user_id'] != session['user_id']:
        flash('Order not found.')
        return redirect(url_for('student_orders'))
    pickup_time = order['pickup_time']
    return render_template('order_detail.html', order=order, items=items, pickup_time=pickup_time)


@app.route('/student/payment/<int:order_id>')
@login_required(role='student')
def student_payment(order_id):
    order, items = get_order_detail(order_id)
    if not order or order['user_id'] != session['user_id']:
        flash('Order not found.')
        return redirect(url_for('student_orders'))
    if order['payment_method'] != 'UPI':
        flash('This order uses cash payment.')
        return redirect(url_for('student_order_detail', order_id=order_id))

    total = float(order['total_amount'])
    payment = get_latest_payment(order_id)
    gateway_order = None
    gateway_ready = bool(razorpay and app.config["RAZORPAY_KEY_ID"] and app.config["RAZORPAY_KEY_SECRET"])
    if gateway_ready and not payment.get('gateway_order_id'):
        client = razorpay.Client(auth=(app.config["RAZORPAY_KEY_ID"], app.config["RAZORPAY_KEY_SECRET"]))
        gateway_order = client.order.create({
            'amount': int(round(total * 100)),
            'currency': 'INR',
            'receipt': order['order_id'],
            'notes': {'local_order_id': str(order_id)},
        })
        set_gateway_order_id(order_id, gateway_order['id'])
    elif payment and payment.get('gateway_order_id'):
        gateway_order = {'id': payment['gateway_order_id']}
    return render_template(
        'payment.html',
        order=order,
        items=items,
        total=total,
        gateway_ready=gateway_ready,
        gateway_order=gateway_order,
        razorpay_key_id=app.config["RAZORPAY_KEY_ID"],
    )


@app.route('/student/payment/verify', methods=['POST'])
@login_required(role='student')
def verify_student_payment():
    order_id = request.form.get('order_id')
    razorpay_order_id = request.form.get('razorpay_order_id', '').strip()
    razorpay_payment_id = request.form.get('razorpay_payment_id', '').strip()
    razorpay_signature = request.form.get('razorpay_signature', '').strip()
    transaction_id = request.form.get('transaction_id', '').strip()
    if not order_id:
        flash('Invalid payment request.')
        return redirect(url_for('student_orders'))

    order, _ = get_order_detail(int(order_id))
    if not order or order['user_id'] != session['user_id']:
        flash('Order not found.')
        return redirect(url_for('student_orders'))

    if order['payment_method'] != 'UPI':
        flash('This order does not use UPI payment.')
        return redirect(url_for('student_order_detail', order_id=int(order_id)))
    if razorpay_order_id and razorpay_payment_id and razorpay_signature:
        payment = get_latest_payment(int(order_id))
        if not payment or payment.get('gateway_order_id') != razorpay_order_id:
            flash('Payment order mismatch.')
            return redirect(url_for('student_payment', order_id=int(order_id)))
        client = razorpay.Client(auth=(app.config["RAZORPAY_KEY_ID"], app.config["RAZORPAY_KEY_SECRET"]))
        try:
            client.utility.verify_payment_signature({
                'razorpay_order_id': razorpay_order_id,
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature': razorpay_signature,
            })
        except razorpay.errors.SignatureVerificationError:
            flash('Payment signature verification failed.')
            return redirect(url_for('student_payment', order_id=int(order_id)))
        record_gateway_payment(int(order_id), 'PAID', razorpay_payment_id, razorpay_payment_id)
        flash('Payment verified and order confirmed.')
        return redirect(url_for('student_order_detail', order_id=int(order_id)))
    if not transaction_id:
        flash('Enter a UPI transaction/reference ID or complete gateway payment.')
        return redirect(url_for('student_payment', order_id=int(order_id)))
    submit_payment_reference(int(order_id), transaction_id)
    flash('Reference submitted. Payment remains pending until gateway/admin verification.')
    return redirect(url_for('student_order_detail', order_id=int(order_id)))


@app.route('/payments/razorpay/webhook', methods=['POST'])
def razorpay_webhook():
    webhook_secret = app.config["RAZORPAY_WEBHOOK_SECRET"]
    signature = request.headers.get('X-Razorpay-Signature', '')
    if not razorpay or not webhook_secret or not signature:
        return {'error': 'Webhook verification is not configured'}, 503
    client = razorpay.Client(auth=(app.config["RAZORPAY_KEY_ID"], app.config["RAZORPAY_KEY_SECRET"]))
    try:
        client.utility.verify_webhook_signature(request.get_data(as_text=True), signature, webhook_secret)
    except razorpay.errors.SignatureVerificationError:
        return {'error': 'Invalid webhook signature'}, 400
    payload = request.get_json(silent=True) or {}
    event = payload.get('event', '')
    entity = payload.get('payload', {}).get('payment', {}).get('entity', {})
    gateway_order_id = entity.get('order_id')
    gateway_payment_id = entity.get('id')
    if gateway_order_id and event in {'payment.captured', 'order.paid'}:
        payment = get_latest_payment_by_gateway_order(gateway_order_id)
        if payment:
            record_gateway_payment(payment['order_id'], 'PAID', gateway_payment_id, gateway_payment_id)
    elif gateway_order_id and event == 'payment.failed':
        payment = get_latest_payment_by_gateway_order(gateway_order_id)
        if payment:
            record_gateway_payment(payment['order_id'], 'FAILED', gateway_payment_id, gateway_payment_id)
    return {'received': True}, 200


@app.errorhandler(404)
def page_not_found(error):
    return render_template('404.html'), 404


@app.errorhandler(403)
def forbidden(error):
    return render_template('403.html'), 403


@app.errorhandler(500)
def server_error(error):
    return render_template('500.html'), 500


if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)
