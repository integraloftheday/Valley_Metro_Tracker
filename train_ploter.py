import requests
from google.transit import gtfs_realtime_pb2
from datetime import datetime
import time
import pandas as pd
from geopy.distance import geodesic
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import numpy as np

def get_valley_metro_train_locations():
    GTFS_RT_URL = "https://app.mecatran.com/utw/ws/gtfsfeed/vehicles/valleymetro?apiKey=4f22263f69671d7f49726c3011333e527368211f"
    
    try:
        feed = gtfs_realtime_pb2.FeedMessage()
        response = requests.get(GTFS_RT_URL)
        feed.ParseFromString(response.content)
        
        train_locations = []
        
        for entity in feed.entity:
            if entity.HasField('vehicle'):
                vehicle = entity.vehicle
                
                if vehicle.trip.route_id.startswith('RAIL'):
                    location = {
                        'lat': vehicle.position.latitude,
                        'lon': vehicle.position.longitude,
                        'train_id': vehicle.vehicle.id,
                        'route_id': vehicle.trip.route_id,
                        'trip_id': vehicle.trip.trip_id,
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
    stations_df = pd.read_csv('stations.csv')
    return stations_df

def check_trains_near_stations(train_locations, stations_df, threshold_km=0.5):
    stations_have_trains = [False] * len(stations_df)
    
    for train in train_locations:
        min_distance = float('inf')
        closest_station_idx = None
        train_coords = (train['lat'], train['lon'])
        
        for idx, station in stations_df.iterrows():
            station_coords = (station['POINT_Y'], station['POINT_X'])
            distance = geodesic(train_coords, station_coords).kilometers
            
            if distance < min_distance:
                min_distance = distance
                closest_station_idx = idx
        
        if min_distance <= threshold_km:
            stations_have_trains[closest_station_idx] = True
    
    return stations_have_trains

def determine_train_direction(train):
    # Extract direction from trip_id or route_id
    # You might need to adjust this based on your actual data format
    if 'EAST' in train['trip_id'].upper():
        return 'eastbound'
    elif 'WEST' in train['trip_id'].upper():
        return 'westbound'
    elif train['bearing'] is not None:
        # Use bearing as fallback
        if 45 <= train['bearing'] <= 225:
            return 'eastbound'
        else:
            return 'westbound'
    return 'unknown'

class TrainPlotter:
    def __init__(self, stations_df):
        self.stations_df = stations_df
        self.fig, self.ax = plt.subplots(figsize=(12, 8))
        self.direction_colors = {
            'eastbound': 'red',
            'westbound': 'blue',
            'unknown': 'gray'
        }
        self.setup_plot()
        
    def setup_plot(self):
        # Plot stations
        self.ax.scatter(self.stations_df['POINT_X'], self.stations_df['POINT_Y'], 
                       c='black', marker='s', label='Stations', zorder=1)
        
        # Add station labels
        for idx, station in self.stations_df.iterrows():
            self.ax.annotate(station['StationName'], 
                           (station['POINT_X'], station['POINT_Y']),
                           xytext=(5, 5), textcoords='offset points',
                           fontsize=8)
        
        self.ax.set_title('Valley Metro Train Locations')
        self.ax.set_xlabel('Longitude')
        self.ax.set_ylabel('Latitude')
        
        # Create legend elements for train directions
        from matplotlib.lines import Line2D
        legend_elements = [
            Line2D([0], [0], marker='^', color='w', 
                  markerfacecolor='red', label='Eastbound', markersize=10),
            Line2D([0], [0], marker='^', color='w', 
                  markerfacecolor='blue', label='Westbound', markersize=10),
            Line2D([0], [0], marker='s', color='w', 
                  markerfacecolor='black', label='Stations', markersize=10),
            Line2D([0], [0], marker='o', color='w', 
                  markerfacecolor='green', label='Active Station', markersize=10)
        ]
        self.ax.legend(handles=legend_elements)
        
        self.train_scatters = {}
        self.active_station_scatter = None
    
    def update(self, frame):
        train_locations = get_valley_metro_train_locations()
        stations_with_trains = check_trains_near_stations(train_locations, self.stations_df)
        
        # Clear previous train positions
        for scatter in self.train_scatters.values():
            scatter.remove()
        self.train_scatters.clear()
        
        if self.active_station_scatter:
            self.active_station_scatter.remove()
        
        # Group trains by direction
        direction_groups = {
            'eastbound': {'lons': [], 'lats': []},
            'westbound': {'lons': [], 'lats': []},
            'unknown': {'lons': [], 'lats': []}
        }
        
        for train in train_locations:
            direction = determine_train_direction(train)
            direction_groups[direction]['lons'].append(train['lon'])
            direction_groups[direction]['lats'].append(train['lat'])
        
        # Plot trains by direction
        for direction, coords in direction_groups.items():
            if coords['lons']:  # If there are trains in this direction
                self.train_scatters[direction] = self.ax.scatter(
                    coords['lons'], 
                    coords['lats'],
                    c=self.direction_colors[direction],
                    marker='^',
                    s=100,
                    zorder=2
                )
        
        # Highlight active stations
        active_stations = self.stations_df[stations_with_trains]
        if not active_stations.empty:
            self.active_station_scatter = self.ax.scatter(
                active_stations['POINT_X'], 
                active_stations['POINT_Y'],
                c='green', marker='o', s=100, 
                zorder=3)
        
        # Print status update
        print(f"\nUpdate at {datetime.now()}")
        print(f"Number of trains detected: {len(train_locations)}")
        print("\nStations with trains nearby:")
        for idx, has_train in enumerate(stations_with_trains):
            if has_train:
                station = self.stations_df.iloc[idx]
                print(f"LED_ID {idx}: {station['StationName']}")
        
        return tuple(self.train_scatters.values()) + (self.active_station_scatter,)

def main():
    print("Starting Valley Metro train tracker...")
    
    # Load stations data
    stations_df = load_stations()
    
    # Create plotter and animate
    plotter = TrainPlotter(stations_df)
    ani = FuncAnimation(plotter.fig, plotter.update, 
                       interval=5000,  # Update every 30 seconds
                       blit=True)
    
    plt.show()

if __name__ == "__main__":
    # Required packages:
    # pip install requests protobuf gtfs-realtime-bindings pandas geopy matplotlib
    main()
