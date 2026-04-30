from flask import Flask, render_template, request, redirect, flash, session
import os
import sqlite3
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

# Create upload folder
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

VALID_CATEGORIES = {"Cleanliness", "Electrical", "WiFi"}
VALID_LOCATIONS = {"CS IT Block", "Chanakya Block", "Management Block", "Btech Auditorium", "Mechanical Block", "Civil Block", "Other"}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function



def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                category TEXT NOT NULL,
                location TEXT NOT NULL,
                photos TEXT
            )
            """
        )
        conn.commit()


def load_issues():
    init_db()
    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT title, description, category, location, photos FROM issues ORDER BY id DESC"
        ).fetchall()
        return [dict(row) for row in rows]


def save_issue(issue):
    init_db()
    with get_db_connection() as conn:
        conn.execute(
            "INSERT INTO issues (title, description, category, location, photos) VALUES (?, ?, ?, ?, ?)",
            (issue["title"], issue["description"], issue["category"], issue["location"], issue.get("photos", "")),
        )
        conn.commit()


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user_id = request.form.get("user_id", "").strip()
        password = request.form.get("password", "").strip()

        if not user_id or not password:
            flash("Please enter both ID and password.", "error")
            return redirect("/login")

        session["user_id"] = user_id
        flash(f"Welcome, {user_id}!", "success")
        return redirect("/")

    return render_template("login.html")


@app.route("/")
@login_required
def index():
    issues = load_issues()
    return render_template("index.html", issues=issues)


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
