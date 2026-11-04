import base64
import os
import time

import numpy as np
import pytest
from werkzeug.security import check_password_hash

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-suite-secret"

import app as application
from models import DetectionHistory, DetectionSession, User, db


@pytest.fixture
def client():
    application.app.config.update(
        TESTING=True,
        SECRET_KEY="test-secret",
        SESSION_COOKIE_SECURE=False,
    )
    with application.app.app_context():
        db.drop_all()
        db.create_all()
    with application.app.test_client() as test_client:
        yield test_client
    with application.app.app_context():
        db.session.remove()
        db.drop_all()


def csrf(client, path="/login"):
    response = client.get(path)
    if response.status_code == 302:
        client.get("/")
    with client.session_transaction() as browser_session:
        return browser_session["_csrf_token"]


def register(client, *, full_name="Test User", username="testuser", email="test@example.com"):
    token = csrf(client, "/signup")
    return client.post(
        "/signup",
        data={
            "csrf_token": token,
            "full_name": full_name,
            "username": username,
            "email": email,
            "password": "SecurePass123!",
            "confirm_password": "SecurePass123!",
        },
        follow_redirects=False,
    )


def sign_in(client, identifier="testuser", password="SecurePass123!"):
    token = csrf(client)
    return client.post(
        "/login",
        data={"csrf_token": token, "identifier": identifier, "password": password},
        follow_redirects=False,
    )


def test_signup_hashes_password_and_assigns_normal_role(client):
    response = register(client)
    assert response.status_code == 302
    with application.app.app_context():
        user = User.query.filter_by(username="testuser").one()
        assert user.role == "NORMAL_USER"
        assert user.account_status == "ACTIVE"
        assert user.password_hash != "SecurePass123!"
        assert check_password_hash(user.password_hash, "SecurePass123!")


def test_signup_rejects_duplicate_username_and_email(client):
    register(client)
    response = register(client, username="testuser", email="other@example.com")
    assert response.status_code == 302
    response = register(client, username="otheruser", email="test@example.com")
    assert response.status_code == 302
    with application.app.app_context():
        assert User.query.count() == 1


def test_signup_rejects_weak_password(client):
    token = csrf(client, "/signup")
    response = client.post(
        "/signup",
        data={
            "csrf_token": token,
            "full_name": "Test User",
            "username": "testuser",
            "email": "test@example.com",
            "password": "weak",
            "confirm_password": "weak",
        },
    )
    assert response.status_code == 302
    with application.app.app_context():
        assert User.query.count() == 0


def test_login_logout_and_protected_dashboard(client):
    register(client)
    assert sign_in(client).status_code == 302
    assert client.get("/dashboard").status_code == 200
    assert client.get("/detect").status_code == 200
    assert client.get("/history").status_code == 200
    assert client.get("/analytics").status_code == 200
    assert client.get("/profile").status_code == 200
    assert client.get("/settings").status_code == 200
    token = csrf(client)
    response = client.post("/logout", data={"csrf_token": token})
    assert response.status_code == 302
    assert client.get("/dashboard").status_code == 302


def test_invalid_password_does_not_authenticate(client):
    register(client)
    response = sign_in(client, password="IncorrectPass123!")
    assert response.status_code == 302
    assert client.get("/dashboard").status_code == 302


def test_login_rate_limit_is_enforced(client):
    token = csrf(client)
    for _ in range(application.LOGIN_ATTEMPT_LIMIT):
        response = client.post(
            "/login",
            data={
                "csrf_token": token,
                "identifier": "unknown-user",
                "password": "IncorrectPass123!",
            },
        )
        assert response.status_code == 302
    response = client.post(
        "/login",
        data={
            "csrf_token": token,
            "identifier": "another-user",
            "password": "IncorrectPass123!",
        },
    )
    assert response.status_code == 302


def test_authenticated_session_expiration(client):
    register(client)
    sign_in(client)
    with client.session_transaction() as browser_session:
        browser_session["auth_expires_at"] = time.time() - 1
    assert client.get("/dashboard").status_code == 302
    assert client.get("/api/profile").status_code == 401


def test_guest_detection_api_requires_csrf(client):
    assert client.get("/api/profile").status_code == 401
    response = client.post("/api/detection/sessions", json={})
    assert response.status_code == 400


def test_normal_user_cannot_access_admin_routes(client):
    register(client)
    sign_in(client)
    assert client.get("/admin/dashboard").status_code == 403
    assert client.get("/admin/users").status_code == 403


def test_csrf_required_for_state_changing_requests(client):
    response = client.post("/signup", data={"username": "no-csrf"})
    assert response.status_code == 400
    csrf(client, "/signup")
    response = client.post(
        "/signup", data={"csrf_token": "💥", "username": "no-csrf"}
    )
    assert response.status_code == 400


def test_signin_and_signup_pages_are_removed(client):
    assert client.get("/login").status_code == 302
    assert client.get("/signup").status_code == 302
    assert client.get("/forgot-password").status_code == 302
    assert client.get("/login", follow_redirects=True).request.path == "/"


def test_guest_can_run_camera_predictions_without_saving_history(client, monkeypatch):
    token = csrf(client, "/")
    response = client.post(
        "/api/detection/sessions", json={}, headers={"X-CSRFToken": token}
    )
    assert response.status_code == 200
    session_id = response.get_json()["session_id"]

    expected_prediction = {
        "emotion": "happy",
        "confidence": 0.88,
        "bbox": [1, 2, 48, 48],
        "face_count": 1,
    }
    monkeypatch.setattr(application, "_predict_from_frame", lambda _frame: expected_prediction)
    encoded_ok, encoded_image = application.cv2.imencode(
        ".jpg", np.zeros((60, 60, 3), dtype=np.uint8)
    )
    assert encoded_ok
    response = client.post(
        "/api/detection",
        json={
            "session_id": session_id,
            "image": "data:image/jpeg;base64," + base64.b64encode(encoded_image).decode(),
        },
        headers={"X-CSRFToken": token},
    )
    assert response.status_code == 200
    assert response.get_json()["emotion"] == "happy"
    with application.app.app_context():
        assert DetectionSession.query.count() == 0
        assert DetectionHistory.query.count() == 0
    response = client.post(
        f"/api/detection/sessions/{session_id}/stop",
        headers={"X-CSRFToken": token},
    )
    assert response.status_code == 200


def test_user_cannot_access_another_users_detection_session(client):
    register(client)
    sign_in(client)
    token = csrf(client)
    response = client.post(
        "/api/detection/sessions",
        json={},
        headers={"X-CSRFToken": token},
    )
    session_id = response.get_json()["session_id"]

    client.post("/logout", data={"csrf_token": token})
    register(client, full_name="Second User", username="seconduser", email="second@example.com")
    sign_in(client, identifier="seconduser")
    second_token = csrf(client)
    response = client.post(
        "/api/detection",
        json={
            "session_id": session_id,
            "image": "data:image/jpeg;base64," + base64.b64encode(b"not-an-image").decode(),
        },
        headers={"X-CSRFToken": second_token},
    )
    assert response.status_code == 404


def test_detection_history_api_is_user_scoped(client):
    register(client)
    sign_in(client)
    with application.app.app_context():
        owner = User.query.filter_by(username="testuser").one()
        record_session = DetectionSession(id="owner-session", user_id=owner.id)
        db.session.add(record_session)
        db.session.add(
            DetectionHistory(
                user_id=owner.id,
                session_id=record_session.id,
                detected_emotion="happy",
                confidence_score=0.9,
            )
        )
        db.session.commit()
    token = csrf(client)
    client.post("/logout", data={"csrf_token": token})
    register(client, full_name="Second User", username="seconduser", email="second@example.com")
    sign_in(client, identifier="seconduser")
    response = client.get("/api/detection/history")
    assert response.status_code == 200
    assert response.get_json()["items"] == []


def test_prediction_api_saves_real_model_output_for_owner(client, monkeypatch):
    register(client)
    sign_in(client)
    token = csrf(client)
    session_response = client.post(
        "/api/detection/sessions", json={}, headers={"X-CSRFToken": token}
    )
    session_id = session_response.get_json()["session_id"]

    model_output = application.model.predict(np.zeros((1, 48, 48, 1)), verbose=0)[0]
    emotion_index = int(np.argmax(model_output))
    actual_model_prediction = {
        "emotion": application.labels[emotion_index],
        "confidence": float(model_output[emotion_index]),
        "bbox": [1, 2, 48, 48],
        "face_count": 1,
    }
    monkeypatch.setattr(application, "_predict_from_frame", lambda _frame: actual_model_prediction)
    image = np.zeros((60, 60, 3), dtype=np.uint8)
    success, encoded = application.cv2.imencode(".jpg", image)
    assert success
    response = client.post(
        "/api/detection",
        json={
            "session_id": session_id,
            "image": "data:image/jpeg;base64," + base64.b64encode(encoded.tobytes()).decode(),
        },
        headers={"X-CSRFToken": token},
    )
    assert response.status_code == 200
    assert response.get_json()["emotion"] == actual_model_prediction["emotion"]
    assert client.get("/dashboard").status_code == 200
    assert client.get("/analytics").status_code == 200
    assert client.get("/api/detection/history").get_json()["total"] == 1
    with application.app.app_context():
        history_record = DetectionHistory.query.one()
        detection_session = DetectionSession.query.one()
        assert history_record.user_id == 1
        assert history_record.detected_emotion == actual_model_prediction["emotion"]
        assert detection_session.total_faces_detected == 1


def test_profile_api_returns_only_authenticated_profile(client):
    register(client)
    sign_in(client)
    response = client.get("/api/profile")
    assert response.status_code == 200
    assert response.get_json()["username"] == "testuser"
    assert "password_hash" not in response.get_json()


def test_inactive_accounts_cannot_sign_in(client):
    register(client)
    with application.app.app_context():
        user = User.query.filter_by(username="testuser").one()
        user.account_status = "INACTIVE"
        db.session.commit()
    response = sign_in(client)
    assert response.status_code == 302
    assert client.get("/dashboard").status_code == 302


def test_model_output_uses_existing_seven_class_shape():
    output = application.model.predict(np.zeros((1, 48, 48, 1)), verbose=0)
    assert output.shape == (1, len(application.labels))


def test_existing_detector_and_model_predict_from_a_sample_face():
    sample_path = os.path.join(application.ROOT, "images", "test", "angry", "10052.jpg")
    frame = application.cv2.imread(sample_path)
    assert frame is not None
    upscaled_frame = application.cv2.resize(
        frame, None, fx=5, fy=5, interpolation=application.cv2.INTER_CUBIC
    )
    prediction = application._predict_from_frame(upscaled_frame)
    assert prediction is not None
    assert prediction["emotion"] in application.labels.values()
    assert 0.0 <= prediction["confidence"] <= 1.0
    assert prediction["face_count"] >= 1


def test_admin_can_activate_and_deactivate_user(client):
    register(client)
    with application.app.app_context():
        admin = User(
            full_name="Site Admin",
            username="siteadmin",
            email="admin@example.com",
            password_hash=application.generate_password_hash("SecureAdmin123!"),
            role="ADMIN",
            account_status="ACTIVE",
        )
        db.session.add(admin)
        db.session.commit()
        admin_id = admin.id
        user_id = User.query.filter_by(username="testuser").one().id
    sign_in(client, "siteadmin", "SecureAdmin123!")
    assert client.get("/admin/dashboard").status_code == 200
    assert client.get("/admin/users").status_code == 200
    token = csrf(client, "/admin/users")
    assert client.get(f"/admin/users/{user_id}").status_code == 200
    response = client.post(
        f"/admin/users/{user_id}/deactivate", data={"csrf_token": token}
    )
    assert response.status_code == 302
    with application.app.app_context():
        assert db.session.get(User, user_id).account_status == "INACTIVE"
    response = client.post(
        f"/admin/users/{user_id}/activate", data={"csrf_token": token}
    )
    assert response.status_code == 302
    with application.app.app_context():
        assert db.session.get(User, user_id).account_status == "ACTIVE"
        assert db.session.get(User, admin_id).role == "ADMIN"


def test_create_admin_cli_bootstraps_secure_admin(client):
    result = application.app.test_cli_runner().invoke(
        args=["create-admin"],
        env={
            "ADMIN_FULL_NAME": "Bootstrap Admin",
            "ADMIN_USERNAME": "bootstrap_admin",
            "ADMIN_EMAIL": "bootstrap@example.com",
            "ADMIN_PASSWORD": "BootstrapPass123!",
        },
    )
    assert result.exit_code == 0, result.output
    with application.app.app_context():
        admin = User.query.filter_by(username="bootstrap_admin").one()
        assert admin.role == "ADMIN"
        assert admin.account_status == "ACTIVE"
        assert check_password_hash(admin.password_hash, "BootstrapPass123!")
