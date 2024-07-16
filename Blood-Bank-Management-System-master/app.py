from flask import Flask, render_template, flash, redirect, request, url_for, session
from flask_mysqldb import MySQL
from wtforms import Form, StringField, PasswordField, validators
from functools import wraps
from passlib.hash import sha256_crypt
import random

app = Flask(__name__)
app.secret_key = 'some_secret_key'

# Configure MySQL
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
# app.config['MYSQL_PASSWORD'] = '123456'
app.config['MYSQL_DB'] = 'bloodbank'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

# Initialize MySQL
mysql = MySQL(app)

# Home page
@app.route('/')
def index():
    return render_template('home.html')

# Contact page
class ContactForm(Form):
    bgroup = StringField('Blood Group', [validators.DataRequired()])
    bpackets = StringField('Packets', [validators.DataRequired()])
    fname = StringField('Full Name', [validators.DataRequired()])
    address = StringField('Address', [validators.DataRequired()])

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    form = ContactForm(request.form)
    if request.method == 'POST' and form.validate():
        bgroup = form.bgroup.data
        bpackets = form.bpackets.data
        fname = form.fname.data
        address = form.address.data

        # Check if B_GROUP exists in BLOODBANK table
        cur = mysql.connection.cursor()
        result = cur.execute("SELECT * FROM BLOODBANK WHERE B_GROUP = %s", [bgroup])

        if result > 0:
            # B_GROUP exists, proceed with insertion
            cur.execute("INSERT INTO CONTACT(B_GROUP, C_PACKETS, F_NAME, ADDRESS) VALUES (%s, %s, %s, %s)", (bgroup, bpackets, fname, address))
            cur.execute("INSERT INTO NOTIFICATIONS(NB_GROUP, N_PACKETS, NF_NAME, NADRESS) VALUES (%s, %s, %s, %s)", (bgroup, bpackets, fname, address))

            # Commit to DB
            mysql.connection.commit()
            cur.close()

            flash('Your request is successfully sent to the Blood Bank', 'success')
            return redirect(url_for('index'))
        else:
            # B_GROUP does not exist in BLOODBANK table
            flash('Invalid Blood Group specified', 'danger')
            return redirect(url_for('contact'))

    return render_template('contact.html', form=form)

# Registration form
class RegisterForm(Form):
    name = StringField('Name', [validators.DataRequired(), validators.Length(min=1, max=25)])
    email = StringField('Email', [validators.DataRequired(), validators.Length(min=10, max=50)])
    password = PasswordField('Password', [
        validators.DataRequired(),
        validators.EqualTo('confirm', message='Passwords do not match')
    ])
    confirm = PasswordField('Confirm Password')

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm(request.form)
    if request.method == 'POST' and form.validate():
        name = form.name.data
        email = form.email.data
        password = sha256_crypt.encrypt(str(form.password.data))
        e_id = name + str(random.randint(1111, 9999))

        # Create cursor
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO RECEPTION(E_ID, NAME, EMAIL, PASSWORD) VALUES(%s, %s, %s, %s)", (e_id, name, email, password))

        # Commit to DB
        mysql.connection.commit()
        cur.close()

        flash(f'Success! You can log in with Employee ID {e_id}', 'success')
        return redirect(url_for('login'))

    return render_template('register.html', form=form)

# Login page
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        e_id = request.form["e_id"]
        password_candidate = request.form["password"]

        cur = mysql.connection.cursor()
        result = cur.execute("SELECT * FROM RECEPTION WHERE E_ID = %s", [e_id])

        if result > 0:
            data = cur.fetchone()
            password = data['PASSWORD']

            if sha256_crypt.verify(password_candidate, password):
                session['logged_in'] = True
                session['e_id'] = e_id

                flash('You are now logged in', 'success')
                return redirect(url_for('dashboard'))
            else:
                error = 'Invalid login'
                return render_template('login.html', error=error)
        else:
            error = 'Employee ID not found'
            return render_template('login.html', error=error)

        cur.close()

    return render_template('login.html')

# Check if user logged in
def is_logged_in(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            return f(*args, **kwargs)
        else:
            flash('Unauthorized, Please login!', 'danger')
            return redirect(url_for('login'))
    return wrap

# Logout
@app.route('/logout')
@is_logged_in
def logout():
    session.clear()
    flash('You are now logged out', 'success')
    return redirect(url_for('index'))

# Dashboard
@app.route('/dashboard')
@is_logged_in
def dashboard():
    cur = mysql.connection.cursor()
    cur.callproc('BLOOD_DATA')
    details = cur.fetchall()
    cur.close()

    if details:
        return render_template('dashboard.html', details=details)
    else:
        msg = 'Blood Bank is Empty'
        return render_template('dashboard.html', msg=msg)

# Donation form
class DonationForm(Form):
    dname = StringField('Name', [validators.DataRequired()])
    sex = StringField('Sex', [validators.DataRequired()])
    age = StringField('Age', [validators.DataRequired()])
    weight = StringField('Weight', [validators.DataRequired()])
    address = StringField('Address', [validators.DataRequired()])
    disease = StringField('Disease', [validators.Optional()])
    demail = StringField('Email', [validators.DataRequired(), validators.Email()])

@app.route('/donate', methods=['GET', 'POST'])
@is_logged_in
def donate():
    form = DonationForm(request.form)
    if request.method == 'POST' and form.validate():
        dname = form.dname.data
        sex = form.sex.data
        age = form.age.data
        weight = form.weight.data
        address = form.address.data
        disease = form.disease.data
        demail = form.demail.data

        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO DONOR(DNAME, SEX, AGE, WEIGHT, ADDRESS, DISEASE, DEMAIL) VALUES(%s, %s, %s, %s, %s, %s, %s)", (dname, sex, age, weight, address, disease, demail))

        mysql.connection.commit()
        cur.close()

        flash('Success! Donor details Added.', 'success')
        return redirect(url_for('donorlogs'))

    return render_template('donate.html', form=form)

# Donor logs
@app.route('/donorlogs')
@is_logged_in
def donorlogs():
    cur = mysql.connection.cursor()
    result = cur.execute("SELECT * FROM DONOR")
    logs = cur.fetchall()
    cur.close()

    if result > 0:
        return render_template('donorlogs.html', logs=logs)
    else:
        msg = 'No logs found'
        return render_template('donorlogs.html', msg=msg)

# Blood donation form
class BloodForm(Form):
    d_id = StringField('Donor ID', [validators.DataRequired()])
    blood_group = StringField('Blood Group', [validators.DataRequired()])
    packets = StringField('Packets', [validators.DataRequired()])

@app.route('/bloodform', methods=['GET', 'POST'])
@is_logged_in
def bloodform():
    form = BloodForm(request.form)
    if request.method == 'POST' and form.validate():
        d_id = form.d_id.data
        blood_group = form.blood_group.data
        packets = form.packets.data

        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO BLOOD(D_ID, B_GROUP, PACKETS) VALUES(%s, %s, %s)", (d_id, blood_group, packets))
        cur.execute("UPDATE BLOODBANK SET TOTAL_PACKETS = TOTAL_PACKETS + %s WHERE B_GROUP = %s", (packets, blood_group))
        cur.execute("SELECT * FROM BLOODBANK")
        records = cur.fetchall()

        mysql.connection.commit()
        cur.close()

        flash('Success! Donor Blood details Added.', 'success')
        return redirect(url_for('dashboard'))

    return render_template('bloodform.html', form=form)

# Notifications
@app.route('/notifications')
@is_logged_in
def notifications():
    cur = mysql.connection.cursor()
    result = cur.execute("SELECT * FROM CONTACT")
    requests = cur.fetchall()
    cur.close()

    if result > 0:
        return render_template('notification.html', requests=requests)
    else:
        msg = 'No requests found'
        return render_template('notification.html', msg=msg)

# Accept notification
@app.route('/notifications/accept')
@is_logged_in
def accept():
    flash('Request Accepted', 'success')
    return redirect(url_for('notifications'))

# Decline notification
@app.route('/notifications/decline')
@is_logged_in
def decline():
    msg = 'Request Declined'
    flash(msg, 'danger')
    return redirect(url_for('notifications'))

if __name__ == '__main__':
    app.run(debug=True)

