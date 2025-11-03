from pynput import keyboard, mouse
from datetime import datetime
import threading

class ActivityLogger:
    def __init__(self, log_file='activity_log.txt'):
        self.log_file = log_file
        self.is_logging = False
        self.left_click_count = 0
        self.right_click_count = 0
        self.backspace_count = 0
        self.scroll_up_count = 0
        self.scroll_down_count = 0
        self.scroll_left_count = 0
        self.scroll_right_count = 0
        self.file_handle = None
        self.first_key_time = None
        self.last_key_time = None
        self.is_moving = False
        self.move_start_time = None
        self.total_mouse_move_time = 0.0
        self.last_move_time = None
        self.movement_thread = None
    
    def log_event(self, event):
        """Log an event with timestamp"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        log_entry = f"[{timestamp}] {event}"
        print(log_entry)
        if self.file_handle:
            self.file_handle.write(log_entry + '\n')
            self.file_handle.flush()
    
    def start_logging(self):
        """Start logging session"""
        if not self.is_logging:
            self.is_logging = True
            self.left_click_count = 0
            self.right_click_count = 0
            self.backspace_count = 0
            self.scroll_up_count = 0
            self.scroll_down_count = 0
            self.scroll_left_count = 0
            self.scroll_right_count = 0
            self.first_key_time = None
            self.last_key_time = None
            self.total_mouse_move_time = 0.0
            self.is_moving = False
            self.move_start_time = None
            self.last_move_time = None

            self.file_handle = open(self.log_file, 'a')
            self.log_event("=== LOGGING STARTED ===")
            print("Logging started. Press F9 to stop.")
    
    def stop_logging(self):
        """Stop logging session"""
        if self.is_logging:

            total_duration = ((self.last_key_time - self.first_key_time).total_seconds() if self.first_key_time and self.last_key_time else 0.0)

            total_clicks = self.left_click_count + self.right_click_count
            total_scrolls = self.scroll_up_count + self.scroll_down_count + self.scroll_left_count + self.scroll_right_count

            print("\n")
            self.log_event(f"Total mouse movement time: {self.total_mouse_move_time:.3f} seconds")
            self.log_event(f"Total mouse clicks: {total_clicks}")
            self.log_event(f"Total mouse scrolls: {total_scrolls}")
            self.log_event(f"Total duration: {total_duration:.3f} seconds")
            self.log_event(f"Total backspaces: {self.backspace_count}")

            summary = "\t".join([
                f"{self.total_mouse_move_time:.3f},"
                f"{total_clicks},"
                f"{total_scrolls},"
                f"{total_duration:.3f},"
                f"{self.backspace_count}"
            ])
            self.log_event(f"SUMMARY (CSV): {summary}")
            self.log_event("=== LOGGING STOPPED ===\n")

            self.is_logging = False
            if self.file_handle:
                self.file_handle.close()
                self.file_handle = None

            print("Logging stopped.")
    
    def on_key_press(self, key):
        """Handle key press events"""
        try:
            # Start logging with F8 key
            if key == keyboard.Key.f8:
                self.start_logging()
                return
            
            # Stop logging with F9 key
            if key == keyboard.Key.f9:
                self.stop_logging()
                return
            
            if self.is_logging:
                now = datetime.now()

                if not self.first_key_time:
                    self.first_key_time = now
                self.last_key_time = now

                if key == keyboard.Key.backspace:
                    self.backspace_count += 1

                try:
                    key_name = key.char
                except AttributeError:
                    key_name = str(key).replace('Key.', '')

                # self.log_event(f"Key pressed: {key_name}")
        
        except Exception as e:
            print(f"Error in key press handler: {e}")
    
    def on_click(self, x, y, button, pressed):
        """Handle mouse click events"""
        if pressed and self.is_logging:
            if button == mouse.Button.left:
                self.left_click_count += 1
                #self.log_event("Mouse click: LEFT")
            elif button == mouse.Button.right:
                self.right_click_count += 1
                #self.log_event("Mouse click: RIGHT")

    def on_move(self, x, y):
        """Track mouse movement duration"""
        if not self.is_logging:
            return
        
        now = datetime.now()

        # if first key isn't pressed yet, mouse movement is first activity
        if not self.first_key_time:
            self.first_key_time = now

        if not self.is_moving:
            self.is_moving = True
            self.move_start_time = now
            # self.log_event("Mouse started moving")
        self.last_move_time = now
        self.last_key_time = now

    def on_scroll(self, x, y, dx, dy):
        """Handle mouse scroll events"""
        if not self.is_logging:
            return

        now = datetime.now()
        if not self.first_key_time:
            self.first_key_time = now
        self.last_key_time = now

        direction = []
        if dy > 0:
            self.scroll_up_count += 1
            direction.append("UP")
        elif dy < 0:
            self.scroll_down_count += 1
            direction.append("DOWN")

        if dx > 0:
            self.scroll_right_count += 1
            direction.append("RIGHT")
        elif dx < 0:
            self.scroll_left_count += 1
            direction.append("LEFT")

        # if direction:
        #     self.log_event(f"Mouse scrolled: {'/'.join(direction)}")

    def monitor_movement(self):
        """Background thread to detect when movement stops"""
        while True:
            if self.is_logging and self.is_moving and self.last_move_time:
                now = datetime.now()
                # If pointer hasn’t moved for 0.5s, stop counting
                if (now - self.last_move_time).total_seconds() > 0.5:
                    move_end = self.last_move_time
                    duration = (move_end - self.move_start_time).total_seconds()
                    self.total_mouse_move_time += duration
                    # self.log_event(f"Mouse stopped moving (duration: {duration:.3f}s)")
                    self.is_moving = False
            threading.Event().wait(0.2)  # check ~5x per second

    def run(self):
        """Start the logger"""
        print("Activity Logger started!")
        print("Press F8 to start logging")
        print("Press F9 to stop logging")

        keyboard_listener = keyboard.Listener(on_press=self.on_key_press)
        mouse_listener = mouse.Listener(
            on_click=self.on_click,
            on_move=self.on_move,
            on_scroll=self.on_scroll
        )

        keyboard_listener.start()
        mouse_listener.start()

        # Start background movement monitor
        self.movement_thread = threading.Thread(target=self.monitor_movement, daemon=True)
        self.movement_thread.start()

        try:
            keyboard_listener.join()
        except KeyboardInterrupt:
            print("\nExiting...")
            self.stop_logging()

if __name__ == "__main__":
    logger = ActivityLogger()
    logger.run()