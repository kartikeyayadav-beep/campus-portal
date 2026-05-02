from flask import Flask, render_template, request, redirect, flash, session, jsonify
import os
import sqlite3
from datetime import datetime
from functools import wraps
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "your-secure-secret-key-change-this"
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024  # 8MB max

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "issues.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static/uploads")
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
MAX_PHOTOS = 5
MAX_FILE_SIZE = 8 * 1024 * 1024  # 8MB

# Admin credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

# Create upload folder
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

VALID_CATEGORIES = {"Cleanliness", "Electrical", "WiFi"}
VALID_LOCATIONS = {"CS IT Block", "Chanakya Block", "Management Block", "Btech Auditorium", "Mechanical Block", "Civil Block", "Other"}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session or session.get("user_type") != "student":
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session or session.get("user_type") != "admin":
            return redirect("/admin/login")
        return f(*args, **kwargs)
    return decorated_function



def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db_connection() as conn:
        # Create issues table with status column
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                category TEXT NOT NULL,
                location TEXT NOT NULL,
                photos TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        
        # Create chat messages table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        
        # Add status column if it doesn't exist (migration)
        try:
            conn.execute("ALTER TABLE issues ADD COLUMN status TEXT DEFAULT 'pending'")
        except:
            pass
        
        try:
            conn.execute("ALTER TABLE issues ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        except:
            pass
        
        conn.commit()


def load_issues(status=None):
    init_db()
    with get_db_connection() as conn:
        if status:
            rows = conn.execute(
                "SELECT id, title, description, category, location, photos, status, created_at FROM issues WHERE status = ? ORDER BY created_at DESC",
                (status,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, title, description, category, location, photos, status, created_at FROM issues ORDER BY created_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]


def save_issue(issue):
    init_db()
    with get_db_connection() as conn:
        conn.execute(
            "INSERT INTO issues (title, description, category, location, photos, status) VALUES (?, ?, ?, ?, ?, 'pending')",
            (issue["title"], issue["description"], issue["category"], issue["location"], issue.get("photos", "")),
        )
        conn.commit()


def update_issue_status(issue_id, status):
    init_db()
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE issues SET status = ? WHERE id = ?",
            (status, issue_id)
        )
        conn.commit()


def delete_issue(issue_id):
    init_db()
    with get_db_connection() as conn:
        conn.execute("DELETE FROM issues WHERE id = ?", (issue_id,))
        conn.commit()


def get_issue_by_id(issue_id):
    init_db()
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT id, title, description, category, location, photos, status FROM issues WHERE id = ?",
            (issue_id,)
        ).fetchone()
        return dict(row) if row else None


def save_chat_message(username, message):
    init_db()
    with get_db_connection() as conn:
        conn.execute(
            "INSERT INTO chat_messages (username, message) VALUES (?, ?)",
            (username, message)
        )
        conn.commit()


def get_chat_messages(limit=50):
    init_db()
    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT username, message, created_at FROM chat_messages ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(row) for row in reversed(rows)]


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user_id = request.form.get("user_id", "").strip()
        password = request.form.get("password", "").strip()

        if not user_id or not password:
            flash("Please enter both ID and password.", "error")
            return redirect("/login")

        session["user_id"] = user_id
        session["user_type"] = "student"
        flash(f"Welcome, {user_id}!", "success")
        return redirect("/")

    return render_template("login.html")


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["user_id"] = username
            session["user_type"] = "admin"
            flash("Welcome, Admin!", "success")
            return redirect("/admin/dashboard")
        else:
            flash("Invalid admin credentials.", "error")
            return redirect("/admin/login")

    return render_template("admin_login.html")


@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    pending_issues = load_issues("pending")
    completed_issues = load_issues("completed")
    return render_template("admin_dashboard.html", pending_issues=pending_issues, completed_issues=completed_issues)


@app.route("/admin/issue/<int:issue_id>/mark-done", methods=["POST"])
@admin_required
def mark_issue_done(issue_id):
    update_issue_status(issue_id, "completed")
    flash("Issue marked as completed.", "success")
    return redirect("/admin/dashboard")


@app.route("/admin/issue/<int:issue_id>/delete", methods=["POST"])
@admin_required
def delete_issue_route(issue_id):
    delete_issue(issue_id)
    flash("Issue deleted.", "success")
    return redirect("/admin/dashboard")


@app.route("/")
@login_required
def index():
    issues = load_issues("pending")
    return render_template("index.html", issues=issues)


@app.route("/chat")
@login_required
def chat():
    return render_template("chat.html")


@app.route("/api/chat/messages")
@login_required
def get_messages():
    messages = get_chat_messages()
    return jsonify(messages)


@app.route("/api/chat/send", methods=["POST"])
@login_required
def send_message():
    data = request.get_json()
    message = data.get("message", "").strip()
    
    if not message:
        return jsonify({"error": "Message cannot be empty"}), 400
    
    username = session.get("user_id", "Anonymous")
    save_chat_message(username, message)
    
    return jsonify({"status": "success", "message": "Message sent"})


@app.route("/submit", methods=["POST"])
@login_required
def submit():
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    category = request.form.get("category", "").strip()
    location = request.form.get("location", "").strip()

    if not title or not description or not category or not location:
        flash("Please complete every field before submitting.", "error")
        return redirect("/")

    if category not in VALID_CATEGORIES:
        category = "Other"
    
    if location not in VALID_LOCATIONS:
        location = "Other"

    # Handle photo uploads
    photos = request.files.getlist("photos")
    saved_photos = []
    
    if photos:
        if len(photos) > MAX_PHOTOS:
            flash(f"Maximum {MAX_PHOTOS} photos allowed.", "error")
            return redirect("/")
        
        total_size = 0
        for photo in photos:
            if photo and photo.filename and allowed_file(photo.filename):
                # Check file size
                photo.seek(0, os.SEEK_END)
                file_size = photo.tell()
                total_size += file_size
                
                if file_size > MAX_FILE_SIZE:
                    flash(f"File {photo.filename} exceeds 8MB limit.", "error")
                    return redirect("/")
                
                filename = secure_filename(photo.filename)
                filename = f"{os.urandom(8).hex()}_{filename}"
                photo.seek(0)
                photo.save(os.path.join(UPLOAD_FOLDER, filename))
                saved_photos.append(filename)

    save_issue({
        "title": title,
        "description": description,
        "category": category,
        "location": location,
        "photos": ",".join(saved_photos) if saved_photos else "",
    })

    flash("Issue submitted successfully.", "success")
    return redirect("/")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect("/login")


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
