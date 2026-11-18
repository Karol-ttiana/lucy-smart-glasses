import threading
import time
import config


class ButtonHandler:
    """Handles GPIO button press detection with debouncing"""
    
    def __init__(self):
        self.line_request = None
        self.button_pressed = False
        self.enabled = config.USE_GPIO_BUTTON
        self.running = False
        self.monitor_thread = None
        
    def initialize(self) -> bool:
        if not self.enabled:
            print("GPIO button disabled in config")
            return True
        
        try:
            import gpiod
            from gpiod.line import Direction, Edge, Bias
            
            # Try different chip paths for Raspberry Pi 5
            chip_paths = ['/dev/gpiochip4', '/dev/gpiochip0']
            chip_path = None
            
            for path in chip_paths:
                try:
                    # Test if chip exists
                    with gpiod.Chip(path) as test_chip:
                        chip_path = path
                        break
                except (FileNotFoundError, OSError):
                    continue
            
            if not chip_path:
                raise Exception("No GPIO chip found")
            
            # Request the GPIO line with gpiod 2.x API
            self.line_request = gpiod.request_lines(
                chip_path,
                consumer="lucy-button",
                config={
                    config.GPIO_BUTTON_PIN: gpiod.LineSettings(
                        direction=Direction.INPUT,
                        edge_detection=Edge.FALLING,
                        bias=Bias.PULL_UP
                    )
                }
            )
            
            
            self.running = True
            self.monitor_thread = threading.Thread(target=self._monitor_button, daemon=True)
            self.monitor_thread.start()
            
            print(f"GPIO button initialized on pin {config.GPIO_BUTTON_PIN}")
            return True
            
        except:
            self.enabled = False
            return True
    
    def _monitor_button(self):
        try:
            last_press_time = 0
            
            while self.running:
                # Wait for edge events with timeout
                if self.line_request.wait_edge_events(timeout=0.1):  # 100ms timeout
                    events = self.line_request.read_edge_events()
                    
                    for event in events:
                        # Check debounce time
                        current_time = time.time()
                        if (current_time - last_press_time) * 1000 > config.GPIO_BUTTON_BOUNCE_TIME:
                            print(f"[BUTTON] Button pressed on GPIO {config.GPIO_BUTTON_PIN}")
                            self.button_pressed = True
                            last_press_time = current_time
                            
        except Exception as e:
            if self.running:
                print(f"Error in button monitor: {e}")
    
    def check_button_press(self) -> bool:
        if self.button_pressed:
            self.button_pressed = False
            return True
        return False
    
    def cleanup(self):
        self.running = False
        
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1.0)
        
        if self.line_request:
            try:
                self.line_request.release()
            except:
                pass
        
        if self.enabled:
            print("GPIO button cleaned up")
    
    def __del__(self):
        self.cleanup()
