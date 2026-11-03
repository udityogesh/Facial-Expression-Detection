"""
Basic tests for the Face Emotion Detection application
Run with: pytest tests/
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_app_imports():
    """Test that the app can be imported"""
    try:
        import app
        assert app is not None
    except ImportError as e:
        assert False, f"Failed to import app: {e}"

def test_model_files_exist():
    """Test that model files exist"""
    assert os.path.exists("emotiondetector.h5"), "Model weights file not found"
    assert os.path.exists("emotiondetector.json"), "Model architecture file not found"

def test_template_files_exist():
    """Test that template files exist"""
    assert os.path.exists("templates/landing.html"), "Landing page template not found"
    assert os.path.exists("templates/detect.html"), "Detection page template not found"

def test_static_files_exist():
    """Test that static files exist"""
    assert os.path.exists("static/landing.css"), "Landing CSS not found"
    assert os.path.exists("static/style.css"), "Main CSS not found"
    assert os.path.exists("static/script.js"), "JavaScript file not found"

def test_labels_dictionary():
    """Test that emotion labels are correct"""
    from app import labels
    
    expected_labels = {
        0: 'angry',
        1: 'disgust',
        2: 'fear',
        3: 'happy',
        4: 'neutral',
        5: 'sad',
        6: 'surprise'
    }
    
    assert labels == expected_labels, "Emotion labels don't match expected values"

def test_app_creation():
    """Test that Flask app can be created"""
    from app import app
    assert app is not None
    assert app.name == 'app'

def test_routes_exist():
    """Test that main routes are registered"""
    from app import app
    
    routes = [rule.rule for rule in app.url_map.iter_rules()]
    
    assert '/' in routes, "Landing page route not found"
    assert '/detect' in routes, "Detection page route not found"
    assert '/video_feed' in routes, "Video feed route not found"
    assert '/health' in routes, "Health check route not found"

# Integration tests (optional, can be run separately)
def test_health_endpoint():
    """Test the health check endpoint"""
    from app import app
    
    with app.test_client() as client:
        response = client.get('/health')
        assert response.status_code == 200
        
        data = response.get_json()
        assert 'status' in data
        assert data['status'] == 'healthy'
        assert 'model_loaded' in data
        assert 'cascade_loaded' in data

def test_landing_page():
    """Test that landing page loads"""
    from app import app
    
    with app.test_client() as client:
        response = client.get('/')
        assert response.status_code == 200
        assert b'Face Emotion Detection' in response.data

def test_detect_page():
    """Test that detect page loads"""
    from app import app
    
    with app.test_client() as client:
        response = client.get('/detect')
        assert response.status_code == 200
        assert b'Real-Time Face Emotion Detection' in response.data
