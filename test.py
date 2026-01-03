import tkinter as tk
from tkinter import ttk, colorchooser
import paho.mqtt.client as mqtt
import json
import colorsys
import threading
import time
from typing import List, Dict

class LEDController:
    def __init__(self):
        # Initialize Tkinter root and variables
        self.root = tk.Tk()
        self.root.title("LED Controller")
        self.root.geometry("800x600")
        
        # Variables
        self.status_var = tk.StringVar(value="Ready")
        self.current_board = tk.StringVar(value="")
        self.boards: Dict[str, List[Dict]] = {}
        self.num_leds = 45
        self.selected_color = "#FF0000"  # Default red
        self.led_states = [False] * self.num_leds  # Track LED states
        self.brightness = tk.IntVar(value=50)  # Default brightness
        
        # Initialize MQTT client with protocol v5
        self.client = mqtt.Client(protocol=mqtt.MQTTv5)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        
        # Connect to MQTT broker
        try:
            self.client.connect("192.168.4.175", 1883, 60)
            self.client.loop_start()
        except Exception as e:
            self.status_var.set(f"Connection failed: {str(e)}")
        
        self.setup_gui()
        
    def setup_gui(self):
        # Top Frame for controls
        control_frame = ttk.Frame(self.root)
        control_frame.pack(fill='x', padx=5, pady=5)
        
        # Board selection
        ttk.Label(control_frame, text="Board ID:").pack(side='left')
        self.board_combo = ttk.Combobox(control_frame, textvariable=self.current_board)
        self.board_combo.pack(side='left', padx=5)
        self.board_combo.bind('<<ComboboxSelected>>', self.on_board_select)
        
        # Color selection
        ttk.Button(control_frame, text="Select Color", 
                  command=self.choose_color).pack(side='left', padx=5)

        # Brightness control
        brightness_frame = ttk.Frame(control_frame)
        brightness_frame.pack(side='left', padx=5)
        ttk.Label(brightness_frame, text="Brightness:").pack(side='left')
        self.brightness_slider = ttk.Scale(brightness_frame, from_=0, to=255,
                                         orient='horizontal', variable=self.brightness,
                                         command=self.on_brightness_change)
        self.brightness_slider.pack(side='left')
        
        # Test patterns
        ttk.Button(control_frame, text="All On", 
                  command=self.all_on).pack(side='left', padx=5)
        ttk.Button(control_frame, text="All Off", 
                  command=self.all_off).pack(side='left', padx=5)
        ttk.Button(control_frame, text="Chase", 
                  command=self.chase_pattern).pack(side='left', padx=5)
        ttk.Button(control_frame, text="Rainbow", 
                  command=self.rainbow_pattern).pack(side='left', padx=5)
        
        # LED Grid
        self.led_frame = ttk.Frame(self.root)
        self.led_frame.pack(fill='both', expand=True, padx=5, pady=5)
        self.create_led_grid()
        
        # Status bar
        ttk.Label(self.root, textvariable=self.status_var).pack(side='bottom', pady=5)

    def on_brightness_change(self, value):
        # Update brightness for current state
        if self.current_board.get():
            self.publish_message({"brightness": self.brightness.get()})
    
    def create_led_grid(self):
        self.led_buttons = []
        rows = 5
        cols = 9
        
        for i in range(rows):
            self.led_frame.grid_rowconfigure(i, weight=1)
            for j in range(cols):
                self.led_frame.grid_columnconfigure(j, weight=1)
                led_num = i * cols + j
                if led_num < self.num_leds:
                    btn = ttk.Button(self.led_frame, text=f"LED {led_num}",
                                   command=lambda x=led_num: self.toggle_led(x))
                    btn.grid(row=i, column=j, padx=2, pady=2, sticky='nsew')
                    self.led_buttons.append(btn)
    
    def choose_color(self):
        color = colorchooser.askcolor(title="Choose LED color")[1]
        if color:
            self.selected_color = color
            
    def hex_to_rgb(self, hex_color):
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def toggle_led(self, led_num):
        if not self.current_board.get():
            self.status_var.set("No board selected!")
            return
        
        # Toggle the LED state
        self.led_states[led_num] = not self.led_states[led_num]
        
        # Set color based on state
        if self.led_states[led_num]:
            r, g, b = self.hex_to_rgb(self.selected_color)
        else:
            r, g, b = 0, 0, 0
            
        message = {
            "leds": [{
                "i": led_num,
                "r": r,
                "g": g,
                "b": b
            }],
            "brightness": self.brightness.get()
        }
        self.publish_message(message)

    def all_on(self):
        if not self.current_board.get():
            self.status_var.set("No board selected!")
            return
        
        r, g, b = self.hex_to_rgb(self.selected_color)
        message = {
            "leds": [{"i": i, "r": r, "g": g, "b": b} for i in range(self.num_leds)],
            "brightness": self.brightness.get()
        }
        self.publish_message(message)
        self.led_states = [True] * self.num_leds

    def all_off(self):
        if not self.current_board.get():
            self.status_var.set("No board selected!")
            return
        
        message = {
            "leds": [{"i": i, "r": 0, "g": 0, "b": 0} for i in range(self.num_leds)],
            "brightness": self.brightness.get()
        }
        self.publish_message(message)
        self.led_states = [False] * self.num_leds
        
    def chase_pattern(self):
        if not self.current_board.get():
            self.status_var.set("No board selected!")
            return
            
        def chase():
            r, g, b = self.hex_to_rgb(self.selected_color)
            while True:
                for i in range(self.num_leds):
                    message = {
                        "leds": [
                            {"i": i, "r": r, "g": g, "b": b},
                            {"i": (i-1) % self.num_leds, "r": 0, "g": 0, "b": 0}
                        ],
                        "brightness": self.brightness.get()
                    }
                    self.publish_message(message)
                    time.sleep(0.1)
        
        # Start chase in background thread
        chase_thread = threading.Thread(target=chase, daemon=True)
        chase_thread.start()
        
    def rainbow_pattern(self):
        if not self.current_board.get():
            self.status_var.set("No board selected!")
            return
            
        leds = []
        for i in range(self.num_leds):
            hue = i / self.num_leds
            rgb = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
            r = int(rgb[0] * 255)
            g = int(rgb[1] * 255)
            b = int(rgb[2] * 255)
            leds.append({"i": i, "r": r, "g": g, "b": b})
        
        message = {
            "leds": leds,
            "brightness": self.brightness.get()
        }
        self.publish_message(message)
    
    def on_board_select(self, event):
        selected = self.current_board.get()
        if selected:
            self.status_var.set(f"Selected board: {selected}")
            # Reset LED states when selecting a new board
            self.led_states = [False] * self.num_leds
    
    def on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            self.status_var.set("Connected to MQTT broker")
            self.client.subscribe("home/neopixels/+/status")
        else:
            self.status_var.set(f"Connection failed with code {rc}")
    
    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload)
            if "boardId" in payload:
                board_id = payload["boardId"]
                if board_id not in self.boards:
                    self.boards[board_id] = payload
                    self.board_combo['values'] = list(self.boards.keys())
                    self.status_var.set(f"New board discovered: {board_id}")
        except json.JSONDecodeError:
            self.status_var.set("Error parsing message")
    
    def publish_message(self, message):
        if not self.current_board.get():
            self.status_var.set("No board selected!")
            return
            
        topic = f"home/neopixels/{self.current_board.get()}/control"
        self.client.publish(topic, json.dumps(message))
        self.status_var.set(f"Published to {topic}")
    
    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    controller = LEDController()
    controller.run()
