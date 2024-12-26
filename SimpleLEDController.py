import paho.mqtt.client as mqtt
import json
import sqlite3
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import threading
import time

class SimpleLEDController:
    def __init__(self, broker_ip="test.mosquitto.org", broker_port=1883, db_path="led_boards.db"):
        self.num_leds = 45
        self.chunk_size = 10
        self.current_board = None
        self.brightness = 50
        self.send_to_all = False
        self.active_boards = {}  # Dictionary to store board_id: last_seen
        self.timeout_seconds = 30
        self.db_path = db_path

        # Initialize database
        self._init_database()

        # Initialize MQTT client
        self.client = mqtt.Client(protocol=mqtt.MQTTv5)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

        # Connect to broker
        try:
            self.client.connect(broker_ip, broker_port, 60)
            self.client.loop_start()
        except Exception as e:
            print(f"Connection failed: {str(e)}")

        # Start cleanup thread for inactive boards
        self.cleanup_thread = threading.Thread(target=self._cleanup_inactive_boards, daemon=True)
        self.cleanup_thread.start()

    def _init_database(self):
        """Initialize SQLite database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS board_heartbeats (
                    board_id TEXT,
                    status TEXT,
                    last_seen TIMESTAMP,
                    PRIMARY KEY (board_id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS heartbeat_history (
                    board_id TEXT,
                    status TEXT,
                    timestamp TIMESTAMP,
                    PRIMARY KEY (board_id, timestamp)
                )
            """)

    def _update_board_heartbeat(self, board_id: str, status: str):
        """Update board heartbeat in database"""
        current_time = datetime.now()
        with sqlite3.connect(self.db_path) as conn:
            # Update current status
            conn.execute("""
                INSERT OR REPLACE INTO board_heartbeats (board_id, status, last_seen)
                VALUES (?, ?, ?)
            """, (board_id, status, current_time))
            # Add to history
            conn.execute("""
                INSERT INTO heartbeat_history (board_id, status, timestamp)
                VALUES (?, ?, ?)
            """, (board_id, status, current_time))
        self.active_boards[board_id] = current_time

    def get_active_boards(self) -> List[str]:
        """Returns list of currently active boards"""
        current_time = datetime.now()
        active = []
        
        for board_id, last_seen in list(self.active_boards.items()):
            if current_time - last_seen <= timedelta(seconds=self.timeout_seconds):
                active.append(board_id)
        return active

    def _cleanup_inactive_boards(self):
        """Periodically clean up inactive boards"""
        while True:
            current_time = datetime.now()
            with sqlite3.connect(self.db_path) as conn:
                for board_id, last_seen in list(self.active_boards.items()):
                    if current_time - last_seen > timedelta(seconds=self.timeout_seconds):
                        conn.execute("""
                            UPDATE board_heartbeats SET status = 'offline'
                            WHERE board_id = ?
                        """, (board_id,))
                        del self.active_boards[board_id]
            time.sleep(10)  # Check every 10 seconds

    def set_board(self, board_id: str, send_to_all: bool = False):
        """Set the current board ID"""
        self.current_board = board_id
        self.send_to_all = send_to_all

    def _publish_message(self, message: Dict):
        """Publish message to MQTT broker"""
        if self.send_to_all:
            active_boards = self.get_active_boards()
            for board_id in active_boards:
                topic = f"xVC5!GVcWEh4CF/neopixels/{board_id}/control"
                self.client.publish(topic, json.dumps(message))
        elif self.current_board:
            topic = f"xVC5!GVcWEh4CF/neopixels/{self.current_board}/control"
            self.client.publish(topic, json.dumps(message))
        else:
            print("No board selected!")

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            print("Connected to MQTT broker")
            # Subscribe to all heartbeat messages
            self.client.subscribe("xVC5!GVcWEh4CF/neopixels/+/heartbeat")
            if self.current_board:
                self.client.subscribe(f"xVC5!GVcWEh4CF/neopixels/{self.current_board}/status")
        else:
            print(f"Connection failed with code {rc}")

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload)
            # Handle heartbeat messages
            if "heartbeat" in msg.topic:
                board_id = payload.get("boardId")
                status = payload.get("status")
                if board_id and status:
                    self._update_board_heartbeat(board_id, status)
                    print(f"Heartbeat from {board_id}: {status}")
            
        except json.JSONDecodeError:
            print("Error parsing message")

    def get_board_history(self, board_id: str, hours: int = 24) -> List[Dict]:
        """Get board heartbeat history for the last n hours"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT board_id, status, timestamp
                FROM heartbeat_history
                WHERE board_id = ? AND timestamp > datetime('now', '-' || ? || ' hours')
                ORDER BY timestamp DESC
            """, (board_id, hours))
            return [{"board_id": row[0], "status": row[1], "timestamp": row[2]} 
                   for row in cursor.fetchall()]

    # [Previous methods remain unchanged: set_brightness, _rgb_to_hex, set_led, 
    # set_all, set_multiple_leds, all_off]

    def set_brightness(self, brightness: int):
        """Set LED brightness (0-255)"""
        if 0 <= brightness <= 255:
            self.brightness = brightness
            self._publish_message({"brightness": brightness})

    def _rgb_to_hex(self, r: int, g: int, b: int) -> str:
        """Convert RGB values to hex string"""
        return f"{r:02X}{g:02X}{b:02X}"

    def set_led(self, led_num: int, r: int, g: int, b: int):
        """Set single LED color using hex encoding"""
        if not self.current_board:
            print("No board selected!")
            return

        # Prepare a single LED update in the new format
        hex_color = self._rgb_to_hex(r, g, b)
        message = {
            "leds_hex": [(led_num, hex_color)],
            "brightness": self.brightness
        }
        self._publish_message(message)

    def set_all(self, r: int, g: int, b: int):
        """Set all LEDs by sending in chunks using hex encoding"""
        if not self.current_board:
            print("No board selected!")
            return

        hex_color = self._rgb_to_hex(r, g, b)

        # Update all LEDs in chunks
        for i in range(0, self.num_leds, self.chunk_size):
            chunk = [(led_num, hex_color) for led_num in range(i, min(i + self.chunk_size, self.num_leds))]
            
            message = {
                "leds_hex": chunk,
                "brightness": self.brightness
            }
            self._publish_message(message)

    def set_multiple_leds(self, led_colors: Dict[int, tuple]):
        """Set multiple LEDs with different colors
        led_colors: Dictionary mapping LED index to (r, g, b) tuple"""
        if not self.current_board:
            print("No board selected!")
            return

        # Convert input to the new format
        leds_hex = [(led_num, self._rgb_to_hex(r, g, b)) for led_num, (r, g, b) in led_colors.items()
                    if 0 <= led_num < self.num_leds]

        # Send in chunks
        for i in range(0, len(leds_hex), self.chunk_size):
            chunk = leds_hex[i:i + self.chunk_size]
            message = {
                "leds_hex": chunk,
                "brightness": self.brightness
            }
            self._publish_message(message)

    def all_off(self):
        """Turn all LEDs off using hex encoding"""
        self.set_all(0, 0, 0)



def main():
    # Create instance of LED controller
    controller = SimpleLEDController()
    
    # Wait for connection
    time.sleep(2)
    
    # Set the board ID (replace with your actual board ID)
    controller.set_board("main", send_to_all=True)
    
    print("Testing LED Controller...")

    while True:
            
        # Test basic functions
        print("\n1. Setting brightness to 50%")
        controller.set_brightness(50)
        time.sleep(1)
        
        print("\n2. Testing single LED control")
        controller.set_led(0, 255, 0, 0)  # Set first LED to red
        time.sleep(1)
        
        print("\n3. Testing all LEDs on (white)")
        controller.set_all(255, 255, 255)
        time.sleep(2)
        
        print("\n4. Testing color patterns")
        # Red gradient across first 5 LEDs
        for i in range(5):
            brightness = int(255 * (i + 1) / 5)
            controller.set_led(i, brightness, 0, 0)
        time.sleep(2)
        
        print("\n5. Testing blue wave (5 LEDs at a time)")
        for start in range(0, controller.num_leds, 5):
            end = min(start + 5, controller.num_leds)
            for i in range(start, end):
                controller.set_led(i, 0, 0, 255)
            time.sleep(0.5)
        time.sleep(2)
        
        print("\n6. Testing all off")
        controller.all_off()
        
        print("\nTest complete!")
        
        # Keep the program running to maintain MQTT connection
        time.sleep(5)



if __name__ == "__main__":
    main()
