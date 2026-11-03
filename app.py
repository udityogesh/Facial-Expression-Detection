from flask import Flask, render_template, Response, jsonify
import cv2
from keras.models import model_from_json
import numpy as np
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Load model
try:
    json_file = open("emotiondetector.json", "r")
    model_json = json_file.read()
    json_file.close()
    model = model_from_json(model_json)
    model.load_weights("emotiondetector.h5")
    logger.info("Model loaded successfully")
except Exception as e:
    logger.error(f"Error loading model: {e}")
    raise

# Load face cascade
try:
    haar_file = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    face_cascade = cv2.CascadeClassifier(haar_file)
    logger.info("Face cascade loaded successfully")
except Exception as e:
    logger.error(f"Error loading face cascade: {e}")
    raise

labels = {0: 'angry', 1: 'disgust', 2: 'fear', 3: 'happy', 4: 'neutral', 5: 'sad', 6: 'surprise'}

def extract_features(image):
    """Extract features from image for model prediction"""
    try:
        feature = np.array(image)
        feature = feature.reshape(1, 48, 48, 1)
        return feature / 255.0
    except Exception as e:
        logger.error(f"Error extracting features: {e}")
        return None

def generate_frames():
    """Generate video frames with emotion detection"""
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
                
                for (x, y, w, h) in faces:
                    face_image = gray[y:y+h, x:x+w]
                    cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 0, 0), 2)
                    
                    face_image = cv2.resize(face_image, (48, 48))
                    img = extract_features(face_image)
                    
                    if img is not None:
                        pred = model.predict(img, verbose=0)
                        prediction_label = labels[pred.argmax()]
                        
                        # Add emotion label
                        cv2.putText(frame, prediction_label, (x, y-10), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
                
                # Encode frame
                ret, buffer = cv2.imencode('.jpg', frame)
                if not ret:
                    continue
                    
                frame_bytes = buffer.tobytes()
                
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                       
            except Exception as e:
                logger.error(f"Error processing frame: {e}")
                continue
                
    except Exception as e:
        logger.error(f"Error in generate_frames: {e}")
    finally:
        if webcam is not None:
            webcam.release()
            logger.info("Webcam released")

@app.route('/')
def index():
    """Landing page"""
    return render_template('landing.html')

@app.route('/detect')
def detect():
    """Detection page"""
    return render_template('detect.html')

@app.route('/video_feed')
def video_feed():
    """Video streaming route"""
    try:
        return Response(generate_frames(),
                        mimetype='multipart/x-mixed-replace; boundary=frame')
    except Exception as e:
        logger.error(f"Error in video_feed: {e}")
        return jsonify({'error': 'Unable to access video feed'}), 500

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'model_loaded': model is not None,
        'cascade_loaded': face_cascade is not None
    })

@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors"""
    return render_template('landing.html'), 404

@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors"""
    logger.error(f"Server error: {e}")
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(debug=debug, host='0.0.0.0', port=port)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
