# Face Emotion Detection Web App

A local-only web application for real-time face emotion detection using Flask, TensorFlow, and OpenCV. Perfect for running on your local machine!

## 🌟 Features

- 🎭 Real-time emotion detection from webcam
- 🌐 Web-based interface accessible from your local browser
- 🎨 Clean, modern UI with landing page
- 📊 Detects 7 emotions: Angry, Disgust, Fear, Happy, Neutral, Sad, Surprise
- 🔐 Optional account and role-management backend
- 📈 Personal dashboards, detection history, and analytics
- 🛡️ Administrator account management
- 🚀 Error handling and logging
- 📱 Mobile responsive design
- 💻 Local-only application - runs on your computer

## 🚀 Quick Start

### Local Development

1. **Install Dependencies**
```bash
pip install -r requirements.txt
```

2. **Run the application**

**Windows:**
```bash
start.bat
```

**Linux/Mac:**
```bash
chmod +x start.sh
./start.sh
```

**Or manually:**
```bash
python app.py
```

3. **Open the application**
Open `http://localhost:5000/` for the landing page or go directly to `http://localhost:5000/detect`. Sign-in and sign-up pages are intentionally not included; camera detection works without an account.

To use the retained administrator/dashboard backend, create the initial administrator:
```powershell
python -m flask --app app create-admin
```
The command prompts for the administrator's name, username, email, and password. Passwords must be at least 12 characters and include uppercase, lowercase, a number, and a symbol. To bootstrap from environment variables instead, set `ADMIN_FULL_NAME`, `ADMIN_USERNAME`, `ADMIN_EMAIL`, and `ADMIN_PASSWORD` for this command only, then remove `ADMIN_PASSWORD`.

**Note:** This is a local-only application designed to run on your computer. You can also access it from other devices on your local network using `http://YOUR_IP:5000`

## 🛠️ Technology Stack

- **Backend**: Flask (Python web framework)
- **ML Model**: Keras/TensorFlow CNN
- **Computer Vision**: OpenCV with Haar Cascade face detection
- **Frontend**: HTML5, CSS3, JavaScript

## 📁 Project Structure

```
.
├── app.py                    # Flask routes, authentication, and preserved inference pipeline
├── config.py                 # Environment-based configuration
├── models.py                 # SQLAlchemy user, session, and detection models
├── emotiondetector.json      # Model architecture
├── emotiondetector.h5        # Trained model weights
├── requirements.txt          # Python dependencies
├── start.bat                 # Windows startup script
├── start.sh                  # Linux/Mac startup script
├── .gitignore              # Git ignore rules
├── README.md               # This file
├── QUICKSTART.md           # Quick start guide
├── PROJECT_SUMMARY.md      # Project overview
├── templates/
│   ├── landing.html        # Public product landing page
│   ├── dashboard/          # User overview, history, analytics, profile
│   ├── admin/              # Administrator dashboard and user management
│   └── detection.html      # Browser camera and live prediction interface
├── static/
│   ├── landing.css         # Landing page styles
│   ├── style.css           # Detection page styles
│   └── script.js           # JavaScript functionality
└── images/
    ├── train/              # Training dataset
    └── test/               # Testing dataset
```

## 🎯 Usage

1. Open the landing page and select **Start detection**.
2. Allow browser camera access.
3. Start the camera. Frames are processed using the existing Keras model and its current class mapping.
4. View live predictions, confidence scores, and bounding boxes. Predictions remain in the page for the current browser session.

## Authentication and database

- SQLite is created automatically at `instance/face_emotion_detection.db` the first time the app starts. Set `DATABASE_URL` to use another SQLAlchemy-supported database URL.
- User passwords are stored as Werkzeug password hashes. Public registration always creates an active `NORMAL_USER`; only the `create-admin` CLI command creates administrators.
- Sign-in and sign-up screens are not part of the current UI. Anonymous visitors can use live detection; their predictions are not saved to account history. The account/dashboard backend remains available for existing authenticated sessions and future UI integration.
- Forms and state-changing APIs use session-bound CSRF tokens. Login is limited to five failed attempts per IP per 15 minutes using shared SQLite records. Sessions expire after 12 hours by default (30 days with Remember Me), and protected pages check roles on the server.
- Detection history is filtered by the authenticated user. Administrators can inspect account records and activate or deactivate accounts.
- Browser camera frames are sent to the Flask server for prediction but are not stored. Anonymous predictions are not persisted.
- Email-based password reset is not configured. Users who lose access must contact an administrator.

For production, set a randomly generated `SECRET_KEY`, set `FLASK_ENV=production`, and serve the app over HTTPS. Production mode enables secure session cookies. The development default is generated at process startup; set a persistent secret if you need sessions to survive application restarts.

Example secret generation in PowerShell:
```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

## ⚙️ Configuration

The application runs on `http://localhost:5000` by default. To change the port, edit `app.py`:

```python
port = int(os.environ.get('PORT', 5000))  # Change 5000 to your preferred port
```

## 🔧 Development

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Run in Development Mode
```bash
# Windows
start.bat

# Linux/Mac
chmod +x start.sh
./start.sh

# Or manually
python app.py
```

### Run Tests
```bash
python test_app.py
```

### Fine-tune the emotion model

The optional training script fine-tunes the existing model using only `images/train`.
It creates a stratified validation split, applies class weights and light training-only
augmentation, and stops when validation loss stops improving. The separate `images/test`
set is used only for the final evaluation.

Run from the project directory:

```powershell
.\.venv\Scripts\python.exe train_improved.py
```

Training runs on the available TensorFlow device and may take a long time on CPU.
Candidate model files and test metrics are written to `training_output/`; the model
currently used by the app is not overwritten.

## 📊 Model Information

- **Architecture**: Convolutional Neural Network (CNN)
- **Input Size**: 48x48 grayscale images
- **Output**: 7 emotion classes
- **Framework**: Keras with TensorFlow backend
- **Face Detection**: Haar Cascade Classifier

## 🔒 Security Features

- ✅ Error handling and logging
- ✅ Input validation
- ✅ Secure local configuration

## 📝 API Endpoints

- `GET /` - Public landing page
- `GET /signup`, `GET /login` - Redirect to the public landing page (no auth screens)
- `POST /signup`, `POST /login` - Retained account backend endpoints
- `POST /logout` - Sign out
- `GET /dashboard` - Authenticated user dashboard
- `GET /detect` - Public live detection page
- `POST /api/detection/sessions` - Start a detection session
- `POST /api/detection` - Process a camera frame using the existing model
- `POST /api/detection/sessions/<id>/stop` - End a detection session
- `GET /api/detection/history` - Return the authenticated user's paginated history
- `GET /history`, `GET /analytics`, `GET|POST /profile` - Personal account pages
- `GET /settings`, `GET|PUT /api/profile`, `POST /api/change-password` - Account settings and password changes
- `GET /admin/dashboard`, `GET /admin/users` - Administrator-only pages
- `POST /admin/users/<id>/activate` and `/deactivate` - Administrator-only status changes
- `GET /video_feed` - Server webcam stream for existing clients
- `GET /health` - Health check endpoint

### Health Check Example
```bash
curl http://localhost:5000/health
```

Response:
```json
{
  "status": "healthy",
  "model_loaded": true,
  "cascade_loaded": true
}
```

## 🚨 Troubleshooting

### Camera Not Working
- Ensure your browser has camera permissions enabled
- Check if another application is using the camera
- Try using a different browser (Chrome/Firefox recommended)

### Model Not Loading
- Verify that `emotiondetector.json` and `emotiondetector.h5` exist in the project directory
- Check if the model files are corrupted
- Review logs for specific error messages

### Port Already in Use
Edit `app.py` and change the port number:
```python
port = int(os.environ.get('PORT', 5001))  # Change to 5001
```

Or kill the process using the port:
```bash
# Windows
netstat -ano | findstr :5000
taskkill /PID <PID> /F

# Linux/Mac
lsof -ti:5000 | xargs kill -9
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is for educational purposes.

## 👥 Authors

- *Rinku*

## 🙏 Acknowledgments

- TensorFlow and Keras teams
- OpenCV community
- Flask framework
- Dataset contributors

## 📞 Support

For issues and questions:
- Review logs for error messages
- Check that all required files are present
- Verify Python packages are installed correctly
- Make sure model files (`emotiondetector.json` and `emotiondetector.h5`) exist

## 📝 Notes

- The app streams video frames processed with emotion detection
- Detection works best with good lighting and clear facial visibility
- Multiple faces can be detected simultaneously
- This is a **local-only** application - designed to run on your computer

---

**Made with ❤️ using Flask, TensorFlow, and OpenCV**

**Local-only application for personal use and development! 🎉**
