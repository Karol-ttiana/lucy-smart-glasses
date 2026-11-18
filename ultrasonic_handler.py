"""
Ultrasonic sensor handler for obstacle detection via MQTT and Serial
Supports ESP32 ultrasonic sensors with dual communication modes
"""
import threading
import time
import queue
from typing import Optional, Dict, Tuple
import config


class UltrasonicHandler:
    """Handles ultrasonic sensor data via MQTT and/or Serial for obstacle detection"""
    
    def __init__(self):
        self.mqtt_client = None
        self.serial_conn = None
        self.running = False
        self.listener_thread = None
        self.serial_thread = None
        
        # Sensor data storage
        self.sensor_data = {
            "sensor1": {
                "distance": None, 
                "timestamp": 0, 
                "position": config.SENSOR_POSITIONS["sensor1"]["position"],
                "angle": config.SENSOR_POSITIONS["sensor1"]["horizontal_angle"],
                "zero_count": 0,  # Track consecutive zero readings
                "failed": False    # Mark sensor as failed
            },
            "sensor2": {
                "distance": None, 
                "timestamp": 0, 
                "position": config.SENSOR_POSITIONS["sensor2"]["position"],
                "angle": config.SENSOR_POSITIONS["sensor2"]["horizontal_angle"],
                "zero_count": 0,  # Track consecutive zero readings
                "failed": False    # Mark sensor as failed
            }
        }
        
        # Alert queue for critical warnings
        self.alert_queue = queue.Queue()
        
        # Last alert times to prevent spam
        self.last_alert_times = {
            "sensor1": 0,
            "sensor2": 0
        }
        
        self.enabled = config.USE_ULTRASONIC_SENSORS
        self.mqtt_connected = False
        self.serial_connected = False
        
        # Failure tracking
        self.MAX_ZERO_COUNT = 4  # Fail sensor after 4 consecutive zeros
        self.both_sensors_failed = False
        
        # Communication mode
        self.mode = config.ULTRASONIC_MODE.lower()  # "mqtt", "serial", or "both"
        
        # Track last data received time for each source
        self.last_mqtt_data_time = 0
        self.last_serial_data_time = 0
        self.DATA_TIMEOUT = 5.0  # Consider source dead if no data for 5 seconds
    
    def initialize(self) -> bool:
        """Initialize MQTT and/or Serial connections to ultrasonic sensors"""
        if not self.enabled:
            print("Ultrasonic sensors disabled in config")
            return True
        
        success = False
        
        # Initialize MQTT if needed
        if self.mode in ["mqtt", "both"]:
            if self._initialize_mqtt():
                success = True
            elif self.mode == "mqtt":
                print("⚠ MQTT mode requested but failed to initialize")
                return False
        
        # Initialize Serial if needed
        if self.mode in ["serial", "both"]:
            if self._initialize_serial():
                success = True
            elif self.mode == "serial":
                print("⚠ Serial mode requested but failed to initialize")
                return False
        
        if not success:
            print("⚠ Failed to initialize any ultrasonic communication method")
            self.enabled = False
            return True
        
        # Start data processing thread
        self.running = True
        self.listener_thread = threading.Thread(target=self._process_data, daemon=True)
        self.listener_thread.start()
        
        # Show initialization status
        print("✓ Ultrasonic sensor handler initialized")
        if self.mqtt_connected and self.serial_connected:
            print("  → Both MQTT and Serial initialized (will use whichever sends data)")
        elif self.mqtt_connected:
            print("  → MQTT initialized (waiting for data...)")
        elif self.serial_connected:
            print("  → Serial initialized (waiting for data...)")
        
        return True
    
    def get_active_source(self) -> str:
        """Determine which data source is currently active"""
        current_time = time.time()
        
        mqtt_active = (current_time - self.last_mqtt_data_time) < self.DATA_TIMEOUT
        serial_active = (current_time - self.last_serial_data_time) < self.DATA_TIMEOUT
        
        if mqtt_active and serial_active:
            return "BOTH"
        elif mqtt_active:
            return "MQTT"
        elif serial_active:
            return "SERIAL"
        else:
            return "NONE"
    
    def _initialize_mqtt(self) -> bool:
        """Initialize MQTT connection"""
        try:
            import paho.mqtt.client as mqtt
            
            # Create MQTT client
            self.mqtt_client = mqtt.Client(client_id="lucy_glasses", clean_session=True)
            
            # Set up callbacks
            self.mqtt_client.on_connect = self._on_mqtt_connect
            self.mqtt_client.on_message = self._on_mqtt_message
            self.mqtt_client.on_disconnect = self._on_mqtt_disconnect
            
            # Connect to broker
            print(f"Connecting to MQTT broker {config.MQTT_BROKER}:{config.MQTT_PORT}...")
            self.mqtt_client.connect(config.MQTT_BROKER, config.MQTT_PORT, 60)
            
            # Start MQTT loop
            self.mqtt_client.loop_start()
            
            print("✓ MQTT connection initialized")
            return True
            
        except ImportError:
            print("⚠ paho-mqtt not installed - MQTT disabled")
            print("  Install with: pip install paho-mqtt")
            return False
        except Exception as e:
            print(f"⚠ Failed to initialize MQTT: {e}")
            return False
    
    def _initialize_serial(self) -> bool:
        """Initialize Serial connection"""
        try:
            import serial
            
            # Try to open serial port
            print(f"Opening serial port {config.SERIAL_PORT} at {config.SERIAL_BAUD_RATE} baud...")
            self.serial_conn = serial.Serial(
                port=config.SERIAL_PORT,
                baudrate=config.SERIAL_BAUD_RATE,
                timeout=config.SERIAL_TIMEOUT
            )
            
            # Wait for connection to stabilize
            time.sleep(2)
            
            # Clear any initial garbage data
            self.serial_conn.reset_input_buffer()
            
            self.serial_connected = True
            
            # Start serial reading thread
            self.serial_thread = threading.Thread(target=self._read_serial, daemon=True)
            self.serial_thread.start()
            
            print("✓ Serial connection initialized")
            return True
            
        except ImportError:
            print("⚠ pyserial not installed - Serial disabled")
            print("  Install with: pip install pyserial")
            return False
        except Exception as e:
            print(f"⚠ Failed to initialize Serial: {e}")
            print(f"  Make sure ESP32 is connected to {config.SERIAL_PORT}")
            return False
    
    def _read_serial(self):
        """Background thread to read serial data"""
        print("[SERIAL] Serial reading thread started")
        while self.running and self.serial_connected:
            try:
                if self.serial_conn and self.serial_conn.in_waiting > 0:
                    line = self.serial_conn.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        self._process_serial_line(line)
                else:
                    time.sleep(0.01)  # Small delay when no data
            except UnicodeDecodeError as e:
                if self.running:
                    print(f"[SERIAL] Decode error: {e}")
            except Exception as e:
                if self.running:
                    print(f"[SERIAL] Read error: {e}")
                    time.sleep(0.5)
    
    def _process_serial_line(self, line: str):
        """Process a line of serial data
        Expected format: "S1:123" or "S2:456" (sensor_id:distance_cm)
        """
        try:
            # Debug: show raw line
            print(f"[SERIAL DEBUG] Received: '{line}'")
            
            # Parse format: "S1:123" or "S2:456"
            if ':' not in line:
                print(f"[SERIAL DEBUG] Skipping - no colon in line")
                return
            
            parts = line.split(':')
            if len(parts) != 2:
                print(f"[SERIAL DEBUG] Skipping - wrong number of parts: {len(parts)}")
                return
            
            sensor_prefix = parts[0].strip().upper()
            distance = int(parts[1].strip())
            
            print(f"[SERIAL DEBUG] Parsed: sensor={sensor_prefix}, distance={distance}")
            
            # Map S1 -> sensor1, S2 -> sensor2
            sensor_id = None
            if sensor_prefix == "S1":
                sensor_id = "sensor1"
            elif sensor_prefix == "S2":
                sensor_id = "sensor2"
            else:
                print(f"[SERIAL DEBUG] Unknown sensor prefix: {sensor_prefix}")
                return
            
            timestamp = time.time()
            
            # Update sensor data (same logic as MQTT)
            self._update_sensor_data(sensor_id, distance, timestamp, source="SERIAL")
            
        except ValueError as e:
            print(f"[SERIAL] Error parsing serial data: '{line}' - {e}")
        except Exception as e:
            print(f"[SERIAL] Error processing serial data: {e}")
    
    def _on_mqtt_connect(self, client, userdata, flags, rc):
        """Callback for MQTT connection"""
        if rc == 0:
            print("✓ Connected to MQTT broker")
            self.mqtt_connected = True
            
            # Subscribe to ultrasonic sensor topics
            for sensor_id, topic in config.MQTT_TOPICS.items():
                client.subscribe(topic)
                print(f"  Subscribed to {topic} ({sensor_id}: {self.sensor_data[sensor_id]['position']})")
        else:
            print(f"✗ Failed to connect to MQTT broker (code {rc})")
            self.mqtt_connected = False
    
    def _on_mqtt_disconnect(self, client, userdata, rc):
        """Callback for MQTT disconnection"""
        self.mqtt_connected = False
        if rc != 0:
            print("⚠ Unexpected MQTT disconnection - will try to reconnect")
    
    def _on_mqtt_message(self, client, userdata, msg):
        """Process incoming MQTT sensor data"""
        try:
            # Decode message - expecting distance in centimeters as integer
            distance = int(msg.payload.decode().strip())
            topic = msg.topic
            timestamp = time.time()
            
            # Find which sensor this is
            sensor_id = None
            for sid, stopic in config.MQTT_TOPICS.items():
                if stopic == topic:
                    sensor_id = sid
                    break
            
            if sensor_id:
                self._update_sensor_data(sensor_id, distance, timestamp, source="MQTT")
                
        except ValueError as e:
            print(f"Error parsing MQTT data: {msg.payload} - {e}")
        except Exception as e:
            print(f"Error processing MQTT data: {e}")
    
    def _update_sensor_data(self, sensor_id: str, distance: int, timestamp: float, source: str):
        """Update sensor data (common logic for both MQTT and Serial)"""
        
        # Track last data time for this source
        if source == "MQTT":
            self.last_mqtt_data_time = timestamp
        elif source == "SERIAL":
            self.last_serial_data_time = timestamp
        
        # Check for zero readings
        if distance == 0:
            self.sensor_data[sensor_id]["zero_count"] += 1
            print(f"[{source}] {sensor_id}: ZERO reading ({self.sensor_data[sensor_id]['zero_count']}/{self.MAX_ZERO_COUNT})")
            
            # Check if sensor should be marked as failed
            if self.sensor_data[sensor_id]["zero_count"] >= self.MAX_ZERO_COUNT:
                if not self.sensor_data[sensor_id]["failed"]:
                    self.sensor_data[sensor_id]["failed"] = True
                    print(f"[{source}] ⚠️ {sensor_id} FAILED after {self.MAX_ZERO_COUNT} zero readings!")
                    
                    # Check if both sensors failed
                    if self.sensor_data["sensor1"]["failed"] and self.sensor_data["sensor2"]["failed"]:
                        self.both_sensors_failed = True
                        print(f"[{source}] ⚠️⚠️ BOTH SENSORS FAILED - Switching to camera only!")
        else:
            # Valid reading - reset zero count and unfail sensor
            self.sensor_data[sensor_id]["zero_count"] = 0
            if self.sensor_data[sensor_id]["failed"]:
                self.sensor_data[sensor_id]["failed"] = False
                print(f"[{source}] ✓ {sensor_id} RECOVERED!")
                
                # Check if both sensors are now working
                if not self.sensor_data["sensor1"]["failed"] and not self.sensor_data["sensor2"]["failed"]:
                    self.both_sensors_failed = False
                    print(f"[{source}] ✓ Both sensors operational again!")
        
        # Update sensor data
        self.sensor_data[sensor_id]["distance"] = distance
        self.sensor_data[sensor_id]["timestamp"] = timestamp
        
        # Debug output
        position = self.sensor_data[sensor_id]["position"]
        print(f"[{source}] {sensor_id} ({position}): {distance}cm")
        
        # Check for critical proximity alerts (only if not failed)
        if not self.sensor_data[sensor_id]["failed"] and distance > 0:
            self._check_proximity_alert(sensor_id, distance, timestamp)
    
    def _check_proximity_alert(self, sensor_id: str, distance: int, timestamp: float):
        """Check if distance requires immediate alert"""
        # Avoid alert spam - minimum 2 seconds between alerts per sensor
        if timestamp - self.last_alert_times[sensor_id] < 2.0:
            return
        
        position = self.sensor_data[sensor_id]["position"]
        
        # Critical proximity alerts
        if distance <= config.DISTANCE_VERY_CLOSE:
            alert = f"Warning! Obstacle very close on the {position}, {distance} centimeters"
            self.alert_queue.put(alert)
            self.last_alert_times[sensor_id] = timestamp
            
        elif distance <= config.DISTANCE_CLOSE:
            alert = f"Obstacle close on the {position}, {distance} centimeters"
            self.alert_queue.put(alert)
            self.last_alert_times[sensor_id] = timestamp
    
    def _process_data(self):
        """Background thread to process sensor data"""
        while self.running:
            try:
                time.sleep(0.1)  # 10Hz processing rate
                
                # Clean old data (older than sensor timeout)
                current_time = time.time()
                for sensor_id in self.sensor_data:
                    if (current_time - self.sensor_data[sensor_id]["timestamp"]) > config.SENSOR_DATA_TIMEOUT:
                        self.sensor_data[sensor_id]["distance"] = None
                        
            except Exception as e:
                if self.running:
                    print(f"Error in ultrasonic data processing: {e}")
    
    def get_critical_alerts(self) -> list:
        """Get any critical proximity alerts"""
        alerts = []
        while not self.alert_queue.empty():
            try:
                alerts.append(self.alert_queue.get_nowait())
            except queue.Empty:
                break
        return alerts
    
    def get_averaged_distance(self) -> Optional[Tuple[int, str]]:
        """
        Get averaged distance from both sensors (for center/ahead detection)
        
        Returns:
            Tuple of (average_distance_cm, "center") or None if no valid data
        """
        if not self.enabled or not config.USE_SENSOR_AVERAGING:
            return None
        
        current_time = time.time()
        
        # Get both sensor readings
        sensor1_distance = self.sensor_data["sensor1"]["distance"]
        sensor1_timestamp = self.sensor_data["sensor1"]["timestamp"]
        sensor1_failed = self.sensor_data["sensor1"]["failed"]
        
        sensor2_distance = self.sensor_data["sensor2"]["distance"]
        sensor2_timestamp = self.sensor_data["sensor2"]["timestamp"]
        sensor2_failed = self.sensor_data["sensor2"]["failed"]
        
        # Check if both sensors have fresh data and are not failed
        sensor1_valid = (sensor1_distance is not None and 
                        sensor1_distance > 0 and
                        not sensor1_failed and
                        (current_time - sensor1_timestamp) <= config.SENSOR_DATA_TIMEOUT)
        sensor2_valid = (sensor2_distance is not None and 
                        sensor2_distance > 0 and
                        not sensor2_failed and
                        (current_time - sensor2_timestamp) <= config.SENSOR_DATA_TIMEOUT)
        
        if sensor1_valid and sensor2_valid:
            # Both sensors have data - calculate weighted average
            # Give more weight to the closer sensor (more critical)
            if abs(sensor1_distance - sensor2_distance) < 50:  # Similar distances
                avg_distance = int((sensor1_distance + sensor2_distance) / 2)
            else:
                # Different distances - weight toward closer one
                min_dist = min(sensor1_distance, sensor2_distance)
                max_dist = max(sensor1_distance, sensor2_distance)
                avg_distance = int(min_dist * 0.7 + max_dist * 0.3)
            
            print(f"[ULTRASONIC AVG] sensor1={sensor1_distance}cm, sensor2={sensor2_distance}cm → AVG={avg_distance}cm")
            return (avg_distance, "center")
        
        return None
    
    def get_distance_description(self) -> Optional[str]:
        """
        Get current distance description with intelligent fallback:
        - Both sensors work → averaged distance (print AVG to terminal)
        - One sensor fails 4+ times → use other sensor
        - Both sensors fail 4+ times → None (camera only)
        """
        if not self.enabled:
            return None
        
        # Check which data source is active
        active_source = self.get_active_source()
        if active_source == "NONE":
            print("[ULTRASONIC] ⚠️ NO DATA from any source!")
            if self.mqtt_connected:
                print("  → MQTT connected but NOT receiving data")
            if self.serial_connected:
                print("  → Serial connected but NOT receiving data")
            print("  → Using CAMERA ONLY")
            return None
        else:
            print(f"[ULTRASONIC] Active source: {active_source}")
        
        # If both sensors failed, return None (camera only)
        if self.both_sensors_failed:
            print("[ULTRASONIC] Both sensors failed → Using CAMERA ONLY")
            return None
        
        current_time = time.time()
        
        # Check which sensors have fresh, valid data
        sensor1_data = self.sensor_data["sensor1"]
        sensor2_data = self.sensor_data["sensor2"]
        
        sensor1_valid = (sensor1_data["distance"] is not None and 
                         sensor1_data["distance"] > 0 and
                         not sensor1_data["failed"] and
                         (current_time - sensor1_data["timestamp"]) <= config.SENSOR_DATA_TIMEOUT)
        
        sensor2_valid = (sensor2_data["distance"] is not None and 
                         sensor2_data["distance"] > 0 and
                         not sensor2_data["failed"] and
                         (current_time - sensor2_data["timestamp"]) <= config.SENSOR_DATA_TIMEOUT)
        
        # CASE 1: Both sensors work → Use averaged distance
        if sensor1_valid and sensor2_valid and config.USE_SENSOR_AVERAGING:
            avg_result = self.get_averaged_distance()
            if avg_result:
                distance, position = avg_result
                distance_m = distance / 100.0
                
                print(f"[ULTRASONIC MODE] AVERAGING (both sensors working)")
                
                # Categorize distance
                if distance <= config.DISTANCE_VERY_CLOSE:
                    return f"Obstacle very close directly ahead, {distance_m:.1f} meters"
                elif distance <= config.DISTANCE_CLOSE:
                    return f"Obstacle close directly ahead, {distance_m:.1f} meters"
                elif distance <= config.DISTANCE_MEDIUM:
                    return f"Obstacle at {distance_m:.1f} meters directly ahead"
                elif distance <= config.DISTANCE_FAR:
                    return f"Obstacle at {distance_m:.1f} meters ahead"
        
        # CASE 2: Only sensor1 works (sensor2 failed)
        if sensor1_valid and not sensor2_valid:
            distance = sensor1_data["distance"]
            position = sensor1_data["position"]
            distance_m = distance / 100.0
            
            print(f"[ULTRASONIC MODE] SENSOR1 ONLY ({position}) - sensor2 failed")
            
            if distance <= config.DISTANCE_VERY_CLOSE:
                return f"Obstacle very close on the {position}, {distance_m:.1f} meters"
            elif distance <= config.DISTANCE_CLOSE:
                return f"Obstacle close on the {position}, {distance_m:.1f} meters"
            elif distance <= config.DISTANCE_MEDIUM:
                return f"Obstacle at {distance_m:.1f} meters on the {position}"
            elif distance <= config.DISTANCE_FAR:
                return f"Obstacle at {distance_m:.1f} meters on the {position}"
        
        # CASE 3: Only sensor2 works (sensor1 failed)
        if sensor2_valid and not sensor1_valid:
            distance = sensor2_data["distance"]
            position = sensor2_data["position"]
            distance_m = distance / 100.0
            
            print(f"[ULTRASONIC MODE] SENSOR2 ONLY ({position}) - sensor1 failed")
            
            if distance <= config.DISTANCE_VERY_CLOSE:
                return f"Obstacle very close on the {position}, {distance_m:.1f} meters"
            elif distance <= config.DISTANCE_CLOSE:
                return f"Obstacle close on the {position}, {distance_m:.1f} meters"
            elif distance <= config.DISTANCE_MEDIUM:
                return f"Obstacle at {distance_m:.1f} meters on the {position}"
            elif distance <= config.DISTANCE_FAR:
                return f"Obstacle at {distance_m:.1f} meters on the {position}"
        
        # CASE 4: No valid sensors → Return None (camera will be used)
        print("[ULTRASONIC MODE] No valid sensor data → Using CAMERA")
        return None
    
    def get_sensor_status(self) -> Dict:
        """Get current status of all sensors"""
        if not self.enabled:
            return {}
        
        status = {
            "mqtt_connected": self.mqtt_connected,
            "serial_connected": self.serial_connected,
            "mode": self.mode,
            "averaging_enabled": config.USE_SENSOR_AVERAGING,
            "both_sensors_failed": self.both_sensors_failed,
            "sensors": {}
        }
        
        current_time = time.time()
        
        for sensor_id, data in self.sensor_data.items():
            distance = data["distance"]
            timestamp = data["timestamp"]
            position = data["position"]
            angle = data["angle"]
            zero_count = data["zero_count"]
            failed = data["failed"]
            
            # Check if sensor is active
            is_active = (distance is not None and 
                        distance > 0 and
                        not failed and
                        (current_time - timestamp) <= config.SENSOR_DATA_TIMEOUT)
            
            status["sensors"][sensor_id] = {
                "position": position,
                "angle": angle,
                "distance_cm": distance,
                "distance_m": distance / 100.0 if distance else None,
                "active": is_active,
                "failed": failed,
                "zero_count": zero_count,
                "age": current_time - timestamp if timestamp > 0 else None
            }
        
        # Add averaged distance if available
        if config.USE_SENSOR_AVERAGING and not self.both_sensors_failed:
            avg_result = self.get_averaged_distance()
            if avg_result:
                status["averaged"] = {
                    "distance_cm": avg_result[0],
                    "distance_m": avg_result[0] / 100.0,
                    "position": avg_result[1]
                }
        
        return status
    
    def stop(self):
        """Stop ultrasonic sensor monitoring"""
        if not self.enabled:
            return
        
        self.running = False
        
        if self.listener_thread:
            self.listener_thread.join(timeout=2.0)
        
        if self.serial_thread:
            self.serial_thread.join(timeout=2.0)
        
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        
        if self.serial_conn:
            self.serial_conn.close()
        
        print("Ultrasonic sensor handler stopped")
