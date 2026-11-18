import os
from pathlib import Path

# ============================================================================
# ENVIRONMENT VARIABLES
# ============================================================================

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / '.env'
    load_dotenv(dotenv_path=env_path)
except ImportError:
    pass  # python-dotenv not installed, will use system env vars

# ============================================================================
# VISION MODE SETTINGS
# ============================================================================

# Vision mode settings
VISION_ANNOUNCEMENT_INTERVAL = 2.0  # seconds
YOLO_MODEL = "yolov8n.pt"  # Will be downloaded automatically
YOLO_CONFIDENCE_THRESHOLD = 0.5
CAMERA_INDEX = 0  # Default camera (0 for USB, can use picamera2 for Pi Camera)

# Raspberry Pi optimizations
USE_PI_CAMERA = False  # Set to True if using Raspberry Pi Camera Module
YOLO_IMG_SIZE = 416  # Smaller image size for faster inference on Pi
YOLO_HALF_PRECISION = False  # Set to True if using Coral TPU or similar

# ============================================================================
# AI SETTINGS (Groq API)
# ============================================================================

# Groq settings
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")  # Get from https://console.groq.com/keys
GROQ_MODEL = "llama-3.1-8b-instant"  # Fast, low-cost, excellent quality
GROQ_VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"  # Llama 4 Scout with vision
# Alternative: "llama-3.3-70b-versatile" for more capability

# ============================================================================
# SPEECH SETTINGS (Text-to-Speech)
# ============================================================================

# Speech settings (Text-to-Speech)
TTS_ENGINE = "festival"  # Options: "piper" (best quality), "pyttsx3", or "espeak"
TTS_RATE = 140  # Words per minute
ESPEAK_VOICE = "en-us+f3"  # Female voice for espeak
PIPER_VOICE = "en_US-lessac-medium"  # Piper voice model (natural female voice)
FESTIVAL_VOICE = "cmu_us_slt_arctic_hts"

# ============================================================================
# SPEECH RECOGNITION SETTINGS
# ============================================================================

# Vosk settings (for wake word detection only)
VOSK_MODEL_PATH = os.path.expanduser("~/.lucy/vosk-model-small-en-us-0.15")
VOSK_SAMPLE_RATE = 16000

# Whisper settings (for speech recognition)
USE_GROQ_WHISPER = True  # Use Groq's Whisper API (fast, no loading time!)
USE_WHISPER = False  # Local Whisper fallback (set to True if Groq fails)
WHISPER_MODEL = "base"  # Only used if USE_WHISPER=True (local fallback)
WHISPER_LANGUAGE = "en"

# ============================================================================
# CONVERSATION MODE SETTINGS
# ============================================================================

# Conversation mode settings
LISTENING_TIMEOUT = 10  # seconds to wait for user speech input (increase for more time)
CONVERSATION_TIMEOUT = 10  # seconds of silence after response before returning to vision mode
MAX_CONVERSATION_TURNS = 5  # Maximum conversation exchanges before auto-return (reduced for Pi)

# System prompts
VISION_SYSTEM_PROMPT = """You are Lucy, an AI assistant for smart glasses helping blind people navigate. 
Describe detected objects and obstacles concisely and clearly, focusing on safety and navigation."""

CONVERSATION_SYSTEM_PROMPT = """You are Lucy, a helpful AI assistant for smart glasses designed for blind people. 
Answer questions VERY briefly and concisely - use 1-2 sentences maximum. Be direct and to the point."""

# ============================================================================
# HARDWARE SETTINGS
# ============================================================================

# Paths
MODEL_DIR = os.path.expanduser("~/.lucy/models")
os.makedirs(MODEL_DIR, exist_ok=True)

# GPIO Button settings (Raspberry Pi only)
USE_GPIO_BUTTON = True  # Set to False to disable button
GPIO_BUTTON_PIN = 17  # GPIO pin number (BCM mode)
GPIO_BUTTON_BOUNCE_TIME = 300  # milliseconds (debounce)

# Performance settings for Raspberry Pi
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 15  # Lower FPS for better performance on Pi

# Vision announcement settings
ANNOUNCE_ONLY_PATH_OBSTACLES = False  # If True, only announce objects directly in path
MAX_OBJECTS_TO_ANNOUNCE = 3  # Maximum objects per announcement
VISION_VERBOSITY = "concise"  # Options: "concise", "normal", "detailed"

# ============================================================================
# ULTRASONIC SENSOR SETTINGS
# ============================================================================

# Enable/disable ultrasonic sensors
USE_ULTRASONIC_SENSORS = True

# Communication mode: "mqtt", "serial", or "both"
ULTRASONIC_MODE = "both"  # Use both MQTT and Serial (auto-fallback)

# MQTT Configuration
MQTT_BROKER = "localhost"  # Change to your MQTT broker IP if on different device
MQTT_PORT = 1883
MQTT_TOPICS = {
    "sensor1": "sensor/ultra1",  # Left sensor topic
    "sensor2": "sensor/ultra2"   # Right sensor topic
}

# Serial Configuration (for ESP32 connected via USB)
SERIAL_PORT = "/dev/ttyUSB0"  # Common: /dev/ttyUSB0, /dev/ttyACM0, or /dev/serial0
SERIAL_BAUD_RATE = 115200
SERIAL_TIMEOUT = 1.0  # seconds

# Sensor positioning (helps with spatial awareness)
SENSOR_POSITIONS = {
    "sensor1": {
        "position": "left",
        "horizontal_angle": -30  # 30 degrees left from center
    },
    "sensor2": {
        "position": "right",
        "horizontal_angle": 30   # 30 degrees right from center
    }
}

# Distance thresholds (in centimeters)
DISTANCE_VERY_CLOSE = 50   # Immediate "STOP!" alerts
DISTANCE_CLOSE = 100       # Regular close warnings
DISTANCE_MEDIUM = 200      # Medium distance mentions
DISTANCE_FAR = 400         # Maximum useful detection range

# Sensor data freshness timeout (seconds)
SENSOR_DATA_TIMEOUT = 2.0  # Consider sensor data stale after 2 seconds

# Sensor averaging settings (NEW)
USE_SENSOR_AVERAGING = True  # Enable averaging between left and right sensors
AVERAGING_WEIGHT_CENTER = 0.6  # Weight for center detection (0.5 = equal weight)
