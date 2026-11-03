# 🚀 Quick Start Guide

Get your Face Emotion Detection app running in minutes!

---

## 🏃 Fast Track (2 Minutes)

### Windows
```powershell
# 1. Navigate to project directory
cd path\to\face_emotion_detection_model-main

# 2. Run the startup script
start.bat
```

### Linux/Mac
```bash
# 1. Navigate to project directory
cd path/to/face_emotion_detection_model-main

# 2. Make script executable
chmod +x start.sh

# 3. Run the startup script
./start.sh
```

### Manual Start
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the app
python app.py
```

---

## 🌐 Access Your App

Once running, open your browser:
- **Local:** http://localhost:5000
- **Network:** http://YOUR_IP:5000

---

## ✅ Verify Everything is Ready

Make sure you have:
- ✅ All required files exist
- ✅ Python packages installed (`pip install -r requirements.txt`)
- ✅ Model files present (`emotiondetector.json` and `emotiondetector.h5`)
- ✅ Templates and static files ready

---

## 🔧 Common Issues & Quick Fixes

### Camera Not Working
- ✅ Allow camera permissions in browser
- ✅ Close other apps using camera
- ✅ Try using a different browser (Chrome/Firefox recommended)

### Port Already in Use
```bash
# Windows
netstat -ano | findstr :5000
taskkill /PID <PID> /F

# Linux/Mac
lsof -ti:5000 | xargs kill -9
```

### Module Not Found
```bash
pip install -r requirements.txt --force-reinstall
```

---

## 📊 Check if App is Running

```bash
# Health check
curl http://localhost:5000/health

# Expected response:
# {"status":"healthy","model_loaded":true,"cascade_loaded":true}
```

---

## 🎯 Next Steps

1. ✅ Test locally: http://localhost:5000
2. ✅ Allow camera permissions when prompted
3. ✅ Try different facial expressions to see emotion detection
4. ✅ Share with friends on your local network (same WiFi)
5. ✅ Customize the design or add new features

---

## 📞 Need Help?

- 📖 Read [README.md](README.md) for detailed documentation
- 🐛 Review app logs for error messages
- 🔍 Check that all required files are present

---

## 🎉 You're All Set!

Your emotion detection app is ready to run locally on your machine!

**Made with ❤️ using Flask, TensorFlow, and OpenCV**

**Note:** This is a local-only application designed to run on your computer. Access it via http://localhost:5000
