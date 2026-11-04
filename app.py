import base64
import binascii
import hmac
import logging
import os
import re
import secrets
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from urllib.parse import urlsplit

import cv2
import numpy as np
from dotenv import load_dotenv
from sqlalchemy import event
from sqlalchemy.engine import Engine
from flask import (
    Flask,
    Response,
    abort,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from keras.models import model_from_json
from werkzeug.security import check_password_hash, generate_password_hash

from config import config as config_by_name
from models import DetectionHistory, DetectionSession, LoginAttempt, User, db


ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, instance_relative_config=True)
os.makedirs(app.instance_path, exist_ok=True)

environment = os.environ.get("FLASK_ENV", "development").lower()
app.config.from_object(config_by_name.get(environment, config_by_name["default"]))
database_url = os.environ.get("DATABASE_URL")
if not database_url:
    database_url = f"sqlite:///{Path(app.instance_path, 'face_emotion_detection.db').as_posix()}"

app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
    SQLALCHEMY_DATABASE_URI=database_url,
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    MAX_CONTENT_LENGTH=16 * 1024 * 1024,
    SEND_FILE_MAX_AGE_DEFAULT=0 if environment == "development" else 3600,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "").lower() == "true",
)

if environment == "production" and not os.environ.get("SECRET_KEY"):
    raise RuntimeError("SECRET_KEY must be configured when FLASK_ENV=production")
if environment == "production":
    app.config["SESSION_COOKIE_SECURE"] = True

db.init_app(app)


@app.after_request
def prevent_stale_page_cache(response):
    if environment == "development" and response.mimetype == "text/html":
        response.headers["Cache-Control"] = "no-store"
    return response


@event.listens_for(Engine, "connect")
def enable_sqlite_foreign_keys(connection, _record):
    if isinstance(connection, sqlite3.Connection):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


try:
    with open(ROOT / "emotiondetector.json", "r", encoding="utf-8") as model_file:
        model = model_from_json(model_file.read())
    model.load_weights(str(ROOT / "emotiondetector.h5"))
    logger.info("Existing emotion model loaded successfully")
except Exception:
    logger.exception("Unable to load the existing emotion model")
    raise

try:
    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    face_cascade = cv2.CascadeClassifier(cascade_path)
    if face_cascade.empty():
        raise RuntimeError("OpenCV face cascade could not be loaded")
    logger.info("Face cascade loaded successfully")
except Exception:
    logger.exception("Unable to load the face cascade")
    raise

labels = {
    0: "angry",
    1: "disgust",
    2: "fear",
    3: "happy",
    4: "neutral",
    5: "sad",
    6: "surprise",
}

_login_attempts_lock = threading.Lock()
_last_login_cleanup = 0.0
LOGIN_ATTEMPT_LIMIT = 5
LOGIN_WINDOW_SECONDS = 15 * 60


def extract_features(image):
    """Apply the existing model's 48x48 grayscale preprocessing."""
    try:
        feature = np.array(image)
        feature = feature.reshape(1, 48, 48, 1)
        return feature / 255.0
    except Exception:
        logger.exception("Error extracting model features")
        return None


def _client_ip():
    return request.remote_addr or "unknown"


def _login_key():
    return hmac.new(
        app.config["SECRET_KEY"].encode("utf-8"),
        _client_ip().encode("utf-8"),
        digestmod="sha256",
    ).hexdigest()


def _login_is_limited(key):
    global _last_login_cleanup
    monotonic_now = time.monotonic()
    with _login_attempts_lock:
        if monotonic_now - _last_login_cleanup >= 300:
            cutoff = datetime.utcnow() - timedelta(seconds=LOGIN_WINDOW_SECONDS)
            LoginAttempt.query.filter(LoginAttempt.attempted_at < cutoff).delete(
                synchronize_session=False
            )
            db.session.commit()
            _last_login_cleanup = monotonic_now
    cutoff = datetime.utcnow() - timedelta(seconds=LOGIN_WINDOW_SECONDS)
    return LoginAttempt.query.filter(
        LoginAttempt.ip_hash == key, LoginAttempt.attempted_at >= cutoff
    ).count() >= LOGIN_ATTEMPT_LIMIT


def _record_login_failure(key):
    db.session.add(LoginAttempt(ip_hash=key))
    db.session.commit()


def _clear_login_failures(key):
    LoginAttempt.query.filter_by(ip_hash=key).delete(synchronize_session=False)
    db.session.commit()


def _csrf_token():
    token = session.get("_csrf_token")
    if token is None:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


@app.before_request
def enforce_csrf_and_load_user():
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        expected = session.get("_csrf_token", "")
        supplied = request.headers.get("X-CSRFToken") or request.form.get("csrf_token", "")
        if (
            not isinstance(expected, str)
            or not isinstance(supplied, str)
            or not expected
            or not supplied
            or not expected.isascii()
            or not supplied.isascii()
            or not hmac.compare_digest(expected, supplied)
        ):
            if request.path.startswith("/api/"):
                return jsonify({"error": "Invalid or missing CSRF token"}), 400
            abort(400, description="Invalid or missing CSRF token")

    expires_at = session.get("auth_expires_at")
    if expires_at and time.time() >= expires_at:
        session.clear()
        if request.path.startswith("/api/"):
            return jsonify({"error": "Session expired. Please sign in again."}), 401
    user_id = session.get("user_id")
    g.user = db.session.get(User, user_id) if user_id else None
    if g.user and g.user.account_status != "ACTIVE":
        session.clear()
        g.user = None
        if request.path.startswith("/api/"):
            return jsonify({"error": "This account is inactive"}), 403
        flash("This account is inactive. Contact an administrator.", "error")
        return redirect(url_for("login"))


@app.context_processor
def inject_template_helpers():
    return {"csrf_token": _csrf_token, "current_user": getattr(g, "user", None)}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not g.user:
            if request.path.startswith("/api/"):
                return jsonify({"error": "Authentication required"}), 401
            return redirect(url_for("login", next=request.full_path))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if g.user.role != "ADMIN":
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def _valid_password(password):
    return (
        len(password) >= 12
        and re.search(r"[a-z]", password)
        and re.search(r"[A-Z]", password)
        and re.search(r"\d", password)
        and re.search(r"[^A-Za-z0-9]", password)
    )


def _dashboard_data(user_id):
    detection_count = DetectionHistory.query.filter_by(user_id=user_id).count()
    session_count = DetectionSession.query.filter_by(user_id=user_id).count()
    face_count = (
        db.session.query(db.func.coalesce(db.func.sum(DetectionSession.total_faces_detected), 0))
        .filter_by(user_id=user_id)
        .scalar()
    )
    most_common = (
        db.session.query(
            DetectionHistory.detected_emotion, db.func.count(DetectionHistory.id).label("total")
        )
        .filter_by(user_id=user_id)
        .group_by(DetectionHistory.detected_emotion)
        .order_by(db.desc("total"))
        .first()
    )
    last_detection = (
        DetectionHistory.query.filter_by(user_id=user_id)
        .order_by(DetectionHistory.detection_timestamp.desc())
        .first()
    )
    emotion_rows = (
        db.session.query(
            DetectionHistory.detected_emotion, db.func.count(DetectionHistory.id)
        )
        .filter_by(user_id=user_id)
        .group_by(DetectionHistory.detected_emotion)
        .all()
    )
    recent = (
        DetectionHistory.query.filter_by(user_id=user_id)
        .order_by(DetectionHistory.detection_timestamp.desc())
        .limit(8)
        .all()
    )
    week_ago = datetime.utcnow() - timedelta(days=6)
    daily_rows = (
        db.session.query(
            db.func.date(DetectionHistory.detection_timestamp),
            db.func.count(DetectionHistory.id),
        )
        .filter(
            DetectionHistory.user_id == user_id,
            DetectionHistory.detection_timestamp >= week_ago,
        )
        .group_by(db.func.date(DetectionHistory.detection_timestamp))
        .all()
    )
    daily_counts = {day: total for day, total in daily_rows}
    activity = [
        {
            "date": (week_ago.date() + timedelta(days=offset)).isoformat(),
            "count": daily_counts.get(
                (week_ago.date() + timedelta(days=offset)).isoformat(), 0
            ),
        }
        for offset in range(7)
    ]
    return {
        "session_count": session_count,
        "detection_count": detection_count,
        "face_count": face_count or 0,
        "most_common": most_common[0].title() if most_common else "—",
        "last_detection": last_detection.detection_timestamp if last_detection else None,
        "emotion_counts": {emotion: count for emotion, count in emotion_rows},
        "recent": recent,
        "activity": activity,
    }


def _predict_from_frame(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)
    if len(faces) == 0:
        return None

    x, y, width, height = max(faces, key=lambda face: face[2] * face[3])
    face_image = cv2.resize(gray[y : y + height, x : x + width], (48, 48))
    features = extract_features(face_image)
    if features is None:
        raise RuntimeError("Unable to preprocess the detected face")
    prediction = model.predict(features, verbose=0)[0]
    if not np.isfinite(prediction).all():
        raise RuntimeError("Model returned a non-finite prediction")
    emotion_index = int(np.argmax(prediction))
    if emotion_index not in labels:
        raise RuntimeError("Model returned an emotion index without a configured label")
    return {
        "emotion": labels[emotion_index],
        "confidence": float(prediction[emotion_index]),
        "bbox": [int(x), int(y), int(width), int(height)],
        "face_count": len(faces),
    }


def generate_frames():
    """Keep the original server webcam stream available for existing clients."""
    webcam = None
    try:
        webcam = cv2.VideoCapture(0)
        if not webcam.isOpened():
            logger.error("Unable to access webcam")
            return

        while True:
            success, frame = webcam.read()
            if not success:
                logger.warning("Failed to read frame from webcam")
                break
            try:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = face_cascade.detectMultiScale(gray, 1.3, 5)
                for (x, y, width, height) in faces:
                    face_image = cv2.resize(gray[y : y + height, x : x + width], (48, 48))
                    features = extract_features(face_image)
                    if features is None:
                        continue
                    prediction = model.predict(features, verbose=0)
                    emotion = labels[int(prediction.argmax())]
                    cv2.rectangle(frame, (x, y), (x + width, y + height), (76, 125, 220), 2)
                    cv2.putText(
                        frame,
                        emotion,
                        (x, max(y - 10, 20)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.8,
                        (76, 125, 220),
                        2,
                    )
                encoded, buffer = cv2.imencode(".jpg", frame)
                if encoded:
                    yield (
                        b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
                        + buffer.tobytes()
                        + b"\r\n"
                    )
            except Exception:
                logger.exception("Error processing legacy video frame")
    finally:
        if webcam is not None:
            webcam.release()
            logger.info("Webcam released")


@app.route("/")
def index():
    return render_template("landing.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return redirect(url_for("index"))

    full_name = request.form.get("full_name", "").strip()
    username = request.form.get("username", "").strip().lower()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    confirmation = request.form.get("confirm_password", "")
    if (
        not 2 <= len(full_name) <= 120
        or not re.fullmatch(r"[a-z0-9_.-]{3,40}", username)
        or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email)
        or len(email) > 254
        or not _valid_password(password)
        or password != confirmation
    ):
        flash("Registration details are invalid.", "error")
    elif User.query.filter(
        db.or_(User.username == username, User.email == email)
    ).first():
        flash("That username or email address is already registered.", "error")
    else:
        db.session.add(
            User(
                full_name=full_name,
                username=username,
                email=email,
                password_hash=generate_password_hash(password),
                role="NORMAL_USER",
                account_status="ACTIVE",
            )
        )
        db.session.commit()
        flash("Account created successfully.", "success")
    return redirect(url_for("index"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return redirect(url_for("index"))
    identifier = request.form.get("identifier", "").strip()
    key = _login_key()
    user = None
    if len(identifier) <= 254 and not _login_is_limited(key):
        user = User.query.filter(
            db.or_(User.email == identifier.lower(), User.username == identifier.lower())
        ).first()
    password = request.form.get("password", "")
    if user and user.account_status == "ACTIVE" and check_password_hash(
        user.password_hash, password
    ):
        _clear_login_failures(key)
        session.clear()
        session["user_id"] = user.id
        session["_csrf_token"] = secrets.token_urlsafe(32)
        remember = request.form.get("remember") == "on"
        session.permanent = True
        session["auth_expires_at"] = time.time() + (
            timedelta(days=30).total_seconds()
            if remember
            else timedelta(hours=12).total_seconds()
        )
        return redirect(
            url_for("admin_dashboard" if user.role == "ADMIN" else "dashboard")
        )
    _record_login_failure(key)
    flash("Sign-in could not be completed.", "error")
    return redirect(url_for("index"))


@app.route("/forgot-password")
def forgot_password():
    return redirect(url_for("index"))


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard():
    if g.user.role == "ADMIN":
        return redirect(url_for("admin_dashboard"))
    return render_template("dashboard/index.html", data=_dashboard_data(g.user.id))


@app.route("/detect")
def detect():
    return render_template("detection.html")


@app.route("/detection")
@login_required
def detection_page():
    return redirect(url_for("detect"))


@app.route("/video_feed")
def video_feed():
    return Response(
        generate_frames(), mimetype="multipart/x-mixed-replace; boundary=frame"
    )


@app.route("/api/detection/sessions", methods=["POST"])
def start_detection_session():
    if not g.user:
        detection_session_id = str(uuid.uuid4())
        session["guest_detection_session"] = detection_session_id
        return jsonify({"session_id": detection_session_id})
    detection_session = DetectionSession(id=str(uuid.uuid4()), user_id=g.user.id)
    db.session.add(detection_session)
    db.session.commit()
    return jsonify({"session_id": detection_session.id})


@app.route("/api/detection/sessions/<session_id>/stop", methods=["POST"])
def stop_detection_session(session_id):
    if not g.user:
        if session.get("guest_detection_session") != session_id:
            return jsonify({"error": "Detection session not found."}), 404
        session.pop("guest_detection_session", None)
        return jsonify({"status": "stopped"})
    detection_session = DetectionSession.query.filter_by(
        id=session_id, user_id=g.user.id
    ).first_or_404()
    if detection_session.ended_at is None:
        detection_session.ended_at = datetime.utcnow()
        db.session.commit()
    return jsonify({"status": "stopped"})


@app.route("/api/detection", methods=["POST"])
def detect_frame():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"error": "A JSON object is required."}), 400
    image_data = payload.get("image")
    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not isinstance(image_data, str):
        return jsonify({"error": "An active session and image are required."}), 400
    detection_session = None
    if g.user:
        detection_session = DetectionSession.query.filter_by(
            id=session_id, user_id=g.user.id, ended_at=None
        ).first()
        if detection_session is None:
            return jsonify({"error": "Detection session not found."}), 404
    elif session.get("guest_detection_session") != session_id:
        return jsonify({"error": "Detection session not found."}), 404
    if len(image_data) > 2_800_000:
        return jsonify({"error": "Image is too large."}), 413
    try:
        encoded_image = image_data.split(",", 1)[-1]
        image_bytes = base64.b64decode(encoded_image, validate=True)
    except (binascii.Error, ValueError):
        return jsonify({"error": "Invalid image data."}), 400
    image_array = np.frombuffer(image_bytes, dtype=np.uint8)
    try:
        frame = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    except cv2.error:
        return jsonify({"error": "Invalid image data."}), 400
    if frame is None:
        return jsonify({"error": "Unable to decode the submitted image."}), 400
    height, width = frame.shape[:2]
    if width > 4096 or height > 4096 or width * height > 16_000_000:
        return jsonify({"error": "Image dimensions are too large."}), 413
    try:
        prediction = _predict_from_frame(frame)
    except Exception:
        logger.exception("Emotion prediction failed")
        return jsonify({"error": "Emotion prediction failed. Please try again."}), 500
    if prediction is None:
        return jsonify({"face_detected": False})

    if not g.user:
        return jsonify(
            {
                "face_detected": True,
                "emotion": prediction["emotion"],
                "confidence": round(prediction["confidence"] * 100, 2),
                "bbox": prediction["bbox"],
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }
        )

    record = DetectionHistory(
        user_id=g.user.id,
        session_id=detection_session.id,
        detected_emotion=prediction["emotion"],
        confidence_score=prediction["confidence"],
    )
    detection_session.total_faces_detected += prediction["face_count"]
    db.session.add(record)
    db.session.commit()
    return jsonify(
        {
            "face_detected": True,
            "emotion": prediction["emotion"],
            "confidence": round(prediction["confidence"] * 100, 2),
            "bbox": prediction["bbox"],
            "timestamp": record.detection_timestamp.isoformat() + "Z",
        }
    )


@app.route("/history")
@login_required
def history():
    page = request.args.get("page", 1, type=int)
    pagination = (
        DetectionHistory.query.filter_by(user_id=g.user.id)
        .order_by(DetectionHistory.detection_timestamp.desc())
        .paginate(page=max(page, 1), per_page=20, error_out=False)
    )
    return render_template("dashboard/history.html", pagination=pagination)


@app.route("/analytics")
@login_required
def analytics():
    data = _dashboard_data(g.user.id)
    return render_template("dashboard/analytics.html", data=data)


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    errors = []
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        username = request.form.get("username", "").strip().lower()
        email = request.form.get("email", "").strip().lower()
        if not 2 <= len(full_name) <= 120:
            errors.append("Full name must be between 2 and 120 characters.")
        if not re.fullmatch(r"[a-z0-9_.-]{3,40}", username):
            errors.append("Username must be 3–40 characters using letters, numbers, dots, underscores or hyphens.")
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) or len(email) > 254:
            errors.append("Enter a valid email address.")
        if User.query.filter(User.username == username, User.id != g.user.id).first():
            errors.append("That username is already taken.")
        if User.query.filter(User.email == email, User.id != g.user.id).first():
            errors.append("That email address is already registered.")
        if not errors:
            g.user.full_name = full_name
            g.user.username = username
            g.user.email = email
            db.session.commit()
            flash("Profile updated.", "success")
            return redirect(url_for("profile"))
    data = _dashboard_data(g.user.id)
    return render_template("dashboard/profile.html", errors=errors, data=data)


@app.route("/settings")
@login_required
def settings():
    return profile()


@app.route("/profile/password", methods=["POST"])
@login_required
def change_password():
    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirmation = request.form.get("confirm_password", "")
    if not check_password_hash(g.user.password_hash, current_password):
        flash("Current password is incorrect.", "error")
    elif not _valid_password(new_password):
        flash("New password must be at least 12 characters and include uppercase, lowercase, a number and a symbol.", "error")
    elif new_password != confirmation:
        flash("New passwords do not match.", "error")
    else:
        g.user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        session.clear()
        flash("Password changed. Sign in again with your new password.", "success")
        return redirect(url_for("login"))
    return redirect(url_for("profile"))


@app.route("/api/change-password", methods=["POST"])
@login_required
def change_password_api():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"error": "A JSON object is required."}), 400
    current_password = payload.get("current_password", "")
    new_password = payload.get("new_password", "")
    confirmation = payload.get("confirm_password", "")
    if not isinstance(current_password, str) or not check_password_hash(
        g.user.password_hash, current_password
    ):
        return jsonify({"error": "Current password is incorrect."}), 400
    if not isinstance(new_password, str) or not _valid_password(new_password):
        return jsonify(
            {
                "error": "New password must be at least 12 characters and include uppercase, lowercase, a number and a symbol."
            }
        ), 400
    if new_password != confirmation:
        return jsonify({"error": "New passwords do not match."}), 400
    g.user.password_hash = generate_password_hash(new_password)
    db.session.commit()
    session.clear()
    return jsonify({"status": "updated", "message": "Sign in again with your new password."})


@app.route("/api/detection/history")
@login_required
def detection_history_api():
    page = max(request.args.get("page", 1, type=int), 1)
    pagination = (
        DetectionHistory.query.filter_by(user_id=g.user.id)
        .order_by(DetectionHistory.detection_timestamp.desc())
        .paginate(page=page, per_page=20, error_out=False)
    )
    return jsonify(
        {
            "items": [
                {
                    "id": item.id,
                    "session_id": item.session_id,
                    "emotion": item.detected_emotion,
                    "confidence": round(item.confidence_score * 100, 2),
                    "timestamp": item.detection_timestamp.isoformat() + "Z",
                }
                for item in pagination.items
            ],
            "page": pagination.page,
            "pages": pagination.pages,
            "total": pagination.total,
        }
    )


@app.route("/api/profile", methods=["GET", "PUT"])
@login_required
def profile_api():
    if request.method == "GET":
        return jsonify(
            {
                "id": g.user.id,
                "full_name": g.user.full_name,
                "username": g.user.username,
                "email": g.user.email,
                "role": g.user.role,
                "created_at": g.user.created_at.isoformat(),
            }
        )
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"error": "A JSON object is required."}), 400
    full_name = str(payload.get("full_name", "")).strip()
    username = str(payload.get("username", "")).strip().lower()
    email = str(payload.get("email", "")).strip().lower()
    if not 2 <= len(full_name) <= 120:
        return jsonify({"error": "Invalid full name."}), 400
    if not re.fullmatch(r"[a-z0-9_.-]{3,40}", username):
        return jsonify({"error": "Invalid username."}), 400
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) or len(email) > 254:
        return jsonify({"error": "Invalid email address."}), 400
    if User.query.filter(User.username == username, User.id != g.user.id).first():
        return jsonify({"error": "Username is already taken."}), 409
    if User.query.filter(User.email == email, User.id != g.user.id).first():
        return jsonify({"error": "Email is already registered."}), 409
    g.user.full_name, g.user.username, g.user.email = full_name, username, email
    db.session.commit()
    return jsonify({"status": "updated"})


@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    total_users = User.query.count()
    active_users = User.query.filter_by(account_status="ACTIVE").count()
    recent_users = User.query.order_by(User.created_at.desc()).limit(10).all()
    registration_start = datetime.utcnow() - timedelta(days=6)
    registration_rows = (
        db.session.query(db.func.date(User.created_at), db.func.count(User.id))
        .filter(User.created_at >= registration_start)
        .group_by(db.func.date(User.created_at))
        .all()
    )
    registrations_by_day = {day: total for day, total in registration_rows}
    registration_activity = [
        {
            "date": (registration_start.date() + timedelta(days=offset)).isoformat(),
            "count": registrations_by_day.get(
                (registration_start.date() + timedelta(days=offset)).isoformat(), 0
            ),
        }
        for offset in range(7)
    ]
    emotion_rows = (
        db.session.query(
            DetectionHistory.detected_emotion, db.func.count(DetectionHistory.id)
        )
        .group_by(DetectionHistory.detected_emotion)
        .all()
    )
    activity = (
        DetectionHistory.query.order_by(DetectionHistory.detection_timestamp.desc())
        .limit(10)
        .all()
    )
    return render_template(
        "admin/dashboard.html",
        total_users=total_users,
        active_users=active_users,
        inactive_users=total_users - active_users,
        session_count=DetectionSession.query.count(),
        recent_users=recent_users,
        emotion_counts={emotion: count for emotion, count in emotion_rows},
        activity=activity,
        registration_activity=registration_activity,
    )


@app.route("/admin/users")
@admin_required
def admin_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template("admin/users.html", users=users)


@app.route("/admin/users/<int:user_id>")
@admin_required
def admin_user_detail(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        abort(404)
    data = _dashboard_data(user.id)
    return render_template("admin/user_detail.html", account=user, data=data)


@app.route("/admin/users/<int:user_id>/<action>", methods=["POST"])
@admin_required
def admin_user_status(user_id, action):
    if action not in {"activate", "deactivate"}:
        abort(404)
    user = db.session.get(User, user_id)
    if user is None:
        abort(404)
    if action == "deactivate" and user.id == g.user.id:
        flash("You cannot deactivate your own administrator account.", "error")
        return redirect(url_for("admin_users"))
    if (
        action == "deactivate"
        and user.role == "ADMIN"
        and user.account_status == "ACTIVE"
        and User.query.filter_by(role="ADMIN", account_status="ACTIVE").count() <= 1
    ):
        flash("The last active administrator cannot be deactivated.", "error")
        return redirect(url_for("admin_users"))
    user.account_status = "ACTIVE" if action == "activate" else "INACTIVE"
    db.session.commit()
    flash(f"Account {action}d.", "success")
    return redirect(url_for("admin_users"))


@app.route("/health")
def health():
    return jsonify(
        {
            "status": "healthy",
            "model_loaded": model is not None,
            "cascade_loaded": not face_cascade.empty(),
        }
    )


@app.cli.command("create-admin")
def create_admin():
    """Interactively create the first administrator account."""
    import click

    email = os.environ.get("ADMIN_EMAIL") or click.prompt("Administrator email").strip().lower()
    username = (
        os.environ.get("ADMIN_USERNAME")
        or click.prompt("Administrator username").strip().lower()
    )
    full_name = os.environ.get("ADMIN_FULL_NAME") or click.prompt("Administrator full name")
    password = os.environ.get("ADMIN_PASSWORD") or click.prompt(
        "Administrator password", hide_input=True, confirmation_prompt=True
    )
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise click.ClickException("Enter a valid administrator email.")
    if not re.fullmatch(r"[a-z0-9_.-]{3,40}", username):
        raise click.ClickException("Username must be 3–40 letters, numbers, dots, underscores or hyphens.")
    if not 2 <= len(full_name.strip()) <= 120:
        raise click.ClickException("Full name must be between 2 and 120 characters.")
    if not _valid_password(password):
        raise click.ClickException("Password must be at least 12 characters and include uppercase, lowercase, a number and a symbol.")
    with app.app_context():
        if User.query.filter(db.or_(User.email == email, User.username == username)).first():
            raise click.ClickException("An account already uses that email or username.")
        user = User(
            full_name=full_name.strip(),
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            role="ADMIN",
            account_status="ACTIVE",
        )
        db.session.add(user)
        db.session.commit()
    click.echo(f"Administrator account created for {email}.")


@app.cli.command("init-db")
def init_db():
    """Create the SQLite tables if they do not exist."""
    with app.app_context():
        db.create_all()
    print("Database tables are ready.")


@app.errorhandler(404)
def not_found(error):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Not found"}), 404
    return render_template("errors/error.html", code=404, message="The page could not be found."), 404


@app.errorhandler(403)
def forbidden(error):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Administrator access required"}), 403
    return render_template("errors/error.html", code=403, message="You do not have permission to view this page."), 403


@app.errorhandler(500)
def server_error(error):
    db.session.rollback()
    logger.exception("Unhandled server error: %s", error)
    if request.path.startswith("/api/"):
        return jsonify({"error": "Internal server error"}), 500
    return render_template("errors/error.html", code=500, message="Something went wrong. Please try again."), 500


with app.app_context():
    db.create_all()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(
        debug=os.environ.get("FLASK_ENV") == "development",
        host="0.0.0.0",
        port=port,
        use_reloader=False,
    )
