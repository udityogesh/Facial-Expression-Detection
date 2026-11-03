# Face Emotion Detection Web App

A local-only web application for real-time face emotion detection using Flask, TensorFlow, and OpenCV. Perfect for running on your local machine!

## 🌟 Features

- 🎭 Real-time emotion detection from webcam
- 🌐 Web-based interface accessible from your local browser
- 🎨 Clean, modern UI with landing page
- 📊 Detects 7 emotions: Angry, Disgust, Fear, Happy, Neutral, Sad, Surprise
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

3. **Access the app**
Open your browser and navigate to: `http://localhost:5000`

**Note:** This is a local-only application designed to run on your computer. You can also access it from other devices on your local network using `http://YOUR_IP:5000`

## 🛠️ Technology Stack

- **Backend**: Flask (Python web framework)
- **ML Model**: Keras/TensorFlow CNN
- **Computer Vision**: OpenCV with Haar Cascade face detection
- **Frontend**: HTML5, CSS3, JavaScript

## 📁 Project Structure

```
.
├── app.py                    # Main Flask application
├── config.py                 # Configuration management
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
│   ├── landing.html        # Landing page with camera access
│   └── detect.html         # Live detection page
├── static/
│   ├── landing.css         # Landing page styles
│   ├── style.css           # Detection page styles
│   └── script.js           # JavaScript functionality
└── images/
    ├── train/              # Training dataset
    └── test/               # Testing dataset
```

## 🎯 Usage

1. **Landing Page**: Visit the home page and click "Open Camera & Start Detection"
2. **Camera Permission**: Allow camera access when prompted by your browser
3. **Detection**: The app automatically redirects to the live detection page
4. **Real-time Analysis**: Watch as emotions are detected and labeled in real-time
5. **Try Expressions**: Make different facial expressions to see the AI in action

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

- `GET /` - Landing page
- `GET /detect` - Detection page
- `GET /video_feed` - Video stream endpoint
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
