from groq import Groq
from typing import List, Dict, Optional
import config
import base64
import cv2


class ConversationHandler:
    """Handles AI-powered conversations with vision and distance awareness"""
    
    def __init__(self):
        self.conversation_history: List[Dict] = []
        self.client = None
        self.camera = None
        self.ultrasonic = None
        
    def set_handlers(self, camera=None, ultrasonic=None):
        self.camera = camera
        self.ultrasonic = ultrasonic
        
    def initialize(self) -> bool:
        try:
            if not config.GROQ_API_KEY:
                print("ERROR: GROQ_API_KEY not set")
                return False
            
            self.client = Groq(api_key=config.GROQ_API_KEY)
            
            test_response = self.client.chat.completions.create(
                model=config.GROQ_MODEL,
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=5
            )
            
            print(f"Groq initialized")
            return True
            
        except:
            return False
    
    def describe_scene(self, frame) -> Optional[str]:
        try:
            if frame is None:
                return "I can't see anything right now - camera not available."
            
            # Encode frame to base64
            success, buffer = cv2.imencode('.jpg', frame)
            if not success:
                return "I'm having trouble processing the camera image."
            
            image_base64 = base64.b64encode(buffer).decode('utf-8')
            
            print("[GROQ VISION] Analyzing scene...")
            
            # Use Groq vision model
            response = self.client.chat.completions.create(
                model=config.GROQ_VISION_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Describe what you see in this image. Be concise and focus on important objects, people, and the environment. Keep it under 50 words."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=150,
                temperature=0.5
            )
            
            description = response.choices[0].message.content
            print(f"[GROQ VISION] {description}")
            return description
            
        except Exception as e:
            print(f"Error describing scene: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return f"I'm having trouble with the vision system: {str(e)}"
    
    def get_distance_info(self) -> str:
        try:
            if not self.ultrasonic:
                return "Distance sensors are not available."
            
            status = self.ultrasonic.get_sensor_status()
            
            if not status or "sensors" not in status:
                return "I can't read the distance sensors right now."
            
            # Get sensor data
            sensor1 = status["sensors"].get("sensor1", {})
            sensor2 = status["sensors"].get("sensor2", {})
            
            left_cm = sensor1.get("distance_cm")
            right_cm = sensor2.get("distance_cm")
            
            # Build distance response
            distances = []
            if left_cm and left_cm > 0:
                distances.append(left_cm)
            if right_cm and right_cm > 0:
                distances.append(right_cm)
            
            if not distances:
                return "I can't detect any distance right now."
            
            # Use average distance (not minimum)
            avg_distance = sum(distances) / len(distances)
            
            # Convert to meters if > 100cm
            if avg_distance > 100:
                return f"The average distance is about {avg_distance/100:.1f} meters away."
            else:
                return f"The average distance is {int(avg_distance)} centimeters away."
                
        except Exception as e:
            print(f"Error getting distance: {e}")
            return "I'm having trouble reading the distance sensors."
    
    def start_conversation(self):
        self.conversation_history = [
            {
                'role': 'system',
                'content': config.CONVERSATION_SYSTEM_PROMPT
            }
        ]
        print("Conversation started")
    
    def send_message(self, message: str) -> str:
        try:
            message_lower = message.lower()
            
            # Check for vision query keywords
            vision_keywords = ["what do you see", "what's in front", "describe", "look at", "what is"]
            is_vision_query = any(keyword in message_lower for keyword in vision_keywords)
            
            # Check for distance query keywords
            distance_keywords = ["how far", "distance", "how close", "how many meters", "centimeters"]
            is_distance_query = any(keyword in message_lower for keyword in distance_keywords)
            
            # Handle vision query
            if is_vision_query:
                print(f"[CONVERSATION] Vision query detected: '{message}'")
                
                if not self.camera:
                    print("[CONVERSATION] ERROR: Camera handler not set!")
                    return "The camera is not available right now."
                
                print("[CONVERSATION] Getting camera frame...")
                frame = self.camera.get_frame()
                
                if frame is None:
                    print("[CONVERSATION] ERROR: Camera returned None frame!")
                    return "I can't get an image from the camera right now."
                
                print(f"[CONVERSATION] Got frame: shape={frame.shape}, dtype={frame.dtype}")
                vision_response = self.describe_scene(frame)
                
                # If also asking for distance, add it
                if is_distance_query:
                    distance_response = self.get_distance_info()
                    return f"{vision_response} {distance_response}"
                
                return vision_response
            
            # Handle distance query only
            elif is_distance_query:
                return self.get_distance_info()
            
            # Regular conversation
            # Add user message to history
            self.conversation_history.append({
                'role': 'user',
                'content': message
            })
            
            # Limit conversation history to save tokens (keep only last 4 exchanges)
            if len(self.conversation_history) > 9:  # system + 4 exchanges (8 messages)
                # Keep system message and last 4 exchanges
                self.conversation_history = [self.conversation_history[0]] + self.conversation_history[-8:]
            
            print("[GROQ] Generating response...")
            
            # Get response from Groq (optimized for speed and cost)
            response = self.client.chat.completions.create(
                model=config.GROQ_MODEL,
                messages=self.conversation_history,
                max_tokens=100,  # Keep responses concise
                temperature=0.7,
            )
            
            assistant_message = response.choices[0].message.content
            
            # Add assistant response to history
            self.conversation_history.append({
                'role': 'assistant',
                'content': assistant_message
            })
            
            return assistant_message
            
        except Exception as e:
            print(f"Error getting response from Groq: {e}")
            return "I'm sorry, I'm having trouble processing that right now."
    
    def end_conversation(self):
        turn_count = len([msg for msg in self.conversation_history if msg['role'] == 'user'])
        print(f"Conversation ended after {turn_count} turns")
        self.conversation_history = []
    
    def get_turn_count(self) -> int:
        return len([msg for msg in self.conversation_history if msg['role'] == 'user'])
