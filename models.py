from datetime import datetime

from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    username = db.Column(db.String(40), unique=True, nullable=False, index=True)
    email = db.Column(db.String(254), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="NORMAL_USER")
    account_status = db.Column(db.String(20), nullable=False, default="ACTIVE")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    detection_sessions = db.relationship(
        "DetectionSession", back_populates="user", cascade="all, delete-orphan"
    )
    detections = db.relationship(
        "DetectionHistory", back_populates="user", cascade="all, delete-orphan"
    )


class DetectionSession(db.Model):
    __tablename__ = "detection_sessions"

    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    started_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    ended_at = db.Column(db.DateTime, nullable=True)
    total_faces_detected = db.Column(db.Integer, nullable=False, default=0)

    user = db.relationship("User", back_populates="detection_sessions")
    detections = db.relationship(
        "DetectionHistory", back_populates="session", cascade="all, delete-orphan"
    )


class DetectionHistory(db.Model):
    __tablename__ = "detection_history"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id = db.Column(
        db.String(36),
        db.ForeignKey("detection_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    detected_emotion = db.Column(db.String(32), nullable=False, index=True)
    confidence_score = db.Column(db.Float, nullable=False)
    detection_timestamp = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, index=True
    )

    user = db.relationship("User", back_populates="detections")
    session = db.relationship("DetectionSession", back_populates="detections")


class LoginAttempt(db.Model):
    __tablename__ = "login_attempts"

    id = db.Column(db.Integer, primary_key=True)
    ip_hash = db.Column(db.String(64), nullable=False, index=True)
    attempted_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
