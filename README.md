# Valley Metro LED Route Tracker

## Project Overview

A real-time visualization system that displays Valley Metro light rail train positions using LED lights on a custom PCB. The system consists of a Python server that fetches real-time train data and controls an ESP32-based Arduino board via MQTT to illuminate LEDs representing train locations along the route.

## Overview

This project creates a physical display of Valley Metro train locations using:
- Custom PCB with LED strip representing the Valley Metro light rail route
- ESP32 microcontroller for LED control
- Python server fetching real-time GTFS data
- MQTT communication between server and ESP32

## Features

- Real-time train tracking using Valley Metro's GTFS feed
- Color-coded LED indicators:
  - Blue: Eastbound trains
  - Red: Westbound trains
  - Purple: Stations with trains in both directions
- Automatic updates every 30 seconds
- MQTT-based communication for reliable control
- Support for multiple LED boards

## Hardware Requirements

- ESP32 development board
- WS2812B LED strip
- Custom PCB (PCB design files in `/hardware`) (to be added in the future)
- 5V power supply
- USB cable for programming

## Software Requirements

### Python Server
```
pip install requirements.txt
```

Required packages:
- requests
- pandas
- geopy
- aiohttp
- protobuf
- gtfs-realtime-bindings
- paho-mqtt

### Arduino IDE
- ESP32 board support
- FastLED library
- PubSubClient library

## Installation

1. **Python Server Setup**
```
git clone
and install requirements
pip install -r requirements.txt
```

2. **ESP32 Setup**
- Open Arduino IDE
- Install ESP32 board support
- Install required libraries
- Upload the Arduino code to your ESP32

## Configuration

### Python Server
1. Update `stations.csv` with your LED mapping
2. Configure MQTT broker settings in `SimpleLEDController.py`
3. Set your GTFS API key in `main.py`

### ESP32
1. Update WiFi credentials in `arduino/config.h`
2. Set MQTT broker details
3. Configure LED pin and count

## Usage

1. Start the MQTT broker
```
mosquitto -v
```

2. Run the Python server
```
python main.py
```

3. Power on the ESP32 board

## Code Structure

### Python Server
```
# main.py - Main application logic
from SimpleLEDController import SimpleLEDController
from ValleyMetroTracker import ValleyMetroTracker
import asyncio

# Main loop fetches train data and updates LEDs
async def main():
    controller = SimpleLEDController()
    tracker = ValleyMetroTracker(stations_csv='stations.csv', gtfs_url="...")
    
    while True:
        await tracker.run_tracker()
        closest_stations = tracker.get_train_closest_stations()
        # Update LEDs based on train locations
```

### Arduino Code
```
// valley_metro_led.ino
#include <WiFi.h>
#include <PubSubClient.h>
#include <FastLED.h>

#define NUM_LEDS 41
#define LED_PIN 5

CRGB leds[NUM_LEDS];

void setup() {
    FastLED.addLeds<WS2812B, LED_PIN, GRB>(leds, NUM_LEDS);
    setupWiFi();
    setupMQTT();
}

void loop() {
    // Handle MQTT messages and LED updates
}
```

## MQTT Topics

| Topic | Description | Format |
|-------|-------------|---------|
| `led/control` | Set individual LED colors | "LED_NUM,R,G,B" | or hex variant

## Project Structure
```
valley-metro-led-tracker/
├── python/
│   ├── main.py
│   ├── SimpleLEDController.py
│   ├── ValleyMetroTracker.py
│   └── stations.csv
├── arduino/
│   ├── valley_metro_led.ino
│   └── config.h
├── hardware/
│   └── pcb_design/
└── README.md
```

## Configuration Files

### stations.csv format
```
LED_ID,StationName,Jurisdiction,StationStatus,POINT_X,POINT_Y
0,Metro Parkway,Phoenix,In Operation,-112.1175874,33.5767664
...
```


## Troubleshooting

Common issues and solutions:
1. **LED not updating**: Check MQTT connection and broker status
2. **No train data**: Verify GTFS API key and internet connection
3. **ESP32 not connecting**: Confirm WiFi credentials and network availability

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Valley Metro for providing the GTFS feed
- FastLED library developers
- MQTT community

## Authors

- Integraloftheday (Mason Manetta)

## Project Status

Active development - Bug reports and feature requests welcome!

## Future Enhancements

- Web interface for configuration
- Mobile app for monitoring
- Additional visualization modes
- Historical data tracking
- Integration with Valley Metro API for service alerts

## Support

For support, please open an issue in the GitHub repository or contact the maintainers.
```
