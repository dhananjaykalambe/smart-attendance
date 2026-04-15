from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
import math
import pandas as pd
import io
import os

app = Flask(__name__)
app.secret_key = "smart_attendance_key_2026"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    roll_no = db.Column(db.String(50), unique=True, nullable=True)
    name = db.Column(db.String(100))
    branch = db.Column(db.String(50))
    semester = db.Column(db.String(20))
    password = db.Column(db.String(100))
    role = db.Column(db.String(10)) # 'teacher' or 'student'

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    roll_no = db.Column(db.String(50))
    name = db.Column(db.String(100))
    date = db.Column(db.DateTime, default=db.func.current_timestamp())

# Global Session state
active_session = {"lat": None, "lon": None, "is_active": False}

def get_distance(lat1, lon1, lat2, lon2):
    R = 6371000 # Meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))

@app.route('/')
def login_page():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    uid = request.form.get('uid') 
    pwd = request.form.get('password')
    user = User.query.filter((User.roll_no == uid) | (User.name == uid)).filter_by(password=pwd).first()
    
    if user:
        session['user_id'] = user.id
        session['role'] = user.role
        session['name'] = user.name
        session['roll_no'] = user.roll_no
        return redirect(url_for('dashboard'))
    return "Invalid Credentials. <a href='/'>Try again</a>"

@app.route('/dashboard')
def dashboard():
    if 'role' not in session: return redirect('/')
    if session['role'] == 'teacher':
        history = Attendance.query.order_by(Attendance.date.desc()).all()
        return render_template('teacher.html', history=history)
    return render_template('student.html')

@app.route('/start_session', methods=['POST'])
def start_session():
    data = request.json
    active_session.update({"lat": data['lat'], "lon": data['lon'], "is_active": True})
    return jsonify({"status": "Session Started"})

@app.route('/mark_attendance', methods=['POST'])
def mark_attendance():
    if not active_session['is_active']:
        return jsonify({"status": "error", "message": "No active session!"})
    
    data = request.json
    dist = get_distance(data['lat'], data['lon'], active_session['lat'], active_session['lon'])
    
    if dist <= 100:
        new_att = Attendance(roll_no=session['roll_no'], name=session['name'])
        db.session.add(new_att)
        db.session.commit()
        return jsonify({"status": "success", "message": "Attendance Marked Successfully!"})
    return jsonify({"status": "error", "message": f"Out of range ({round(dist)}m away)."})

@app.route('/upload_csv', methods=['POST'])
def upload_csv():
    file = request.files['file']
    if not file: return "No file"
    df = pd.read_csv(io.StringIO(file.stream.read().decode("UTF8")))
    for _, row in df.iterrows():
        if not User.query.filter_by(roll_no=str(row['roll_no'])).first():
            u = User(
                roll_no=str(row['roll_no']), name=row['name'], 
                branch=row['branch'], semester=row['semester'],
                password=str(row['roll_no']), role='student'
            )
            db.session.add(u)
    db.session.commit()
    return redirect('/dashboard')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(name="admin").first():
            admin = User(name="admin", password="admin2324", role="teacher")
            db.session.add(admin)
            db.session.commit()
    app.run(debug=True)