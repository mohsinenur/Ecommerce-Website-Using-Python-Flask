from flask import Flask, render_template, flash, redirect, url_for, session, request, logging
from flask_mysqldb import MySQL
from wtforms import Form, StringField, TextAreaField, PasswordField, validators, SelectField
from passlib.hash import sha256_crypt
from functools import wraps
from flask_uploads import UploadSet, configure_uploads, IMAGES
import timeit
import datetime
from flask_mail import Mail, Message
import os
from wtforms.fields.html5 import EmailField

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['UPLOADED_PHOTOS_DEST'] = 'static/image/product'
photos = UploadSet('photos', IMAGES)
configure_uploads(app, photos)

# Config MySQL
mysql = MySQL()
app.config['MYSQL_HOST'] = '127.0.0.1'
app.config['MYSQL_USER'] = 'nur'
app.config['MYSQL_PASSWORD'] = 'secret'
app.config['MYSQL_DB'] = 'menshut'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

# Initialize the app for use with this MySQL class
mysql.init_app(app)


def is_logged_in(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            return f(*args, *kwargs)
        else:
            return redirect(url_for('login'))

    return wrap


def not_logged_in(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            return redirect(url_for('index'))
        else:
            return f(*args, *kwargs)

    return wrap


def is_admin_logged_in(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'admin_logged_in' in session:
            return f(*args, *kwargs)
        else:
            return redirect(url_for('admin_login'))

    return wrap


def not_admin_logged_in(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'admin_logged_in' in session:
            return redirect(url_for('admin'))
        else:
            return f(*args, *kwargs)

    return wrap


def wrappers(func, *args, **kwargs):
    def wrapped():
        return func(*args, **kwargs)

    return wrapped


def content_based_filtering(product_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM products WHERE id=%s", (product_id,))  # getting id row
    data = cur.fetchone()  # get row info
    data_cat = data['category']  # get id category ex shirt
    print('Showing result for Product Id: ' + product_id)
    category_matched = cur.execute("SELECT * FROM products WHERE category=%s", (data_cat,))  # get all shirt category
    print('Total product matched: ' + str(category_matched))
    cat_product = cur.fetchall()  # get all row
    cur.execute("SELECT * FROM product_level WHERE product_id=%s", (product_id,))  # id level info
    id_level = cur.fetchone()
    recommend_id = []
    cate_level = ['v_shape', 'polo', 'clean_text', 'design', 'leather', 'color', 'formal', 'converse', 'loafer', 'hook',
                  'chain']
    for product_f in cat_product:
        cur.execute("SELECT * FROM product_level WHERE product_id=%s", (product_f['id'],))
        f_level = cur.fetchone()
        match_score = 0
        if f_level['product_id'] != int(product_id):
            for cat_level in cate_level:
                if f_level[cat_level] == id_level[cat_level]:
                    match_score += 1
            if match_score == 11:
                recommend_id.append(f_level['product_id'])
    print('Total recommendation found: ' + str(recommend_id))
    if recommend_id:
        cur = mysql.connection.cursor()
        placeholders = ','.join((str(n) for n in recommend_id))
        query = 'SELECT * FROM products WHERE id IN (%s)' % placeholders
        cur.execute(query)
        recommend_list = cur.fetchall()
        return recommend_list, recommend_id, category_matched, product_id
    else:
        return ''


@app.route('/')
def index():
    form = OrderForm(request.form)
    # Create cursor
    cur = mysql.connection.cursor()
    # Get message
    values = 'tshirt'
    cur.execute("SELECT * FROM products WHERE category=%s ORDER BY RAND() LIMIT 4", (values,))
    tshirt = cur.fetchall()
    values = 'wallet'
    cur.execute("SELECT * FROM products WHERE category=%s ORDER BY RAND() LIMIT 4", (values,))
    wallet = cur.fetchall()
    values = 'belt'
    cur.execute("SELECT * FROM products WHERE category=%s ORDER BY RAND() LIMIT 4", (values,))
    belt = cur.fetchall()
    values = 'shoes'
    cur.execute("SELECT * FROM products WHERE category=%s ORDER BY RAND() LIMIT 4", (values,))
    shoes = cur.fetchall()
    # Close Connection
    cur.close()
    return render_template('home.html', tshirt=tshirt, wallet=wallet, belt=belt, shoes=shoes, form=form)


class LoginForm(Form):  # Create Login Form
    username = StringField('', [validators.length(min=1)],
                           render_kw={'autofocus': True, 'placeholder': 'Username'})
    password = PasswordField('', [validators.length(min=3)],
                             render_kw={'placeholder': 'Password'})


# User Login
@app.route('/login', methods=['GET', 'POST'])
@not_logged_in
def login():
    form = LoginForm(request.form)
    if request.method == 'POST' and form.validate():
        # GEt user form
        username = form.username.data
        # password_candidate = request.form['password']
        password_candidate = form.password.data

        # Create cursor
        cur = mysql.connection.cursor()

        # Get user by username
        result = cur.execute("SELECT * FROM users WHERE username=%s", [username])

        if result > 0:
            # Get stored value
            data = cur.fetchone()
            password = data['password']
            uid = data['id']
            name = data['name']

            # Compare password
            if sha256_crypt.verify(password_candidate, password):
                # passed
                session['logged_in'] = True
                session['uid'] = uid
                session['s_name'] = name
                x = '1'
                cur.execute("UPDATE users SET online=%s WHERE id=%s", (x, uid))

                return redirect(url_for('index'))

            else:
                flash('Incorrect password', 'danger')
                return render_template('login.html', form=form)

        else:
            flash('Username not found', 'danger')
            # Close connection
            cur.close()
            return render_template('login.html', form=form)
    return render_template('login.html', form=form)


@app.route('/out')
def logout():
    if 'uid' in session:
        # Create cursor
        cur = mysql.connection.cursor()
        uid = session['uid']
        x = '0'
        cur.execute("UPDATE users SET online=%s WHERE id=%s", (x, uid))
        session.clear()
        flash('You are logged out', 'success')
        return redirect(url_for('index'))
    return redirect(url_for('login'))


class RegisterForm(Form):
    name = StringField('', [validators.length(min=3, max=50)],
                       render_kw={'autofocus': True, 'placeholder': 'Full Name'})
    username = StringField('', [validators.length(min=3, max=25)], render_kw={'placeholder': 'Username'})
    email = EmailField('', [validators.DataRequired(), validators.Email(), validators.length(min=4, max=25)],
                       render_kw={'placeholder': 'Email'})
    password = PasswordField('', [validators.length(min=3)],
                             render_kw={'placeholder': 'Password'})
    mobile = StringField('', [validators.length(min=11, max=15)], render_kw={'placeholder': 'Mobile'})


@app.route('/register', methods=['GET', 'POST'])
@not_logged_in
def register():
    form = RegisterForm(request.form)
    if request.method == 'POST' and form.validate():
        name = form.name.data
        email = form.email.data
        username = form.username.data
        password = sha256_crypt.encrypt(str(form.password.data))
        mobile = form.mobile.data

        # Create Cursor
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO users(name, email, username, password, mobile) VALUES(%s, %s, %s, %s, %s)",
                    (name, email, username, password, mobile))

        # Commit cursor
        mysql.connection.commit()

        # Close Connection
        cur.close()

        flash('You are now registered and can login', 'success')

        return redirect(url_for('index'))
    return render_template('register.html', form=form)


class MessageForm(Form):  # Create Message Form
    body = StringField('', [validators.length(min=1)], render_kw={'autofocus': True})


@app.route('/chatting/<string:id>', methods=['GET', 'POST'])
def chatting(id):
    if 'uid' in session:
        form = MessageForm(request.form)
        # Create cursor
        cur = mysql.connection.cursor()

        # lid name
        get_result = cur.execute("SELECT * FROM users WHERE id=%s", [id])
        l_data = cur.fetchone()
        if get_result > 0:
            session['name'] = l_data['name']
            uid = session['uid']
            session['lid'] = id

            if request.method == 'POST' and form.validate():
                txt_body = form.body.data
                # Create cursor
                cur = mysql.connection.cursor()
                cur.execute("INSERT INTO messages(body, msg_by, msg_to) VALUES(%s, %s, %s)",
                            (txt_body, id, uid))
                # Commit cursor
                mysql.connection.commit()

            # Get users
            cur.execute("SELECT * FROM users")
            users = cur.fetchall()

            # Close Connection
            cur.close()
            return render_template('chat_room.html', users=users, form=form)
        else:
            flash('No permission!', 'danger')
            return redirect(url_for('index'))
    else:
        return redirect(url_for('login'))


@app.route('/chats', methods=['GET', 'POST'])
def chats():
    if 'lid' in session:
        id = session['lid']
        uid = session['uid']
        # Create cursor
        cur = mysql.connection.cursor()
        # Get message
        cur.execute("SELECT * FROM messages WHERE (msg_by=%s AND msg_to=%s) OR (msg_by=%s AND msg_to=%s) "
                    "ORDER BY id ASC", (id, uid, uid, id))
        chats = cur.fetchall()
        # Close Connection
        cur.close()
        return render_template('chats.html', chats=chats, )
    return redirect(url_for('login'))


class OrderForm(Form):  # Create Order Form
    name = StringField('', [validators.length(min=1), validators.DataRequired()],
                       render_kw={'autofocus': True, 'placeholder': 'Full Name'})
    mobile_num = StringField('', [validators.length(min=1), validators.DataRequired()],
                             render_kw={'autofocus': True, 'placeholder': 'Mobile'})
    quantity = SelectField('', [validators.DataRequired()],
                           choices=[('1', '1'), ('2', '2'), ('3', '3'), ('4', '4'), ('5', '5')])
    order_place = StringField('', [validators.length(min=1), validators.DataRequired()],
                              render_kw={'placeholder': 'Order Place'})


@app.route('/tshirt', methods=['GET', 'POST'])
def tshirt():
    form = OrderForm(request.form)
    # Create cursor
    cur = mysql.connection.cursor()
    # Get message
    values = 'tshirt'
    cur.execute("SELECT * FROM products WHERE category=%s ORDER BY id ASC", (values,))
    products = cur.fetchall()
    # Close Connection
    cur.close()
    if request.method == 'POST' and form.validate():
        name = form.name.data
        mobile = form.mobile_num.data
        order_place = form.order_place.data
        quantity = form.quantity.data
        pid = request.args['order']
        now = datetime.datetime.now()
        week = datetime.timedelta(days=7)
        delivery_date = now + week
        now_time = delivery_date.strftime("%y-%m-%d %H:%M:%S")
        # Create Cursor
        curs = mysql.connection.cursor()
        if 'uid' in session:
            uid = session['uid']
            curs.execute("INSERT INTO orders(uid, pid, ofname, mobile, oplace, quantity, ddate) "
                         "VALUES(%s, %s, %s, %s, %s, %s, %s)",
                         (uid, pid, name, mobile, order_place, quantity, now_time))
        else:
            curs.execute("INSERT INTO orders(pid, ofname, mobile, oplace, quantity, ddate) "
                         "VALUES(%s, %s, %s, %s, %s, %s)",
                         (pid, name, mobile, order_place, quantity, now_time))
        # Commit cursor
        mysql.connection.commit()

        # Close Connection
        cur.close()

        flash('Order successful', 'success')
        return render_template('tshirt.html', tshirt=products, form=form)
    if 'view' in request.args:
        product_id = request.args['view']
        curso = mysql.connection.cursor()
        curso.execute("SELECT * FROM products WHERE id=%s", (product_id,))
        product = curso.fetchall()
        x = content_based_filtering(product_id)
        wrappered = wrappers(content_based_filtering, product_id)
        execution_time = timeit.timeit(wrappered, number=0)
        # print('Execution time: ' + str(execution_time) + ' usec')
        if 'uid' in session:
            uid = session['uid']
            # Create cursor
            cur = mysql.connection.cursor()
            cur.execute("SELECT * FROM product_view WHERE user_id=%s AND product_id=%s", (uid, product_id))
            result = cur.fetchall()
            if result:
                now = datetime.datetime.now()
                now_time = now.strftime("%y-%m-%d %H:%M:%S")
                cur.execute("UPDATE product_view SET date=%s WHERE user_id=%s AND product_id=%s",
                            (now_time, uid, product_id))
            else:
                cur.execute("INSERT INTO product_view(user_id, product_id) VALUES(%s, %s)", (uid, product_id))
                mysql.connection.commit()
        return render_template('view_product.html', x=x, tshirts=product)
    elif 'order' in request.args:
        product_id = request.args['order']
        curso = mysql.connection.cursor()
        curso.execute("SELECT * FROM products WHERE id=%s", (product_id,))
        product = curso.fetchall()
        x = content_based_filtering(product_id)
        return render_template('order_product.html', x=x, tshirts=product, form=form)
    return render_template('tshirt.html', tshirt=products, form=form)


@app.route('/wallet', methods=['GET', 'POST'])
def wallet():
    form = OrderForm(request.form)
    # Create cursor
    cur = mysql.connection.cursor()
    # Get message
    values = 'wallet'
    cur.execute("SELECT * FROM products WHERE category=%s ORDER BY id ASC", (values,))
    products = cur.fetchall()
    # Close Connection
    cur.close()

    if request.method == 'POST' and form.validate():
        name = form.name.data
        mobile = form.mobile_num.data
        order_place = form.order_place.data
        quantity = form.quantity.data
        pid = request.args['order']

        now = datetime.datetime.now()
        week = datetime.timedelta(days=7)
        delivery_date = now + week
        now_time = delivery_date.strftime("%y-%m-%d %H:%M:%S")
        # Create Cursor
        curs = mysql.connection.cursor()
        if 'uid' in session:
            uid = session['uid']
            curs.execute("INSERT INTO orders(uid, pid, ofname, mobile, oplace, quantity, ddate) "
                         "VALUES(%s, %s, %s, %s, %s, %s, %s)",
                         (uid, pid, name, mobile, order_place, quantity, now_time))
        else:
            curs.execute("INSERT INTO orders(pid, ofname, mobile, oplace, quantity, ddate) "
                         "VALUES(%s, %s, %s, %s, %s, %s)",
                         (pid, name, mobile, order_place, quantity, now_time))
        # Commit cursor
        mysql.connection.commit()
        # Close Connection
        cur.close()

        flash('Order successful', 'success')
        return render_template('wallet.html', wallet=products, form=form)
    if 'view' in request.args:
        q = request.args['view']
        product_id = q
        x = content_based_filtering(product_id)
        curso = mysql.connection.cursor()
        curso.execute("SELECT * FROM products WHERE id=%s", (q,))
        products = curso.fetchall()
        return render_template('view_product.html', x=x, tshirts=products)
    elif 'order' in request.args:
        product_id = request.args['order']
        curso = mysql.connection.cursor()
        curso.execute("SELECT * FROM products WHERE id=%s", (product_id,))
        product = curso.fetchall()
        x = content_based_filtering(product_id)
        return render_template('order_product.html', x=x, tshirts=product, form=form)
    return render_template('wallet.html', wallet=products, form=form)


@app.route('/belt', methods=['GET', 'POST'])
def belt():
    form = OrderForm(request.form)
    # Create cursor
    cur = mysql.connection.cursor()
    # Get message
    values = 'belt'
    cur.execute("SELECT * FROM products WHERE category=%s ORDER BY id ASC", (values,))
    products = cur.fetchall()
    # Close Connection
    cur.close()

    if request.method == 'POST' and form.validate():
        name = form.name.data
        mobile = form.mobile_num.data
        order_place = form.order_place.data
        quantity = form.quantity.data
        pid = request.args['order']
        now = datetime.datetime.now()
        week = datetime.timedelta(days=7)
        delivery_date = now + week
        now_time = delivery_date.strftime("%y-%m-%d %H:%M:%S")
        # Create Cursor
        curs = mysql.connection.cursor()
        if 'uid' in session:
            uid = session['uid']
            curs.execute("INSERT INTO orders(uid, pid, ofname, mobile, oplace, quantity, ddate) "
                         "VALUES(%s, %s, %s, %s, %s, %s, %s)",
                         (uid, pid, name, mobile, order_place, quantity, now_time))
        else:
            curs.execute("INSERT INTO orders(pid, ofname, mobile, oplace, quantity, ddate) "
                         "VALUES(%s, %s, %s, %s, %s, %s)",
                         (pid, name, mobile, order_place, quantity, now_time))

        # Commit cursor
        mysql.connection.commit()

        # Close Connection
        cur.close()

        flash('Order successful', 'success')
        return render_template('belt.html', belt=products, form=form)
    if 'view' in request.args:
        q = request.args['view']
        product_id = q
        x = content_based_filtering(product_id)
        curso = mysql.connection.cursor()
        curso.execute("SELECT * FROM products WHERE id=%s", (q,))
        products = curso.fetchall()
        return render_template('view_product.html', x=x, tshirts=products)
    elif 'order' in request.args:
        product_id = request.args['order']
        curso = mysql.connection.cursor()
        curso.execute("SELECT * FROM products WHERE id=%s", (product_id,))
        product = curso.fetchall()
        x = content_based_filtering(product_id)
        return render_template('order_product.html', x=x, tshirts=product, form=form)
    return render_template('belt.html', belt=products, form=form)


@app.route('/shoes', methods=['GET', 'POST'])
def shoes():
    form = OrderForm(request.form)
    # Create cursor
    cur = mysql.connection.cursor()
    # Get message
    values = 'shoes'
    cur.execute("SELECT * FROM products WHERE category=%s ORDER BY id ASC", (values,))
    products = cur.fetchall()
    # Close Connection
    cur.close()

    if request.method == 'POST' and form.validate():
        name = form.name.data
        mobile = form.mobile_num.data
        order_place = form.order_place.data
        quantity = form.quantity.data
        pid = request.args['order']
        now = datetime.datetime.now()
        week = datetime.timedelta(days=7)
        delivery_date = now + week
        now_time = delivery_date.strftime("%y-%m-%d %H:%M:%S")
        # Create Cursor
        curs = mysql.connection.cursor()
        if 'uid' in session:
            uid = session['uid']
            curs.execute("INSERT INTO orders(uid, pid, ofname, mobile, oplace, quantity, ddate) "
                         "VALUES(%s, %s, %s, %s, %s, %s, %s)",
                         (uid, pid, name, mobile, order_place, quantity, now_time))
        else:
            curs.execute("INSERT INTO orders(pid, ofname, mobile, oplace, quantity, ddate) "
                         "VALUES(%s, %s, %s, %s, %s, %s)",
                         (pid, name, mobile, order_place, quantity, now_time))
        # Commit cursor
        mysql.connection.commit()
        # Close Connection
        cur.close()

        flash('Order successful', 'success')
        return render_template('shoes.html', shoes=products, form=form)
    if 'view' in request.args:
        q = request.args['view']
        product_id = q
        x = content_based_filtering(product_id)
        curso = mysql.connection.cursor()
        curso.execute("SELECT * FROM products WHERE id=%s", (q,))
        products = curso.fetchall()
        return render_template('view_product.html', x=x, tshirts=products)
    elif 'order' in request.args:
        product_id = request.args['order']
        curso = mysql.connection.cursor()
        curso.execute("SELECT * FROM products WHERE id=%s", (product_id,))
        product = curso.fetchall()
        x = content_based_filtering(product_id)
        return render_template('order_product.html', x=x, tshirts=product, form=form)
    return render_template('shoes.html', shoes=products, form=form)


@app.route('/admin_login', methods=['GET', 'POST'])
@not_admin_logged_in
def admin_login():
    if request.method == 'POST':
        # GEt user form
        username = request.form['email']
        password_candidate = request.form['password']

        # Create cursor
        cur = mysql.connection.cursor()

        # Get user by username
        result = cur.execute("SELECT * FROM admin WHERE email=%s", [username])

        if result > 0:
            # Get stored value
            data = cur.fetchone()
            password = data['password']
            uid = data['id']
            name = data['firstName']

            # Compare password
            if sha256_crypt.verify(password_candidate, password):
                # passed
                session['admin_logged_in'] = True
                session['admin_uid'] = uid
                session['admin_name'] = name

                return redirect(url_for('admin'))

            else:
                flash('Incorrect password', 'danger')
                return render_template('pages/login.html')

        else:
            flash('Username not found', 'danger')
            # Close connection
            cur.close()
            return render_template('pages/login.html')
    return render_template('pages/login.html')


@app.route('/admin_out')
def admin_logout():
    if 'admin_logged_in' in session:
        session.clear()
        return redirect(url_for('admin_login'))
    return redirect(url_for('admin'))


@app.route('/admin')
@is_admin_logged_in
def admin():
    curso = mysql.connection.cursor()
    num_rows = curso.execute("SELECT * FROM products")
    result = curso.fetchall()
    order_rows = curso.execute("SELECT * FROM orders")
    users_rows = curso.execute("SELECT * FROM users")
    return render_template('pages/index.html', result=result, row=num_rows, order_rows=order_rows,
                           users_rows=users_rows)


@app.route('/orders')
@is_admin_logged_in
def orders():
    curso = mysql.connection.cursor()
    num_rows = curso.execute("SELECT * FROM products")
    order_rows = curso.execute("SELECT * FROM orders")
    result = curso.fetchall()
    users_rows = curso.execute("SELECT * FROM users")
    return render_template('pages/all_orders.html', result=result, row=num_rows, order_rows=order_rows,
                           users_rows=users_rows)


@app.route('/users')
@is_admin_logged_in
def users():
    curso = mysql.connection.cursor()
    num_rows = curso.execute("SELECT * FROM products")
    order_rows = curso.execute("SELECT * FROM orders")
    users_rows = curso.execute("SELECT * FROM users")
    result = curso.fetchall()
    return render_template('pages/all_users.html', result=result, row=num_rows, order_rows=order_rows,
                           users_rows=users_rows)


@app.route('/admin_add_product', methods=['POST', 'GET'])
@is_admin_logged_in
def admin_add_product():
    if request.method == 'POST':
        name = request.form.get('name')
        price = request.form['price']
        description = request.form['description']
        available = request.form['available']
        category = request.form['category']
        item = request.form['item']
        code = request.form['code']
        file = request.files['picture']
        if name and price and description and available and category and item and code and file:
            pic = file.filename
            photo = pic.replace("'", "")
            picture = photo.replace(" ", "_")
            if picture.lower().endswith(('.png', '.jpg', '.jpeg')):
                save_photo = photos.save(file, folder=category)
                if save_photo:
                    # Create Cursor
                    curs = mysql.connection.cursor()
                    curs.execute("INSERT INTO products(pName,price,description,available,category,item,pCode,picture)"
                                 "VALUES(%s, %s, %s, %s, %s, %s, %s, %s)",
                                 (name, price, description, available, category, item, code, picture))
                    mysql.connection.commit()
                    product_id = curs.lastrowid
                    curs.execute("INSERT INTO product_level(product_id)" "VALUES(%s)", [product_id])
                    if category == 'tshirt':
                        level = request.form.getlist('tshirt')
                        for lev in level:
                            yes = 'yes'
                            query = 'UPDATE product_level SET {field}=%s WHERE product_id=%s'.format(field=lev)
                            curs.execute(query, (yes, product_id))
                            # Commit cursor
                            mysql.connection.commit()
                    elif category == 'wallet':
                        level = request.form.getlist('wallet')
                        for lev in level:
                            yes = 'yes'
                            query = 'UPDATE product_level SET {field}=%s WHERE product_id=%s'.format(field=lev)
                            curs.execute(query, (yes, product_id))
                            # Commit cursor
                            mysql.connection.commit()
                    elif category == 'belt':
                        level = request.form.getlist('belt')
                        for lev in level:
                            yes = 'yes'
                            query = 'UPDATE product_level SET {field}=%s WHERE product_id=%s'.format(field=lev)
                            curs.execute(query, (yes, product_id))
                            # Commit cursor
                            mysql.connection.commit()
                    elif category == 'shoes':
                        level = request.form.getlist('shoes')
                        for lev in level:
                            yes = 'yes'
                            query = 'UPDATE product_level SET {field}=%s WHERE product_id=%s'.format(field=lev)
                            curs.execute(query, (yes, product_id))
                            # Commit cursor
                            mysql.connection.commit()
                    else:
                        flash('Product level not fund', 'danger')
                        return redirect(url_for('admin_add_product'))
                    # Close Connection
                    curs.close()

                    flash('Product added successful', 'success')
                    return redirect(url_for('admin_add_product'))
                else:
                    flash('Picture not save', 'danger')
                    return redirect(url_for('admin_add_product'))
            else:
                flash('File not supported', 'danger')
                return redirect(url_for('admin_add_product'))
        else:
            flash('Please fill up all form', 'danger')
            return redirect(url_for('admin_add_product'))
    else:
        return render_template('pages/add_product.html')


@app.route('/edit_product', methods=['POST', 'GET'])
@is_admin_logged_in
def edit_product():
    if 'id' in request.args:
        product_id = request.args['id']
        curso = mysql.connection.cursor()
        res = curso.execute("SELECT * FROM products WHERE id=%s", (product_id,))
        product = curso.fetchall()
        curso.execute("SELECT * FROM product_level WHERE product_id=%s", (product_id,))
        product_level = curso.fetchall()
        if res:
            if request.method == 'POST':
                name = request.form.get('name')
                price = request.form['price']
                description = request.form['description']
                available = request.form['available']
                category = request.form['category']
                item = request.form['item']
                code = request.form['code']
                file = request.files['picture']
                # Create Cursor
                if name and price and description and available and category and item and code and file:
                    pic = file.filename
                    photo = pic.replace("'", "")
                    picture = photo.replace(" ", "")
                    if picture.lower().endswith(('.png', '.jpg', '.jpeg')):
                        file.filename = picture
                        save_photo = photos.save(file, folder=category)
                        if save_photo:
                            # Create Cursor
                            cur = mysql.connection.cursor()
                            exe = curso.execute(
                                "UPDATE products SET pName=%s, price=%s, description=%s, available=%s, category=%s, item=%s, pCode=%s, picture=%s WHERE id=%s",
                                (name, price, description, available, category, item, code, picture, product_id))
                            if exe:
                                if category == 'tshirt':
                                    level = request.form.getlist('tshirt')
                                    for lev in level:
                                        yes = 'yes'
                                        query = 'UPDATE product_level SET {field}=%s WHERE product_id=%s'.format(
                                            field=lev)
                                        cur.execute(query, (yes, product_id))
                                        # Commit cursor
                                        mysql.connection.commit()
                                elif category == 'wallet':
                                    level = request.form.getlist('wallet')
                                    for lev in level:
                                        yes = 'yes'
                                        query = 'UPDATE product_level SET {field}=%s WHERE product_id=%s'.format(
                                            field=lev)
                                        cur.execute(query, (yes, product_id))
                                        # Commit cursor
                                        mysql.connection.commit()
                                elif category == 'belt':
                                    level = request.form.getlist('belt')
                                    for lev in level:
                                        yes = 'yes'
                                        query = 'UPDATE product_level SET {field}=%s WHERE product_id=%s'.format(
                                            field=lev)
                                        cur.execute(query, (yes, product_id))
                                        # Commit cursor
                                        mysql.connection.commit()
                                elif category == 'shoes':
                                    level = request.form.getlist('shoes')
                                    for lev in level:
                                        yes = 'yes'
                                        query = 'UPDATE product_level SET {field}=%s WHERE product_id=%s'.format(
                                            field=lev)
                                        cur.execute(query, (yes, product_id))
                                        # Commit cursor
                                        mysql.connection.commit()
                                else:
                                    flash('Product level not fund', 'danger')
                                    return redirect(url_for('admin_add_product'))
                                flash('Product updated', 'success')
                                return redirect(url_for('edit_product'))
                            else:
                                flash('Data updated', 'success')
                                return redirect(url_for('edit_product'))
                        else:
                            flash('Pic not upload', 'danger')
                            return render_template('pages/edit_product.html', product=product,
                                                   product_level=product_level)
                    else:
                        flash('File not support', 'danger')
                        return render_template('pages/edit_product.html', product=product,
                                               product_level=product_level)
                else:
                    flash('Fill all field', 'danger')
                    return render_template('pages/edit_product.html', product=product,
                                           product_level=product_level)
            else:
                return render_template('pages/edit_product.html', product=product, product_level=product_level)
        else:
            return redirect(url_for('admin_login'))
    else:
        return redirect(url_for('admin_login'))


@app.route('/search', methods=['POST', 'GET'])
def search():
    form = OrderForm(request.form)
    if 'q' in request.args:
        q = request.args['q']
        # Create cursor
        cur = mysql.connection.cursor()
        # Get message
        query_string = "SELECT * FROM products WHERE pName LIKE %s ORDER BY id ASC"
        cur.execute(query_string, ('%' + q + '%',))
        products = cur.fetchall()
        # Close Connection
        cur.close()
        flash('Showing result for: ' + q, 'success')
        return render_template('search.html', products=products, form=form)
    else:
        flash('Search again', 'danger')
        return render_template('search.html')


@app.route('/profile')
@is_logged_in
def profile():
    if 'user' in request.args:
        q = request.args['user']
        curso = mysql.connection.cursor()
        curso.execute("SELECT * FROM users WHERE id=%s", (q,))
        result = curso.fetchone()
        if result:
            if result['id'] == session['uid']:
                curso.execute("SELECT * FROM orders WHERE uid=%s ORDER BY id ASC", (session['uid'],))
                res = curso.fetchall()
                return render_template('profile.html', result=res)
            else:
                flash('Unauthorised', 'danger')
                return redirect(url_for('login'))
        else:
            flash('Unauthorised! Please login', 'danger')
            return redirect(url_for('login'))
    else:
        flash('Unauthorised', 'danger')
        return redirect(url_for('login'))


class UpdateRegisterForm(Form):
    name = StringField('Full Name', [validators.length(min=3, max=50)],
                       render_kw={'autofocus': True, 'placeholder': 'Full Name'})
    email = EmailField('Email', [validators.DataRequired(), validators.Email(), validators.length(min=4, max=25)],
                       render_kw={'placeholder': 'Email'})
    password = PasswordField('Password', [validators.length(min=3)],
                             render_kw={'placeholder': 'Password'})
    mobile = StringField('Mobile', [validators.length(min=11, max=15)], render_kw={'placeholder': 'Mobile'})


@app.route('/settings', methods=['POST', 'GET'])
@is_logged_in
def settings():
    form = UpdateRegisterForm(request.form)
    if 'user' in request.args:
        q = request.args['user']
        curso = mysql.connection.cursor()
        curso.execute("SELECT * FROM users WHERE id=%s", (q,))
        result = curso.fetchone()
        if result:
            if result['id'] == session['uid']:
                if request.method == 'POST' and form.validate():
                    name = form.name.data
                    email = form.email.data
                    password = sha256_crypt.encrypt(str(form.password.data))
                    mobile = form.mobile.data

                    # Create Cursor
                    cur = mysql.connection.cursor()
                    exe = cur.execute("UPDATE users SET name=%s, email=%s, password=%s, mobile=%s WHERE id=%s",
                                      (name, email, password, mobile, q))
                    if exe:
                        flash('Profile updated', 'success')
                        return render_template('user_settings.html', result=result, form=form)
                    else:
                        flash('Profile not updated', 'danger')
                return render_template('user_settings.html', result=result, form=form)
            else:
                flash('Unauthorised', 'danger')
                return redirect(url_for('login'))
        else:
            flash('Unauthorised! Please login', 'danger')
            return redirect(url_for('login'))
    else:
        flash('Unauthorised', 'danger')
        return redirect(url_for('login'))


class DeveloperForm(Form):  #
    id = StringField('', [validators.length(min=1)],
                     render_kw={'placeholder': 'Input a product id...'})


@app.route('/developer', methods=['POST', 'GET'])
def developer():
    form = DeveloperForm(request.form)
    if request.method == 'POST' and form.validate():
        q = form.id.data
        curso = mysql.connection.cursor()
        result = curso.execute("SELECT * FROM products WHERE id=%s", (q,))
        if result > 0:
            x = content_based_filtering(q)
            wrappered = wrappers(content_based_filtering, q)
            execution_time = timeit.timeit(wrappered, number=0)
            seconds = ((execution_time / 1000) % 60)
            return render_template('developer.html', form=form, x=x, execution_time=seconds)
        else:
            nothing = 'Nothing found'
            return render_template('developer.html', form=form, nothing=nothing)
    else:
        return render_template('developer.html', form=form)


if __name__ == '__main__':
    app.run(debug=True)
