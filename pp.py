import os
from flask import Flask, render_template_string, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'pawpals_secret_key_safe_123')

# ⚠️ เบอร์พร้อมเพย์
PROMPTPAY_NUMBER = "0812345678" 

# ตั้งค่าโฟลเดอร์สลิป
UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'slips')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# ตั้งค่าฐานข้อมูล SQLite
db_path = os.path.join(app.root_path, 'instance', 'pawpals_v3.db')
os.makedirs(os.path.dirname(db_path), exist_ok=True)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    pet_name = db.Column(db.String(100), nullable=False)
    service_type = db.Column(db.String(100), nullable=False)
    booking_date = db.Column(db.String(50), nullable=False)
    dropoff_time = db.Column(db.String(20), nullable=False)
    pickup_time = db.Column(db.String(20), nullable=False)
    total_price = db.Column(db.Integer, nullable=False)
    deposit = db.Column(db.Integer, nullable=False)
    slip_file = db.Column(db.String(200), nullable=True)

# สร้างตารางฐานข้อมูลอัตโนมัติทุกครั้งที่แอปเริ่มทำงาน (รองรับ Gunicorn บน Render)
with app.app_context():
    db.create_all()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PawPals Cafe & Care</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #f4f8f6; font-family: 'Kanit', sans-serif; }
        .navbar { background-color: #2e7d32; }
        .card { border-radius: 15px; border: none; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        .btn-custom { background-color: #ff9800; color: white; font-weight: bold; }
        .btn-custom:hover { background-color: #e68a00; color: white; }
        .live-badge { animation: pulse 1.5s infinite; }
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.4; } 100% { opacity: 1; } }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg mb-4">
        <div class="container">
            <a class="navbar-brand text-white fw-bold" href="/">🐾 PawPals Cafe & Care</a>
            <div>
                {% if session.get('user_id') %}
                    <span class="text-white me-3">สวัสดี, <strong>{{ session['username'] }}</strong></span>
                    <a href="/logout" class="btn btn-sm btn-outline-light">ออกจากระบบ</a>
                {% else %}
                    <a href="/login" class="btn btn-sm btn-light me-2">เข้าสู่ระบบ</a>
                    <a href="/register" class="btn btn-sm btn-custom">สมัครสมาชิก</a>
                {% endif %}
            </div>
        </div>
    </nav>
    <div class="container">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, msg in messages %}
                    <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                        {{ msg }}
                        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        {% if page == 'login' %}
            {% if success_login %}
                <div class="row justify-content-center text-center my-5">
                    <div class="col-md-6 card p-5">
                        <div class="spinner-border text-success mx-auto mb-3" style="width: 3rem; height: 3rem;" role="status"></div>
                        <h4 class="text-success fw-bold">✅ เข้าสู่ระบบสำเร็จ!</h4>
                        <p class="text-muted mb-0">กำลังพาคุณเข้าสู่ระบบจองคิว...</p>
                    </div>
                </div>
                <script>
                    setTimeout(function(){ window.location.href = "/"; }, 1500);
                </script>
            {% else %}
                <div class="row justify-content-center">
                    <div class="col-md-4">
                        <div class="card p-4">
                            <h3 class="text-center fw-bold mb-3">เข้าสู่ระบบ</h3>
                            <form method="POST" action="/login">
                                <div class="mb-3">
                                    <label>ชื่อผู้ใช้งาน</label>
                                    <input type="text" name="username" class="form-control" required>
                                </div>
                                <div class="mb-3">
                                    <label>รหัสผ่าน</label>
                                    <input type="password" name="password" class="form-control" required>
                                </div>
                                <button type="submit" class="btn btn-success w-100">เข้าสู่ระบบ</button>
                            </form>
                        </div>
                    </div>
                </div>
            {% endif %}

        {% elif page == 'register' %}
            <div class="row justify-content-center">
                <div class="col-md-4">
                    <div class="card p-4">
                        <h3 class="text-center fw-bold mb-3">สมัครสมาชิก</h3>
                        <form method="POST" action="/register">
                            <div class="mb-3">
                                <label>ตั้งชื่อผู้ใช้งาน (Username)</label>
                                <input type="text" name="username" class="form-control" required>
                            </div>
                            <div class="mb-3">
                                <label>ตั้งรหัสผ่าน (Password)</label>
                                <input type="password" name="password" class="form-control" required>
                            </div>
                            <button type="submit" class="btn btn-custom w-100">สมัครสมาชิก</button>
                        </form>
                    </div>
                </div>
            </div>

        {% elif page == 'home' %}
            <div class="card p-3 mb-4 bg-dark text-white">
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <h5 class="mb-0 fw-bold">🎥 ดูน้องๆ แบบ Real-Time 24 ชม.</h5>
                    <span class="badge bg-danger live-badge">● LIVE</span>
                </div>
                <div class="row text-center">
                    <div class="col-md-6 mb-2">
                        <div class="ratio ratio-16x9 rounded overflow-hidden">
                            <iframe src="https://www.youtube.com/embed/live_stream?channel=EXPLORE" title="Pet Cam 1" allowfullscreen></iframe>
                        </div>
                        <small class="text-light mt-1 d-block">กล้อง 1: โซนวิ่งเล่น Daycare</small>
                    </div>
                    <div class="col-md-6 mb-2">
                        <div class="ratio ratio-16x9 rounded overflow-hidden">
                            <iframe src="https://www.youtube.com/embed/live_stream?channel=EXPLORE" title="Pet Cam 2" allowfullscreen></iframe>
                        </div>
                        <small class="text-light mt-1 d-block">กล้อง 2: โซนสปา</small>
                    </div>
                </div>
            </div>

            <div class="row">
                <div class="col-md-6 mb-4">
                    <div class="card p-4">
                        <h4 class="fw-bold mb-3 text-success">📅 จองบริการ PawPals & ชำระเงิน</h4>
                        <form action="/book" method="POST" enctype="multipart/form-data">
                            <div class="mb-3">
                                <label class="form-label fw-bold">ชื่อสัตว์เลี้ยง</label>
                                <input type="text" name="pet_name" class="form-control" placeholder="เช่น น้องมงคล" required>
                            </div>
                            <div class="mb-3">
                                <label class="form-label fw-bold">เลือกบริการ</label>
                                <select name="service_type" id="serviceSelect" class="form-select" onchange="updatePrice()" required>
                                    <option value="สปา & ตัดแต่งขน" data-price="600">สปา & ตัดแต่งขน (600 บาท)</option>
                                    <option value="ฝากเลี้ยง & โรงแรม" data-price="500">ฝากเลี้ยง & โรงแรม (500 บาท/วัน)</option>
                                    <option value="จองโต๊ะคาเฟ่" data-price="200">จองโต๊ะคาเฟ่สัตว์เลี้ยง (200 บาท)</option>
                                </select>
                            </div>
                            <div class="mb-3">
                                <label class="form-label fw-bold">วันที่บริการ</label>
                                <input type="date" name="booking_date" class="form-control" required>
                            </div>
                            
                            <div class="row mb-3">
                                <div class="col-6">
                                    <label class="form-label fw-bold">⏰ เวลาส่งน้อง</label>
                                    <select name="dropoff_time" class="form-select" required>
                                        <option value="09:00">09:00 น.</option>
                                        <option value="10:00" selected>10:00 น.</option>
                                        <option value="11:00">11:00 น.</option>
                                        <option value="13:00">13:00 น.</option>
                                    </select>
                                </div>
                                <div class="col-6">
                                    <label class="form-label fw-bold">⏰ เวลารับน้องกลับ</label>
                                    <select name="pickup_time" class="form-select" required>
                                        <option value="15:00">15:00 น.</option>
                                        <option value="17:00" selected>17:00 น.</option>
                                        <option value="18:00">18:00 น.</option>
                                    </select>
                                </div>
                            </div>

                            <div class="p-3 bg-light rounded mb-3 border text-center">
                                <h6 class="fw-bold text-dark mb-2">💳 สแกนโอนเงินมัดจำ PromptPay</h6>
                                <p class="mb-1 text-muted">ราคารวม: <strong id="totalDisplay" class="text-dark">600</strong> บาท</p>
                                <p class="mb-2 text-danger">ยอดมัดจำ (50%): <strong id="depositDisplay" class="text-danger fs-5">300</strong> บาท</p>
                                
                                <img id="qrImage" src="https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=PromptPay-{{ promptpay_no }}-300" alt="PromptPay QR" class="img-thumbnail my-2" style="width: 170px;">
                                <p class="small text-primary fw-bold mb-0">พร้อมเพย์: {{ promptpay_no }}</p>
                                <small class="d-block text-muted">เปิดแอปธนาคารสแกน หรือโอนตามเบอร์ด้านบน</small>

                                <div class="mt-3 text-start">
                                    <label class="form-label fw-bold text-dark">แนบสลิปการโอนเงิน</label>
                                    <input type="file" name="slip" class="form-control" accept="image/*" required>
                                </div>
                            </div>

                            <button type="submit" class="btn btn-custom w-100 py-2">ยืนยันการจองและส่งสลิปมัดจำ</button>
                        </form>
                    </div>
                </div>

                <div class="col-md-6">
                    <div class="card p-4">
                        <h4 class="fw-bold mb-3">📋 ประวัติการจอง</h4>
                        {% if bookings %}
                            <div class="table-responsive">
                                <table class="table table-hover align-middle">
                                    <thead>
                                        <tr>
                                            <th>น้อง</th>
                                            <th>บริการ</th>
                                            <th>วัน-เวลา</th>
                                            <th>มัดจำ</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {% for b in bookings %}
                                        <tr>
                                            <td><strong>{{ b.pet_name }}</strong></td>
                                            <td><span class="badge bg-success">{{ b.service_type }}</span></td>
                                            <td>
                                                <small class="d-block text-muted">📅 {{ b.booking_date }}</small>
                                                <small class="d-block">🕒 ส่ง {{ b.dropoff_time }} | รับ {{ b.pickup_time }}</small>
                                            </td>
                                            <td>
                                                <span class="badge bg-warning text-dark">{{ b.deposit }} บ.</span>
                                                <small class="d-block text-success">✓ ชำระแล้ว</small>
                                            </td>
                                        </tr>
                                        {% endfor %}
                                    </tbody>
                                </table>
                            </div>
                        {% else %}
                            <p class="text-muted">ยังไม่มีรายการจองในระบบ</p>
                        {% endif %}
                    </div>
                </div>
            </div>

            <script>
                function updatePrice() {
                    var select = document.getElementById("serviceSelect");
                    var price = select.options[select.selectedIndex].getAttribute("data-price");
                    var deposit = price / 2;
                    document.getElementById("totalDisplay").innerText = price;
                    document.getElementById("depositDisplay").innerText = deposit;
                    
                    var ppNo = "{{ promptpay_no }}";
                    document.getElementById("qrImage").src = "https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=PromptPay-" + ppNo + "-" + deposit;
                }
            </script>
        {% endif %}
    </div>
</body>
</html>
"""

@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_bookings = Booking.query.filter_by(user_id=session['user_id']).all()
    return render_template_string(HTML_TEMPLATE, page='home', bookings=user_bookings, promptpay_no=PROMPTPAY_NUMBER)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        
        if User.query.filter_by(username=username).first():
            flash('❌ ชื่อผู้ใช้นี้มีในระบบแล้ว!', 'danger')
            return redirect(url_for('register'))
        
        hashed_pw = generate_password_hash(password)
        new_user = User(username=username, password=hashed_pw)
        db.session.add(new_user)
        db.session.commit()
        
        flash('✅ สมัครสมาชิกสำเร็จ! สามารถเข้าสู่ระบบได้ทันที', 'success')
        return redirect(url_for('login'))
        
    return render_template_string(HTML_TEMPLATE, page='register')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username
            return render_template_string(HTML_TEMPLATE, page='login', success_login=True)
        else:
            flash('❌ รหัสผ่านหรือชื่อผู้ใช้ไม่ถูกต้อง', 'danger')
            return render_template_string(HTML_TEMPLATE, page='login', success_login=False)

    return render_template_string(HTML_TEMPLATE, page='login', success_login=False)

@app.route('/book', methods=['POST'])
def book():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    service_type = request.form['service_type']
    price_map = {'สปา & ตัดแต่งขน': 600, 'ฝากเลี้ยง & โรงแรม': 500, 'จองโต๊ะคาเฟ่': 200}
    total_price = price_map.get(service_type, 500)
    deposit = total_price // 2

    slip_filename = None
    if 'slip' in request.files:
        file = request.files['slip']
        if file.filename != '':
            slip_filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], slip_filename))

    new_booking = Booking(
        user_id=session['user_id'],
        pet_name=request.form['pet_name'],
        service_type=service_type,
        booking_date=request.form['booking_date'],
        dropoff_time=request.form['dropoff_time'],
        pickup_time=request.form['pickup_time'],
        total_price=total_price,
        deposit=deposit,
        slip_file=slip_filename
    )
    db.session.add(new_booking)
    db.session.commit()
    
    flash('🎉 จองคิวและแนบสลิปมัดจำสำเร็จเรียบร้อย!', 'success')
    return redirect(url_for('home'))

@app.route('/logout')
def logout():
    session.clear()
    flash('ออกจากระบบเรียบร้อยแล้ว', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)