import os
import uuid
from datetime import datetime, timedelta

import qrcode
from flask import Flask, flash, redirect, render_template, request, session, url_for

from db import get_db, init_db, reset_db


app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "smart_attendance_secret")
app.config["ATTENDANCE_WINDOW_MINUTES"] = 5
app.config["RESET_KEY"] = os.getenv("RESET_KEY", "1234")
app.config["BASE_URL"] = os.getenv("BASE_URL", "http://localhost:5000").rstrip("/")

try:
    init_db()
    print("SQLite DB connected successfully")
except Exception as exc:
    print("DB ERROR:", exc)

COLLEGE_NAME = "Priyadarshini Bhagwati College of Engineering, Nagpur"
PROGRAM_NAME = "Smart Attendance System"
COURSE_INFO = "B.Tech Computer Science & Engineering | 3rd Year | Semester VI"

SUBJECTS = [
    {"code": "ML", "label": "Machine Learning"},
    {"code": "DS", "label": "Data Structures"},
    {"code": "CD", "label": "Compiler Design"},
    {"code": "IPR", "label": "Intellectual Property Rights"},
    {"code": "EOII", "label": "Economics in IT Industry"},
    {"code": "OE-1", "label": "Environmental Engineering"},
    {"code": "ML-Lab (PSL-2)", "label": "Machine Learning Lab"},
    {"code": "CD-Lab", "label": "Compiler Design Lab"},
    {"code": "Hardware-Lab", "label": "Hardware Lab"},
]

SUBJECT_DETAILS = [
    {"code": "ML", "name": "Machine Learning", "teacher": "Prof. Khadse", "contact": "0012", "theory": 70, "practical": 30},
    {"code": "DS", "name": "Data Structures", "teacher": "Prof. Tikle", "contact": "0013", "theory": 70, "practical": 30},
    {"code": "CD", "name": "Compiler Design", "teacher": "Prof. Katore", "contact": "0014", "theory": 70, "practical": 30},
    {"code": "EOII", "name": "Economics in IT Industry", "teacher": "Prof. Deshpande", "contact": "0015", "theory": 35, "practical": 15},
    {"code": "OE-1", "name": "Environmental Engineering", "teacher": "Prof. Takarkhede", "contact": "0016", "theory": 70, "practical": 30},
    {"code": "IPR", "name": "Intellectual Property Rights", "teacher": "Prof. Nikose", "contact": "0017", "theory": 70, "practical": 30},
    {"code": "ML-Lab", "name": "Machine Learning Lab", "teacher": "Prof. Khadse", "contact": "9336", "theory": 25, "practical": 25},
    {"code": "CD-Lab", "name": "Compiler Design Lab", "teacher": "Prof. Katore", "contact": "3643", "theory": 25, "practical": 25},
    {"code": "Hardware-Lab", "name": "Hardware Lab", "teacher": "Prof. Dhande", "contact": "9343", "theory": 25, "practical": 25},
]


@app.context_processor
def inject_layout_data():
    return {
        "college_name": COLLEGE_NAME,
        "program_name": PROGRAM_NAME,
        "course_info": COURSE_INFO,
    }


def build_mark_url(session_id):
    return f"{app.config['BASE_URL']}/mark?session_id={session_id}"


def is_valid(start_time):
    start = datetime.fromisoformat(start_time)
    window = timedelta(minutes=app.config["ATTENDANCE_WINDOW_MINUTES"])
    return datetime.now() - start <= window


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        roll = request.form.get("roll", "").strip()
        with get_db() as conn:
            student = conn.execute(
                "SELECT name FROM students WHERE roll_no = ?",
                (roll,),
            ).fetchone()

        if not student:
            flash("The roll number was not found. Please try again.", "error")
            return render_template("login.html")

        session["student_id"] = roll
        session["student_name"] = student["name"]
        flash(f"Welcome back, {student['name']}.", "success")
        return redirect(url_for("scan"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for("login"))


@app.route("/scan")
def scan():
    if "student_id" not in session:
        flash("Please log in before scanning a session QR code.", "warning")
        return redirect(url_for("login"))
    return render_template("scan.html", name=session["student_name"])


@app.route("/create_session", methods=["GET", "POST"])
def create_session():
    if request.method == "POST":
        subject = request.form.get("subject", "").strip()
        if not subject:
            flash("Please choose a subject to create a session.", "warning")
            return redirect(url_for("create_session"))

        session_id = str(uuid.uuid4())[:6].upper()
        qr_folder = os.path.join(app.static_folder, "qr_codes")
        os.makedirs(qr_folder, exist_ok=True)

        qr_filename = f"qr_{session_id}.png"
        qr_path = os.path.join(qr_folder, qr_filename)

        qrcode.make(build_mark_url(session_id)).save(qr_path)
        start_time = datetime.now().isoformat()

        with get_db() as conn:
            conn.execute(
                "INSERT INTO sessions (session_id, subject, start_time) VALUES (?, ?, ?)",
                (session_id, subject, start_time),
            )
            conn.commit()

        flash("Attendance session created successfully.", "success")
        return render_template(
            "session.html",
            session_id=session_id,
            subject=subject,
            qr=qr_filename,
            expiry_minutes=app.config["ATTENDANCE_WINDOW_MINUTES"],
        )

    return render_template("create_session.html", subjects=SUBJECTS)


@app.route("/mark", methods=["GET", "POST"])
def mark():
    session_id = (request.form.get("session_id") or request.args.get("session_id") or "").strip()

    if "student_id" not in session:
        flash("Please log in before marking attendance.", "warning")
        return redirect(url_for("login"))
    if not session_id:
        flash("Session ID is required to mark attendance.", "warning")
        return redirect(url_for("scan"))

    student_id = session["student_id"]
    with get_db() as conn:
        result = conn.execute(
            "SELECT subject, start_time FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()

        if not result:
            return render_template("status.html", title="Invalid Session", message="The attendance session could not be found. Please scan a valid QR code or ask your faculty for the correct session ID.", tone="error")
        if not is_valid(result["start_time"]):
            return render_template("status.html", title="Session Expired", message=f"This session is older than {app.config['ATTENDANCE_WINDOW_MINUTES']} minutes and can no longer accept attendance.", tone="warning")

        existing = conn.execute(
            "SELECT 1 FROM attendance WHERE student_id = ? AND session_id = ?",
            (student_id, session_id),
        ).fetchone()
        if existing:
            return render_template("status.html", title="Attendance Already Marked", message="Your attendance for this session has already been recorded.", tone="info")

        conn.execute(
            """
            INSERT INTO attendance (student_id, session_id, subject, time)
            VALUES (?, ?, ?, ?)
            """,
            (student_id, session_id, result["subject"], datetime.now().isoformat()),
        )
        conn.commit()

    return render_template("status.html", title="Attendance Marked Successfully", message=f"Your attendance for {result['subject']} has been saved.", tone="success")


@app.route("/attendance")
def attendance():
    with get_db() as conn:
        data = conn.execute(
            """
            SELECT s.roll_no, s.name, s.branch, a.session_id, a.subject, a.time
            FROM attendance a
            JOIN students s ON a.student_id = s.roll_no
            ORDER BY a.time DESC
            """
        ).fetchall()
    return render_template("attendance.html", data=data)


@app.route("/add_student", methods=["GET", "POST"])
def add_student():
    with get_db() as conn:
        if request.method == "POST":
            roll = request.form.get("roll", "").strip()
            name = request.form.get("name", "").strip()
            branch = request.form.get("branch", "").strip()

            if not all([roll, name, branch]):
                flash("All student fields are required.", "warning")
            else:
                try:
                    conn.execute(
                        "INSERT INTO students (roll_no, name, branch) VALUES (?, ?, ?)",
                        (roll, name, branch),
                    )
                    conn.commit()
                    flash("Student added successfully.", "success")
                    return redirect(url_for("add_student"))
                except Exception:
                    flash("A student with this roll number already exists.", "error")

        students = conn.execute(
            "SELECT roll_no, name, branch FROM students ORDER BY roll_no"
        ).fetchall()

    return render_template("add_student.html", students=students)


@app.route("/students_report", methods=["GET", "POST"])
def students_report():
    from_date = request.form.get("from_date", "").strip()
    to_date = request.form.get("to_date", "").strip()
    subject_filter = request.form.get("subject", "").strip()

    query = """
        SELECT s.roll_no, s.name, s.branch, a.subject, COUNT(a.student_id) AS total
        FROM students s
        LEFT JOIN attendance a ON s.roll_no = a.student_id
        WHERE 1 = 1
    """
    params = []

    if subject_filter:
        query += " AND a.subject = ?"
        params.append(subject_filter)
    if from_date and to_date:
        query += " AND date(a.time) BETWEEN ? AND ?"
        params.extend([from_date, to_date])

    query += " GROUP BY s.roll_no, s.name, s.branch, a.subject ORDER BY s.roll_no"

    with get_db() as conn:
        data = conn.execute(query, params).fetchall()
        if from_date and to_date:
            total_sessions = conn.execute(
                """
                SELECT subject, COUNT(DISTINCT session_id)
                FROM sessions
                WHERE date(start_time) BETWEEN ? AND ?
                GROUP BY subject
                """,
                (from_date, to_date),
            ).fetchall()
        else:
            total_sessions = conn.execute(
                """
                SELECT subject, COUNT(DISTINCT session_id)
                FROM sessions
                GROUP BY subject
                """
            ).fetchall()

    total_sessions_dict = {row["subject"]: row[1] for row in total_sessions}
    return render_template(
        "students_report.html",
        data=data,
        total_sessions_dict=total_sessions_dict,
        subjects=SUBJECTS,
        filters={"from_date": from_date, "to_date": to_date, "subject": subject_filter},
    )


@app.route("/delete_student/<roll_no>")
def delete_student(roll_no):
    with get_db() as conn:
        conn.execute("DELETE FROM students WHERE roll_no = ?", (roll_no,))
        conn.commit()
    flash("Student removed successfully.", "info")
    return redirect(url_for("add_student"))


@app.route("/admin/reset-db/<key>")
def secure_reset(key):
    if key != app.config["RESET_KEY"]:
        return render_template("status.html", title="Unauthorized Access", message="The provided reset key is not valid.", tone="error")

    reset_db()
    return render_template("status.html", title="Database Reset Complete", message="The database has been recreated successfully.", tone="success")


@app.route("/subject_details")
def subject_details():
    return render_template("subject_details.html", subjects=SUBJECT_DETAILS)


@app.route("/about")
def about():
    return render_template("about.html")


if __name__ == "__main__":
    app.run(debug=True)
