#!/usr/bin/env python3
"""
Lucy Smart Glasses - Main Application
A smart glasses system for visually impaired users with:
- Vision mode: Continuous object detection and obstacle warnings
- Conversation mode: AI-powered voice assistant
"""

# ============================================================================
# IMPORTS
# ============================================================================
import time
import signal
import sys
import threading
from enum import Enum

# Configuration
import config

# Hardware Handlers
from handlers.camera_handler import CameraHandler
from handlers.vision_detector import VisionDetector
from handlers.speech_handler import SpeechHandler, SpeechRecognizer
from handlers.conversation_handler import ConversationHandler
from handlers.button_handler import ButtonHandler
from handlers.ultrasonic_handler import UltrasonicHandler

# GUI (Optional)
try:
    from gui.gui_manager import GUIManager
    GUI_AVAILABLE = True
except ImportError:
    print("Warning: GUI not available (Pillow not installed)")
    GUI_AVAILABLE = False


# ============================================================================
# ENUMS - Operating Modes and States
# ============================================================================

class Mode(Enum):
    """Application operating modes"""
    VISION = "vision"              # Continuous object detection
    CONVERSATION = "conversation"  # Voice assistant mode


class VisionState(Enum):
    """States within vision mode"""
    READY_TO_CAPTURE = "ready_to_capture"  # Ready to take picture
    PROCESSING_IMAGE = "processing_image"  # Analyzing image
    SPEAKING = "speaking"                  # Announcing results
    WAITING = "waiting"                    # Brief pause before next cycle


# ============================================================================
# MAIN APPLICATION CLASS
# ============================================================================

class LucyGlasses:
    """Main application class for Lucy Smart Glasses"""
    
    def __init__(self):
        """Initialize all hardware handlers and GUI"""
        self.camera = CameraHandler()
        self.vision_detector = VisionDetector()
        self.speech = SpeechHandler()
        self.speech_recognizer = SpeechRecognizer()
        self.conversation = ConversationHandler()
        self.button = ButtonHandler()
        self.ultrasonic = UltrasonicHandler()
        
        # Initialize GUI if available
        self.gui = None
        if GUI_AVAILABLE:
            try:
                self.gui = GUIManager()
                print("GUI initialized")
            except Exception as e:
                print(f"Warning: Could not initialize GUI: {e}")
                self.gui = None
        
        self.current_mode = Mode.VISION
        self.vision_state = VisionState.READY_TO_CAPTURE
        self.running = False
        self.last_announcement_time = 0
        self.interrupt_listening = False
    
    # ========================================================================
    # INITIALIZATION
    # ========================================================================
    
    def initialize(self) -> bool:
        """Initialize all components. Returns True if successful."""
        print("=" * 50)
        print("Lucy Smart Glasses - Initializing...")
        print("=" * 50)
        
        # Initialize camera
        if not self.camera.start():
            print("Failed to initialize camera")
            return False
        
        # Initialize vision detector
        if not self.vision_detector.initialize():
            print("Failed to initialize vision detector")
            return False
        
        # Initialize speech
        if not self.speech.initialize():
            print("Failed to initialize speech handler")
            return False
        
        # Initialize speech recognizer
        if not self.speech_recognizer.initialize():
            print("Warning: Speech recognizer not initialized (optional)")
        
        # Initialize conversation handler
        if not self.conversation.initialize():
            print("Failed to initialize conversation handler")
            return False
        
        # Initialize button handler
        if not self.button.initialize():
            print("Warning: Button handler not initialized (optional)")
        
        # Initialize ultrasonic sensors
        if not self.ultrasonic.initialize():
            print("Warning: Ultrasonic sensors not initialized (optional)")
        
        print("=" * 50)
        print("Initialization complete!")
        print("=" * 50)
        
        return True
    
    # ========================================================================
    # VISION MODE - Continuous Object Detection
    # ========================================================================
    
    def run_vision_mode(self):
        """Main loop for vision mode - detects objects and announces them"""
        current_time = time.time()
        
        # PRIORITY 1: Check for CRITICAL ultrasonic alerts (VERY CLOSE - STOP!)
        ultrasonic_alerts = self.ultrasonic.get_critical_alerts()
        if ultrasonic_alerts:
            for alert in ultrasonic_alerts:
                if "very close" in alert.lower():
                    # STOP EVERYTHING and warn immediately
                    self.speech.speak("STOP! STOP! Obstacle very close!", interrupt=True)
                    print(f"[CRITICAL ALERT] {alert}")
                    return
        
        if self.vision_state == VisionState.READY_TO_CAPTURE:
            # Check if enough time has passed for next announcement
            if current_time - self.last_announcement_time >= config.VISION_ANNOUNCEMENT_INTERVAL:
                print("[VISION] Taking picture...")
                self.vision_state = VisionState.PROCESSING_IMAGE
        
        elif self.vision_state == VisionState.PROCESSING_IMAGE:
            frame = self.camera.get_frame()
            
            if frame is not None:
                # STEP 1: Get CAMERA detections (what objects are there)
                detections = self.vision_detector.detect_objects(frame)
                camera_description = self.vision_detector.generate_description(detections)
                
                # Update GUI with YOLO boxes when Lucy analyzes
                if self.gui:
                    import cv2
                    gui_frame = cv2.resize(frame, (640, 480))
                    
                    # Scale bounding boxes
                    scale_x = 640 / frame.shape[1]
                    scale_y = 480 / frame.shape[0]
                    
                    gui_detections = []
                    for det in detections:
                        label = det['class']
                        conf = det['confidence']
                        x1, y1, x2, y2 = det['bbox']
                        scaled_bbox = (
                            int(x1 * scale_x),
                            int(y1 * scale_y),
                            int(x2 * scale_x),
                            int(y2 * scale_y)
                        )
                        gui_detections.append((label, conf, scaled_bbox))
                    
                    self.gui.update_camera(gui_frame, gui_detections)
                    self.gui.update_camera_status(f"Analyzing: {len(detections)} objects detected")
                
                # STEP 2: Get ULTRASONIC distance (no print here - keep it clean)
                ultrasonic_description = self.ultrasonic.get_distance_description()
                
                # STEP 3: MERGE camera objects WITH ultrasonic distance
                # Extract object names from camera
                object_name = "Obstacle"  # Default if camera sees nothing
                
                if camera_description and "path clear" not in camera_description.lower():
                    # Camera detected something - use that as object name
                    # Extract first object from description (before "at" or ",")
                    if " at " in camera_description:
                        object_name = camera_description.split(" at ")[0]
                    elif "," in camera_description:
                        object_name = camera_description.split(",")[0]
                    else:
                        object_name = camera_description
                else:
                    # Camera sees nothing
                    object_name = "Path clear"
                
                # Build final description with camera object + ultrasonic distance
                if ultrasonic_description:
                    # Replace "Obstacle" in ultrasonic with camera object name
                    if "obstacle" in ultrasonic_description.lower():
                        # Extract distance part from ultrasonic
                        # e.g., "Obstacle close directly ahead, 0.6 meters" 
                        # -> "close directly ahead, 0.6 meters"
                        distance_part = ultrasonic_description.lower().replace("obstacle ", "")
                        description = f"{object_name}, {distance_part}"
                    else:
                        description = f"{object_name}. {ultrasonic_description}"
                    
                    print(f"[CAMERA] {camera_description if camera_description else 'Path clear'}")
                    print(f"[MERGED] {description}")
                else:
                    # No ultrasonic - just use camera
                    description = camera_description if camera_description else "No obstacles detected. Path appears clear."
                    print(f"[CAMERA ONLY] {description}")
                
                # Check for critical warnings from camera
                warnings = self.vision_detector.get_critical_warnings(detections)
                if warnings:
                    for warning in warnings:
                        self.speech.speak(warning, interrupt=True)
                        if self.gui:
                            self.gui.add_response(warning, is_system=True)
                
                # Speak the combined description
                self.speech.speak(description)
                
                # Update GUI with Lucy's response
                if self.gui:
                    self.gui.add_response(description)
                
                print(f"[FINAL OUTPUT] {description}")
                print("=" * 60)
                
                self.vision_state = VisionState.SPEAKING
                self.last_announcement_time = current_time
        
        elif self.vision_state == VisionState.SPEAKING:
            # Check for CRITICAL alerts even while speaking
            ultrasonic_alerts = self.ultrasonic.get_critical_alerts()
            if ultrasonic_alerts:
                for alert in ultrasonic_alerts:
                    if "very close" in alert.lower():
                        self.speech.speak("STOP! STOP! Obstacle very close!", interrupt=True)
                        print(f"[CRITICAL ALERT WHILE SPEAKING] {alert}")
                        self.vision_state = VisionState.WAITING
                        self.wait_start_time = time.time()
                        return
            
            # Check if speech is finished
            if not self.speech.is_speaking():
                print("[VISION] Speech finished, starting wait period...")
                self.vision_state = VisionState.WAITING
                self.wait_start_time = time.time()
        
        elif self.vision_state == VisionState.WAITING:
            # Small wait period before next capture
            if time.time() - self.wait_start_time >= 0.5:
                print("[VISION] Ready for next capture")
                self.vision_state = VisionState.READY_TO_CAPTURE
        
        # Check for button press (no wake word needed)
        if self.button.check_button_press():
            print("[BUTTON] Mode switch triggered")
            self.switch_to_conversation_mode()
    
    # ========================================================================
    # CONVERSATION MODE - Voice Assistant
    # ========================================================================
    
    def switch_to_conversation_mode(self):
        """Switch from vision mode to conversation mode"""
        print("\n" + "=" * 50)
        print("Switching to CONVERSATION mode")
        print("=" * 50)
        
        self.current_mode = Mode.CONVERSATION
        self.vision_state = VisionState.READY_TO_CAPTURE
        
        # Set camera and ultrasonic handlers for conversation
        self.conversation.set_handlers(camera=self.camera, ultrasonic=self.ultrasonic)
        
        self.speech.speak("Yes, how can I help you?", interrupt=True)
        if self.gui:
            self.gui.add_response("Yes, how can I help you?")
            self.gui.update_listening_status("Button pressed!")
        
        self.conversation.start_conversation()
    
    def run_conversation_mode(self):
        """Main loop for conversation mode - listen and respond to user"""
        
        # Reset interrupt flag
        self.interrupt_listening = False
        
        # Start button monitoring thread
        import threading
        
        def monitor_button():
            while self.current_mode == Mode.CONVERSATION and not self.interrupt_listening:
                if self.button.check_button_press():
                    print("[BUTTON] Interrupt! Returning to vision mode")
                    self.interrupt_listening = True
                    break
                time.sleep(0.05)
        
        button_thread = threading.Thread(target=monitor_button, daemon=True)
        button_thread.start()
        
        # Play high beep - START listening
        self.speech.play_beep(frequency=1000, duration=0.1)
        print("[CONVERSATION] 🎤 Listening...")
        
        # Update GUI
        if self.gui:
            self.gui.update_listening_status("Listening...")
        
        # Listen for user input with interrupt callback
        user_input = self.speech_recognizer.listen(
            timeout=config.LISTENING_TIMEOUT,
            interrupt_callback=lambda: self.interrupt_listening
        )
        
        # Play low beep - STOP listening
        self.speech.play_beep(frequency=600, duration=0.1)
        
        # Update GUI
        if self.gui:
            self.gui.update_listening_status("Processing...")
        
        # Check if interrupted by button
        if self.interrupt_listening:
            self.speech.speak("Returning to vision mode", interrupt=True)
            if self.gui:
                self.gui.add_response("Returning to vision mode", is_system=True)
            self.switch_to_vision_mode()
            return
        
        if user_input:
            print(f"[USER] {user_input}")
            
            # Update GUI with user speech
            if self.gui:
                self.gui.add_speech(user_input)
            
            # Check if interrupted by button
            if self.interrupt_listening:
                self.speech.speak("Returning to vision mode", interrupt=True)
                self.switch_to_vision_mode()
                return
            
            # Check for exit commands
            if any(word in user_input.lower() for word in ['goodbye', 'bye', 'exit', 'stop', 'vision mode']):
                self.speech.speak("Returning to vision mode", interrupt=True)
                self.switch_to_vision_mode()
                return
            
            # Check if user is asking about vision/what she sees
            vision_keywords = ['see', 'look', 'view', 'front', 'ahead', 'around', 'describe', 'what\'s', 'whats']
            is_vision_question = any(keyword in user_input.lower() for keyword in vision_keywords)
            
            if is_vision_question:
                # Take a picture and analyze it
                print("[CONVERSATION] Vision question detected - capturing image...")
                frame = self.camera.get_frame()
                
                if frame is not None:
                    # Get camera vision
                    detections = self.vision_detector.detect_objects(frame)
                    vision_description = self.vision_detector.generate_description(detections)
                    
                    # Get ultrasonic distance
                    ultrasonic_description = self.ultrasonic.get_distance_description()
                    
                    # Merge camera + ultrasonic
                    object_name = "Obstacle"
                    
                    if vision_description and "path clear" not in vision_description.lower():
                        if " at " in vision_description:
                            object_name = vision_description.split(" at ")[0]
                        elif "," in vision_description:
                            object_name = vision_description.split(",")[0]
                        else:
                            object_name = vision_description
                    else:
                        object_name = "Path clear"
                    
                    if ultrasonic_description:
                        if "obstacle" in ultrasonic_description.lower():
                            distance_part = ultrasonic_description.lower().replace("obstacle ", "")
                            full_vision = f"{object_name}, {distance_part}"
                        else:
                            full_vision = f"{object_name}. {ultrasonic_description}"
                    else:
                        full_vision = vision_description if vision_description else "I don't see any obstacles. The path appears clear."
                    
                    # Add vision context to the conversation
                    enhanced_input = f"{user_input}\n\nCurrent vision: {full_vision}"
                    print(f"[VISION] {full_vision}")
                    
                    # Get response from Groq with vision context
                    print("[CONVERSATION] Processing with Groq (with vision)...")
                    response = self.conversation.send_message(enhanced_input)
                else:
                    # Camera error - just answer normally
                    print("[CONVERSATION] Processing with Groq...")
                    response = self.conversation.send_message(user_input)
            else:
                # Normal conversation without vision
                print("[CONVERSATION] Processing with Groq...")
                response = self.conversation.send_message(user_input)
            
            print(f"[LUCY] {response}")
            
            # Update GUI with Lucy's response
            if self.gui:
                self.gui.add_response(response)
            
            # Check if interrupted by button
            if self.interrupt_listening:
                self.speech.speak("Returning to vision mode", interrupt=True)
                if self.gui:
                    self.gui.add_response("Returning to vision mode", is_system=True)
                self.switch_to_vision_mode()
                return
            
            # Speak response
            self.speech.speak(response, interrupt=True)
            
            # WAIT until she's done speaking before listening again
            print("[CONVERSATION] 🔊 Speaking... (waiting to finish)")
            if self.gui:
                self.gui.update_listening_status("Speaking...")
            
            self.speech.wait_until_done_speaking()
            print("[CONVERSATION] ✓ Done speaking")
            
            if self.gui:
                self.gui.update_listening_status("Ready")
            
            # Check if interrupted by button
            if self.interrupt_listening:
                self.switch_to_vision_mode()
                return
            
            # Check if max turns reached
            if self.conversation.get_turn_count() >= config.MAX_CONVERSATION_TURNS:
                self.speech.speak("Returning to vision mode", interrupt=True)
                self.switch_to_vision_mode()
        else:
            # Check if interrupted by button
            if self.interrupt_listening:
                self.speech.speak("Returning to vision mode", interrupt=True)
                self.switch_to_vision_mode()
                return
            
            # Timeout - return to vision mode
            print("[CONVERSATION] Timeout - returning to vision mode")
            self.speech.speak("Returning to vision mode", interrupt=True)
            self.switch_to_vision_mode()
    
    def switch_to_vision_mode(self):
        """Switch from conversation mode back to vision mode"""
        print("\n" + "=" * 50)
        print("Switching to VISION mode")
        print("=" * 50)
        
        self.current_mode = Mode.VISION
        self.vision_state = VisionState.READY_TO_CAPTURE
        self.conversation.end_conversation()
        
        # Set speech window to idle
        if self.gui:
            self.gui.update_listening_status("Idle - Vision Mode")
            self.gui.add_speech("Switched to vision mode", is_system=True)
        
        self.last_announcement_time = 0
    
    # ========================================================================
    # MAIN RUN LOOP
    # ========================================================================
    
    def run(self):
        """Start the application - runs GUI in main thread, Lucy logic in background"""
        self.running = True
        
        print("\n" + "=" * 50)
        print("Lucy Smart Glasses - Running")
        print(f"Mode: {self.current_mode.value.upper()}")
        print("Press button to switch modes")
        print("Press Ctrl+C to exit")
        print("=" * 50 + "\n")
        
        # If GUI is available, run Lucy's logic in background thread
        # and let GUI run in main thread (Tkinter requirement)
        if self.gui:
            def lucy_loop():
                try:
                    while self.running:
                        if self.current_mode == Mode.VISION:
                            self.run_vision_mode()
                            time.sleep(0.1)
                        
                        elif self.current_mode == Mode.CONVERSATION:
                            self.run_conversation_mode()
                
                except Exception as e:
                    print(f"Error in Lucy loop: {e}")
                    import traceback
                    traceback.print_exc()
            
            def gui_vision_loop():
                import cv2
                print("GUI camera thread started - live feed")
                
                while self.running:
                    try:
                        # Get frame
                        frame = self.camera.get_frame()
                        if frame is None:
                            time.sleep(0.05)
                            continue
                        
                        # Resize for GUI (640x480 for better quality but still fast)
                        gui_frame = cv2.resize(frame, (640, 480))
                        
                        # Show plain camera feed (no YOLO - faster!)
                        if self.current_mode == Mode.VISION:
                            self.gui.update_camera(gui_frame, None)
                            self.gui.update_camera_status("Vision Mode - Live Feed")
                        else:
                            # Conversation mode
                            self.gui.update_camera(gui_frame, None)
                            self.gui.update_camera_status("Conversation Mode - Camera Feed")
                        
                        # Faster update for smooth feed (~20 FPS)
                        time.sleep(0.05)
                        
                    except Exception as e:
                        print(f"Error in GUI camera loop: {e}")
                        time.sleep(0.5)
            
            def gui_ultrasonic_loop():
                print("GUI ultrasonic thread started - sensor data feed")
                
                while self.running:
                    try:
                        # Get sensor status
                        status = self.ultrasonic.get_sensor_status()
                        
                        if status and "sensors" in status:
                            # Extract sensor data
                            sensor1 = status["sensors"].get("sensor1", {})
                            sensor2 = status["sensors"].get("sensor2", {})
                            
                            # Get distances in cm
                            left_cm = sensor1.get("distance_cm")
                            right_cm = sensor2.get("distance_cm")
                            
                            # Calculate average if both sensors are active
                            avg_cm = None
                            if "averaged" in status:
                                avg_cm = status["averaged"].get("distance_cm")
                            
                            # Determine if should STOP (based on closest sensor)
                            should_stop = False
                            distances = []
                            if left_cm is not None and left_cm > 0:
                                distances.append(left_cm)
                            if right_cm is not None and right_cm > 0:
                                distances.append(right_cm)
                            
                            if distances:
                                min_distance = min(distances)
                                should_stop = min_distance <= config.DISTANCE_CLOSE
                            
                            # Update GUI
                            self.gui.update_ultrasonic(left_cm, right_cm, avg_cm, should_stop)
                        else:
                            # No sensor data - show empty
                            self.gui.update_ultrasonic(None, None, None, False)
                        
                        # Update every 0.2 seconds (5 Hz)
                        time.sleep(0.2)
                        
                    except Exception as e:
                        print(f"Error in GUI ultrasonic loop: {e}")
                        time.sleep(0.5)
            
            # Start Lucy's logic in background thread
            lucy_thread = threading.Thread(target=lucy_loop, daemon=True)
            lucy_thread.start()
            
            # Start GUI vision thread (continuous YOLO for display)
            gui_vision_thread = threading.Thread(target=gui_vision_loop, daemon=True)
            gui_vision_thread.start()
            
            # Start GUI ultrasonic thread (continuous sensor data display)
            gui_ultrasonic_thread = threading.Thread(target=gui_ultrasonic_loop, daemon=True)
            gui_ultrasonic_thread.start()
            
            # Set initial status for speech window (we start in vision mode)
            self.gui.update_listening_status("Idle - Vision Mode")
            
            print("GUI windows opened")
            print("Lucy is running in background...")
            
            # Run GUI in main thread (blocking)
            try:
                self.gui.run()
            except KeyboardInterrupt:
                print("\n\nShutting down...")
            finally:
                self.shutdown()
        
        else:
            # No GUI - run normally in main thread
            try:
                while self.running:
                    if self.current_mode == Mode.VISION:
                        self.run_vision_mode()
                        time.sleep(0.1)
                    
                    elif self.current_mode == Mode.CONVERSATION:
                        self.run_conversation_mode()
            
            except KeyboardInterrupt:
                print("\n\nShutting down...")
            
            finally:
                self.shutdown()
    
    def shutdown(self):
        """Clean up all resources before exiting"""
        print("Cleaning up...")
        self.running = False
        
        self.speech.stop()
        self.camera.stop()
        self.button.cleanup()
        self.ultrasonic.stop()
        
        print("Goodbye!")


# ============================================================================
# ENTRY POINT
# ============================================================================

def main():
    """Application entry point"""
    app = LucyGlasses()
    
    if not app.initialize():
        print("Initialization failed. Exiting.")
        sys.exit(1)
    
    app.run()


if __name__ == "__main__":
    main()
