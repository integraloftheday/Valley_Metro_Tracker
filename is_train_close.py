import requests
from google.transit import gtfs_realtime_pb2
from datetime import datetime
import time
import pandas as pd
from geopy.distance import geodesic
from SimpleLEDController import SimpleLEDController

def get_valley_metro_train_locations():
    GTFS_RT_URL = "https://app.mecatran.com/utw/ws/gtfsfeed/vehicles/valleymetro?apiKey=4f22263f69671d7f49726c3011333e527368211f"
    
    try:
        # Create a GTFS-realtime feed message
        feed = gtfs_realtime_pb2.FeedMessage()
        response = requests.get(GTFS_RT_URL)
        feed.ParseFromString(response.content)
        
        train_locations = []
        
        for entity in feed.entity:
            if entity.HasField('vehicle'):
                vehicle = entity.vehicle
                
                # Check if it's a light rail vehicle
                if vehicle.trip.route_id.startswith('RAIL'):
                    location = {
                        'lat': vehicle.position.latitude,
                        'lon': vehicle.position.longitude,
                        'train_id': vehicle.vehicle.id,
                        'route_id': vehicle.trip.route_id,
                        'timestamp': datetime.fromtimestamp(vehicle.timestamp),
                        'speed': vehicle.position.speed if vehicle.position.HasField('speed') else None,
                        'bearing': vehicle.position.bearing if vehicle.position.HasField('bearing') else None
                    }
                    train_locations.append(location)
        
        return train_locations
    
    except Exception as e:
        print(f"Error fetching train locations: {e}")
        return []

def load_stations():
    # Load the CSV file with station information
    stations_df = pd.read_csv('stations.csv')  # Replace with your CSV file path
    return stations_df

def check_trains_near_stations(train_locations, stations_df, threshold_km=0.5):
    # Initialize list of booleans for each station
    stations_have_trains = [False] * len(stations_df)
    
    # For each train, find the closest station
    for train in train_locations:
        min_distance = float('inf')
        closest_station_idx = None
        train_coords = (train['lat'], train['lon'])
        
        # Check distance to each station
        for idx, station in stations_df.iterrows():
            station_coords = (station['POINT_Y'], station['POINT_X'])  # Note: CSV has lat in POINT_Y and lon in POINT_X
            distance = geodesic(train_coords, station_coords).kilometers
            
            if distance < min_distance:
                min_distance = distance
                closest_station_idx = idx
        
        # If train is within threshold of closest station, mark that station
        if min_distance <= threshold_km:
            stations_have_trains[closest_station_idx] = True
    
    return stations_have_trains

def main():
    print("Starting Valley Metro train tracker...")
    controller = SimpleLEDController()
    controller.set_brightness(10)
    
    # Wait for connection
    time.sleep(2)
    
    # Set the board ID (replace with your actual board ID)
    controller.set_board("fce6fc84")
    # Load stations data
    stations_df = load_stations()
    
    while True:
        try:
            # Get train locations
            train_locations = get_valley_metro_train_locations()
            
            if train_locations:
                # Check which stations have trains nearby
                stations_with_trains = check_trains_near_stations(train_locations, stations_df)
                
                print(f"\nUpdate at {datetime.now()}")
                print(f"Number of trains detected: {len(train_locations)}")
                print("\nStations with trains nearby:")
                
                # Print information about stations with trains
                for idx, has_train in enumerate(stations_with_trains):
                    led_num = int(stations_df["LED_ID"][idx])
                    if has_train:
                        controller.set_led(led_num, 255, 255, 255)
                        station = stations_df.iloc[idx]
                        print(f"LED_ID {idx}: {station['StationName']}")
                    else:
                        controller.set_led(led_num, 0, 0, 0)
                
                # Print the full boolean list
                print("\nFull station status list (True = train nearby):")
                print(stations_with_trains)
            else:
                print("No trains found in the current update")
            
            # Wait 30 seconds before next update
            time.sleep(5)
            
        except KeyboardInterrupt:
            print("\nStopping train tracker...")
            break
        except Exception as e:
            print(f"Error in main loop: {e}")
            time.sleep(30)  # Wait before retrying

if __name__ == "__main__":
    # Required packages:
    # pip install requests protobuf gtfs-realtime-bindings pandas geopy
    main()
