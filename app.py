from gc import get_stats

from flask import Flask, render_template, request, redirect, url_for # type: ignore
from flask_sqlalchemy import SQLAlchemy # type: ignore
from datetime import date, datetime, timedelta
import os
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user # type: ignore


# =========================
# FLASK APP CONFIGURATION
# =========================
app = Flask(__name__)
app.config['SECRET_KEY'] = 'ang-iyong-lihim-na-key' # Palitan mo ito ng kahit anong text

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # Dito itatapon ang user pag hindi pa naka-login

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id)) # type: ignore

# Force database path to be in the same folder as this script
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "market_final_system.db")

app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{DB_PATH}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# =========================
# DATABASE MODEL
# =========================
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)

class Stall(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    stall_no = db.Column(db.String(20), nullable=False)
    permit_no = db.Column(db.String(50), nullable=False)
    vendor = db.Column(db.String(100), nullable=False)
    section = db.Column(db.String(50), nullable=True)
    date_registered = db.Column(db.Date, nullable=False)
    expiry_date = db.Column(db.Date, nullable=False)


def get_status(expiry_date):
    today = date.today()
    days_left = (expiry_date - today).days

    if days_left <= 0:
        return "expired", days_left
    elif 1 <= days_left <= 2:
        return "warning", days_left
    else:
        return "active", days_left

# Initialize the database
with app.app_context():
    db.create_all()

# =========================
# HOME PAGE (DASHBOARD)
# =========================
@app.route('/')
@login_required # Siguraduhin na nandito ito kung gumagamit ka na ng login
def index():
    search = request.args.get('search', '')
    filter_type = request.args.get('filter', '')
    today = date.today()

    # 1. Kunin lahat at i-assign ang status agad
    all_stalls = Stall.query.all()
    for s in all_stalls:
        # Siguraduhin na wala nang "s." sa harap ng get_stats kung inilabas mo na ito sa class
        s.status, s.days_left = get_status(s.expiry_date) # type: ignore

    # 2. DEFAULT LIST (Lahat ng stalls)
    stalls = all_stalls

    # 3. SEARCH LOGIC
    if search:
        stalls = [
            s for s in stalls
            if search.lower() in s.vendor.lower()
            or search.lower() in s.stall_no.lower()
        ]

    # 4. FILTERS LOGIC (Dito ang fix para hindi na baliktad!)
    if filter_type == 'active':
        stalls = [s for s in stalls if s.status == 'active']

    elif filter_type == 'expiring':
        stalls = [s for s in stalls if s.status == 'warning']

    elif filter_type == 'expired':
        stalls = [s for s in stalls if s.status == 'expired']

    elif filter_type == 'total':
        stalls = all_stalls

    # 5. COUNTS (Para sa dashboard cards)
    total = len(all_stalls)
    active = len([s for s in all_stalls if s.status == 'active'])
    expiring = len([s for s in all_stalls if s.status == 'warning'])
    expired = len([s for s in all_stalls if s.status == 'expired'])

    return render_template(
        'index.html',
        stalls=stalls,
        total=total,
        active=active,
        expiring=expiring,
        expired=expired,
        today=today
    )
# =========================
# CREATE RECORD
# =========================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and user.password == password:
            login_user(user)
            return redirect(url_for('index'))
        else:
            # Pwede kang mag-flash ng error message dito sa susunod
            return "Maling username o password!"
            
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        # Check kung existing na ang username
        user_exists = User.query.filter_by(username=username).first()
        if user_exists:
            return "Username already exists!"
        
        if password != confirm_password:
            return "Passwords do not match!"

        # Gawa ng bagong user
        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()
        
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/add', methods=['POST'])
def add():
    try:
        registered = datetime.strptime(request.form['date_registered'], '%Y-%m-%d').date()
        expiry = datetime.strptime(request.form['expiry_date'], '%Y-%m-%d').date()

        new_stall = Stall(
            stall_no=request.form['stall_no'],
            permit_no=request.form['permit_no'],
            vendor=request.form['vendor'],
            section=request.form['section'],
            date_registered=registered,
            expiry_date=expiry
        )

        db.session.add(new_stall)
        db.session.commit()
    except Exception as e:
        print(f'Error adding record: {e}')

    return redirect(url_for('index'))

# =========================
# UPDATE RECORD
# =========================
@app.route('/update/<int:id>', methods=['GET', 'POST'])
def update(id):
    stall = Stall.query.get_or_404(id)

    if request.method == 'POST':
        try:
            stall.stall_no = request.form['stall_no']
            stall.permit_no = request.form['permit_no']
            stall.vendor = request.form['vendor']
            stall.section = request.form['section']
            stall.date_registered = datetime.strptime(request.form['date_registered'], '%Y-%m-%d').date()
            stall.expiry_date = datetime.strptime(request.form['expiry_date'], '%Y-%m-%d').date()

            db.session.commit()
            return redirect(url_for('index'))
        except Exception as e:
            print(f'Error updating record: {e}')

    return render_template('update.html', stall=stall)

# =========================
# DELETE RECORD
# =========================
@app.route('/delete/<int:id>')
def delete(id):
    stall = Stall.query.get_or_404(id)
    db.session.delete(stall)
    db.session.commit()
    return redirect(url_for('index'))

# =========================
# RUN APP
# =========================
if __name__ == '__main__':
    app.run(debug=True) 