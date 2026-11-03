import os, sqlite3
from pathlib import Path
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-before-deployment")
DB_PATH = os.environ.get("DATABASE_PATH", str(Path(__file__).with_name("learnloop.db")))
UPLOAD_DIR = Path(os.environ.get("UPLOAD_FOLDER", str(Path(__file__).with_name("uploads"))))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED = {"pdf", "doc", "docx", "txt", "png", "jpg", "jpeg"}

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, password TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS subjects(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, name TEXT NOT NULL, color TEXT DEFAULT '#5b6df6');
        CREATE TABLE IF NOT EXISTS resources(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, subject_id INTEGER NOT NULL, title TEXT NOT NULL, kind TEXT NOT NULL, url TEXT, filename TEXT, topic TEXT, completed INTEGER DEFAULT 0, shared INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        """)
init_db()

def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapped

@app.route("/")
def index():
    return redirect(url_for("dashboard") if "user_id" in session else url_for("login"))

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        name=request.form.get("name","").strip()
        email=request.form.get("email","").strip().lower()
        password=request.form.get("password","")
        if not name or not email or len(password)<6:
            flash("Enter your name, a valid email, and a password with at least 6 characters.", "error")
        else:
            try:
                with db() as con:
                    con.execute("INSERT INTO users(name,email,password) VALUES(?,?,?)",(name,email,generate_password_hash(password)))
                flash("Account created. Please sign in.", "success")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("That email is already registered.", "error")
    return render_template("auth.html", mode="register")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email=request.form.get("email","").strip().lower()
        password=request.form.get("password","")
        with db() as con:
            user=con.execute("SELECT * FROM users WHERE email=?",(email,)).fetchone()
        if user and check_password_hash(user["password"],password):
            session.clear()
            session["user_id"]=user["id"]; session["name"]=user["name"]
            return redirect(url_for("dashboard"))
        flash("Email or password is incorrect.", "error")
    return render_template("auth.html", mode="login")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    uid=session["user_id"]
    with db() as con:
        subjects=con.execute("SELECT * FROM subjects WHERE user_id=? ORDER BY id DESC",(uid,)).fetchall()
        resources=con.execute("""SELECT r.*,s.name subject FROM resources r JOIN subjects s ON r.subject_id=s.id
          WHERE r.user_id=? ORDER BY r.created_at DESC""",(uid,)).fetchall()
        total=len(resources); done=sum(r["completed"] for r in resources)
    return render_template("dashboard.html", subjects=subjects, resources=resources, total=total, done=done,
                           percent=round(done*100/total) if total else 0)

@app.route("/subjects/add", methods=["POST"])
@login_required
def add_subject():
    name=request.form.get("name","").strip()
    if name:
        with db() as con:
            con.execute("INSERT INTO subjects(user_id,name,color) VALUES(?,?,?)",(session["user_id"],name,request.form.get("color","#5b6df6")))
        flash("Subject added.", "success")
    return redirect(url_for("dashboard"))

@app.route("/subjects/<int:sid>/delete", methods=["POST"])
@login_required
def delete_subject(sid):
    with db() as con:
        own=con.execute("SELECT id FROM subjects WHERE id=? AND user_id=?",(sid,session["user_id"])).fetchone()
        if own:
            con.execute("DELETE FROM resources WHERE subject_id=? AND user_id=?",(sid,session["user_id"]))
            con.execute("DELETE FROM subjects WHERE id=? AND user_id=?",(sid,session["user_id"]))
    flash("Subject and its resources deleted.", "success")
    return redirect(url_for("dashboard"))

@app.route("/resources/add", methods=["POST"])
@login_required
def add_resource():
    uid=session["user_id"]
    title=request.form.get("title","").strip()
    sid=request.form.get("subject_id","")
    kind=request.form.get("kind","Link")
    topic=request.form.get("topic","").strip()
    url=request.form.get("url","").strip()
    file=request.files.get("file")
    filename=None
    if file and file.filename:
        safe=secure_filename(file.filename)
        ext=safe.rsplit(".",1)[-1].lower() if "." in safe else ""
        if ext not in ALLOWED:
            flash("File type not allowed. Use PDF, DOC/DOCX, TXT, PNG, or JPG.", "error")
            return redirect(url_for("dashboard"))
        filename=f"{uid}_{safe}"
        file.save(UPLOAD_DIR/filename)
        kind="File"
    if not title or not sid or (kind=="Link" and not url) or (kind=="File" and not filename):
        flash("Please provide a title, subject, and link or file.", "error")
        return redirect(url_for("dashboard"))
    with db() as con:
        subject=con.execute("SELECT id FROM subjects WHERE id=? AND user_id=?",(sid,uid)).fetchone()
        if not subject:
            flash("Choose one of your subjects.", "error")
            return redirect(url_for("dashboard"))
        con.execute("INSERT INTO resources(user_id,subject_id,title,kind,url,filename,topic) VALUES(?,?,?,?,?,?,?)",
                    (uid,sid,title,kind,url,filename,topic))
    flash("Resource saved.", "success")
    return redirect(url_for("dashboard"))

@app.route("/resources/<int:rid>/toggle", methods=["POST"])
@login_required
def toggle_resource(rid):
    with db() as con:
        r=con.execute("SELECT completed FROM resources WHERE id=? AND user_id=?",(rid,session["user_id"])).fetchone()
        if r: con.execute("UPDATE resources SET completed=? WHERE id=? AND user_id=?",(0 if r["completed"] else 1,rid,session["user_id"]))
    return redirect(url_for("dashboard"))

@app.route("/resources/<int:rid>/share", methods=["POST"])
@login_required
def share_resource(rid):
    with db() as con:
        r=con.execute("SELECT shared FROM resources WHERE id=? AND user_id=?",(rid,session["user_id"])).fetchone()
        if r: con.execute("UPDATE resources SET shared=? WHERE id=? AND user_id=?",(0 if r["shared"] else 1,rid,session["user_id"]))
    flash("Sharing setting updated.", "success")
    return redirect(url_for("dashboard"))

@app.route("/resources/<int:rid>/delete", methods=["POST"])
@login_required
def delete_resource(rid):
    with db() as con:
        r=con.execute("SELECT filename FROM resources WHERE id=? AND user_id=?",(rid,session["user_id"])).fetchone()
        if r:
            if r["filename"]:
                try: (UPLOAD_DIR/r["filename"]).unlink(missing_ok=True)
                except OSError: pass
            con.execute("DELETE FROM resources WHERE id=? AND user_id=?",(rid,session["user_id"]))
    return redirect(url_for("dashboard"))

@app.route("/shared")
@login_required
def shared():
    with db() as con:
        items=con.execute("SELECT r.*,s.name subject,u.name owner FROM resources r JOIN subjects s ON r.subject_id=s.id JOIN users u ON u.id=r.user_id WHERE r.shared=1 AND r.user_id!=? ORDER BY r.created_at DESC",(session["user_id"],)).fetchall()
    return render_template("shared.html",resources=items)

@app.route("/uploads/<path:filename>")
@login_required
def uploaded_file(filename):
    # Only serve files belonging to the logged-in owner.
    with db() as con:
        row=con.execute("SELECT id FROM resources WHERE filename=? AND user_id=?",(filename,session["user_id"])).fetchone()
    if not row: return "Not found",404
    return send_from_directory(UPLOAD_DIR,filename,as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)), debug=False)
