import cv2
import threading
import time
from typing import Optional
import numpy as np
import config


class CameraHandler:
    """Handles camera initialization and frame capture"""
    
    def __init__(self, camera_index: int = config.CAMERA_INDEX):
        self.camera_index = camera_index
        self.cap = None
        self.current_frame = None
        self.running = False
        self.lock = threading.Lock()
        self.capture_thread = None
        self.use_pi_camera = config.USE_PI_CAMERA
        self.picam2 = None
        
    def start(self) -> bool:
        try:
            if self.use_pi_camera:
                return self._start_pi_camera()
            else:
                return self._start_usb_camera()
                
        except Exception as e:
            print(f"Error starting camera: {e}")
            return False
    
    def _start_pi_camera(self) -> bool:
        try:
            from picamera2 import Picamera2
            
            self.picam2 = Picamera2()
            camera_config = self.picam2.create_preview_configuration(
                main={"size": (config.CAMERA_WIDTH, config.CAMERA_HEIGHT), "format": "RGB888"}
            )
            self.picam2.configure(camera_config)
            self.picam2.start()
            
            self.running = True
            self.capture_thread = threading.Thread(target=self._pi_camera_loop, daemon=True)
            self.capture_thread.start()
            
            print("Pi Camera started")
            return True
            
        except ImportError:
            self.use_pi_camera = False
            return self._start_usb_camera()
        except:
            return False
    
    def _start_usb_camera(self) -> bool:
        try:
            self.cap = cv2.VideoCapture(self.camera_index)
            if not self.cap.isOpened():
                print(f"Error: Could not open camera {self.camera_index}")
                return False
            
            # Set camera properties
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)
            self.cap.set(cv2.CAP_PROP_FPS, config.CAMERA_FPS)
            
            self.running = True
            self.capture_thread = threading.Thread(target=self._usb_camera_loop, daemon=True)
            self.capture_thread.start()
            
            print("USB Camera started")
            return True
            
        except:
            return False
    
    def _pi_camera_loop(self):
        while self.running:
            try:
                frame = self.picam2.capture_array()
                # Convert RGB to BGR for OpenCV compatibility
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                
                with self.lock:
                    self.current_frame = frame
                    
                time.sleep(1.0 / config.CAMERA_FPS)
            except Exception as e:
                print(f"Error in Pi camera loop: {e}")
                time.sleep(0.1)
    
    def _usb_camera_loop(self):
        while self.running:
            ret, frame = self.cap.read()
            if ret:
                with self.lock:
                    self.current_frame = frame
            time.sleep(1.0 / config.CAMERA_FPS)
    
    def get_frame(self) -> Optional[np.ndarray]:
        with self.lock:
            return self.current_frame.copy() if self.current_frame is not None else None
    
    def stop(self):
        self.running = False
        if self.capture_thread:
            self.capture_thread.join(timeout=2.0)
        
        if self.use_pi_camera and self.picam2:
            self.picam2.stop()
        elif self.cap:
            self.cap.release()
            
        print("Camera stopped")
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
