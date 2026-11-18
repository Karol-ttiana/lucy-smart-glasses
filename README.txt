# Lucy Smart Glasses - Raspberry Pi

AI-powered smart glasses system for blind people navigation assistance.

## Features

- Vision Mode: Continuous obstacle detection using YOLOv8n
- Conversation Mode: Voice interaction with Groq AI
- Ultrasonic Sensors: Distance measurement via ESP32
- GUI Interface: Real-time camera feed and sensor data display
- GPIO Button: Hardware mode switching

## Hardware Requirements

- Raspberry Pi 5 (or Pi 4)
- USB Camera or Pi Camera Module
- ESP32 with dual ultrasonic sensors (HC-SR04)
- GPIO button (optional)
- Speaker/headphones for audio output
- Microphone for voice input

## Installation

1. Install system dependencies:
```bash
bash setup.sh
```

2. Install Python requirements:
```bash
pip3 install -r requirements.txt
```

3. Configure environment:
```bash
cp .env.example .env
# Edit .env and add your GROQ_API_KEY
```

4. Run the application:
```bash
python3 main.py
```

## Configuration

Edit `config.py` to customize:
- Camera settings
- YOLO model parameters
- Speech recognition settings
- Ultrasonic sensor configuration
- GPIO button pin

## Files

### Core Application
- `main.py` - Main application entry point
- `config.py` - Configuration settings

### Handlers (handlers/)
- `camera_handler.py` - Camera capture management
- `vision_detector.py` - YOLOv8n object detection
- `speech_handler.py` - Text-to-speech output
- `conversation_handler.py` - Groq AI conversation
- `button_handler.py` - GPIO button handling
- `ultrasonic_handler.py` - ESP32 ultrasonic sensor integration

### GUI Components (gui/)
- `gui_manager.py` - Main GUI window manager
- `gui_camera.py` - Camera feed display
- `gui_speech.py` - Speech/conversation display
- `gui_ultrasonic.py` - Ultrasonic sensor visualization
- `gui_response.py` - Response text display

### Setup Scripts
- `setup.sh` - Main setup script
- `install_requirements.sh` - Python dependencies installer
- `start.sh` - Application startup script

### Service
- `lucy-glasses.service` - Systemd service file for auto-start

## License

MIT License
