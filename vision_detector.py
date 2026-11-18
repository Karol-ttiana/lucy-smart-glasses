from ultralytics import YOLO
import numpy as np
from typing import List, Dict, Optional
import config


class VisionDetector:
    """Handles object detection and scene description for navigation assistance"""
    
    # Object categories for better prioritization
    OBSTACLE_OBJECTS = {'chair', 'couch', 'table', 'bench', 'bed', 'desk'}
    PEOPLE_OBJECTS = {'person'}
    NAVIGATION_OBJECTS = {'door', 'stairs', 'escalator', 'elevator'}
    VEHICLE_OBJECTS = {'car', 'truck', 'bus', 'bicycle', 'motorcycle', 'train'}
    HAZARD_OBJECTS = {'fire hydrant', 'stop sign', 'traffic light', 'parking meter'}
    
    def __init__(self):
        self.model = None
        self.class_names = None
        self.ultrasonic_handler = None
        
    def initialize(self, ultrasonic_handler=None) -> bool:
        try:
            print("Loading YOLOv8n model (optimized for Raspberry Pi)...")
            self.model = YOLO(config.YOLO_MODEL)
            
            # Get class names
            self.class_names = self.model.names
            
            # Store reference to ultrasonic handler for distance fusion
            self.ultrasonic_handler = ultrasonic_handler
            
            print(f"YOLOv8n model loaded successfully with {len(self.class_names)} classes")
            return True
            
        except Exception as e:
            print(f"Error initializing YOLO model: {e}")
            return False
    
    def detect_objects(self, frame: np.ndarray) -> List[Dict]:
        if self.model is None:
            return []
        
        try:
            # Run inference with optimizations for Raspberry Pi
            results = self.model(
                frame,
                conf=config.YOLO_CONFIDENCE_THRESHOLD,
                verbose=False,
                imgsz=config.YOLO_IMG_SIZE,
                half=config.YOLO_HALF_PRECISION
            )
            
            detections = []
            
            for result in results:
                boxes = result.boxes
                
                for box in boxes:
                    # Get box coordinates
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    
                    # Get confidence and class
                    confidence = float(box.conf[0])
                    class_id = int(box.cls[0])
                    class_name = self.class_names[class_id]
                    
                    # Estimate relative distance based on bounding box size
                    bbox_area = (x2 - x1) * (y2 - y1)
                    frame_area = frame.shape[0] * frame.shape[1]
                    relative_size = bbox_area / frame_area
                    
                    # Determine position (left, center, right)
                    center_x = (x1 + x2) / 2
                    frame_width = frame.shape[1]
                    
                    # More precise position detection
                    if center_x < frame_width * 0.25:
                        position = "on your left"
                        in_path = False
                    elif center_x < frame_width * 0.4:
                        position = "slightly left"
                        in_path = True
                    elif center_x < frame_width * 0.6:
                        position = "directly ahead"
                        in_path = True
                    elif center_x < frame_width * 0.75:
                        position = "slightly right"
                        in_path = True
                    else:
                        position = "on your right"
                        in_path = False
                    
                    # Get ultrasonic distance for this position
                    ultrasonic_distance_cm = None
                    ultrasonic_distance_m = None
                    
                    if self.ultrasonic_handler:
                        ultrasonic_distance_cm = self.ultrasonic_handler.get_distance_for_position(position)
                        if ultrasonic_distance_cm:
                            ultrasonic_distance_m = ultrasonic_distance_cm / 100.0
                    
                    # Determine distance category with ultrasonic fusion
                    if ultrasonic_distance_cm is not None:
                        # Use ultrasonic for accurate distance
                        if ultrasonic_distance_cm <= config.DISTANCE_VERY_CLOSE:
                            distance = f"at {ultrasonic_distance_m:.1f} meters"
                            distance_category = 1  # Critical
                        elif ultrasonic_distance_cm <= config.DISTANCE_CLOSE:
                            distance = f"at {ultrasonic_distance_m:.1f} meters"
                            distance_category = 2  # Important
                        elif ultrasonic_distance_cm <= config.DISTANCE_MEDIUM:
                            distance = f"at {ultrasonic_distance_m:.1f} meters"
                            distance_category = 3  # Normal
                        else:
                            distance = f"at {ultrasonic_distance_m:.1f} meters"
                            distance_category = 4  # Far
                    else:
                        # Fallback to camera-based estimation
                        if relative_size > 0.3:
                            distance = "very close"
                            distance_category = 1  # Critical
                        elif relative_size > 0.15:
                            distance = "close"
                            distance_category = 2  # Important
                        elif relative_size > 0.05:
                            distance = "medium distance"
                            distance_category = 3  # Normal
                        else:
                            distance = "far"
                            distance_category = 4  # Background
                    
                    # Calculate importance score
                    importance = self._calculate_importance(
                        class_name, distance_category, in_path, relative_size
                    )
                    
                    detections.append({
                        'class': class_name,
                        'confidence': confidence,
                        'bbox': (int(x1), int(y1), int(x2), int(y2)),
                        'distance': distance,
                        'distance_category': distance_category,
                        'ultrasonic_distance_cm': ultrasonic_distance_cm,
                        'ultrasonic_distance_m': ultrasonic_distance_m,
                        'position': position,
                        'in_path': in_path,
                        'relative_size': relative_size,
                        'importance': importance
                    })
            
            return detections
            
        except Exception as e:
            print(f"Error during object detection: {e}")
            return []
    
    def _calculate_importance(self, class_name: str, distance_category: int, 
                             in_path: bool, relative_size: float) -> float:
        score = 0.0
        
        # Distance is most important (closer = higher score)
        score += (5 - distance_category) * 30  # 30-120 points
        
        # In-path objects are critical
        if in_path:
            score += 50
        
        # Object type importance
        if class_name in self.PEOPLE_OBJECTS:
            score += 40  # People are very important
        elif class_name in self.VEHICLE_OBJECTS:
            score += 45  # Vehicles are critical
        elif class_name in self.NAVIGATION_OBJECTS:
            score += 35  # Navigation aids are important
        elif class_name in self.OBSTACLE_OBJECTS:
            score += 25  # Obstacles matter
        elif class_name in self.HAZARD_OBJECTS:
            score += 30
        
        # Size factor (larger = more important)
        score += relative_size * 20
        
        return score
    
    def generate_description(self, detections: List[Dict]) -> str:
        if not detections:
            return "Path clear"
        
        # Sort by importance score (most important first)
        sorted_detections = sorted(detections, key=lambda x: x['importance'], reverse=True)
        
        # Filter based on settings
        if config.ANNOUNCE_ONLY_PATH_OBSTACLES:
            sorted_detections = [d for d in sorted_detections if d['in_path']]
        
        # Limit to max objects
        important_objects = sorted_detections[:config.MAX_OBJECTS_TO_ANNOUNCE]
        
        if not important_objects:
            return "Path clear"
        
        # Build concise description with distances
        descriptions = []
        
        for obj in important_objects:
            class_name = obj['class']
            position = obj['position']
            distance = obj['distance']
            
            # Create natural description with accurate distance
            if obj['in_path']:
                desc = f"{class_name} {position} {distance}"
            else:
                desc = f"{class_name} {position}"
            
            descriptions.append(desc)
        
        # Create final announcement based on verbosity
        if config.VISION_VERBOSITY == "concise":
            # Ultra-concise: just the most important
            if len(descriptions) == 1:
                return descriptions[0].capitalize()
            elif len(descriptions) >= 2:
                return f"{descriptions[0].capitalize()}, {descriptions[1]}"
        
        elif config.VISION_VERBOSITY == "detailed":
            # More detailed
            if len(descriptions) == 1:
                return descriptions[0].capitalize()
            elif len(descriptions) == 2:
                return f"{descriptions[0].capitalize()}, and {descriptions[1]}"
            else:
                return f"{descriptions[0].capitalize()}, {descriptions[1]}, and {descriptions[2]}"
        
        else:  # normal
            if len(descriptions) == 1:
                return descriptions[0].capitalize()
            elif len(descriptions) == 2:
                return f"{descriptions[0].capitalize()}, {descriptions[1]}"
            else:
                return f"{descriptions[0].capitalize()}, {descriptions[1]}, and {descriptions[2]}"
    
    def get_critical_warnings(self, detections: List[Dict]) -> List[str]:
        warnings = []
        
        for obj in detections:
            if obj['distance_category'] == 1 and obj['in_path']:  # Very close and in path
                if obj['ultrasonic_distance_m']:
                    warnings.append(f"Stop! {obj['class']} very close {obj['position']} at {obj['ultrasonic_distance_m']:.1f} meters")
                else:
                    warnings.append(f"Stop! {obj['class']} very close {obj['position']}")
        
        return warnings
