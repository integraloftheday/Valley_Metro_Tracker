#!/usr/bin/env python3

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

                # Filter for specific routes if needed, or remove check to see all
                if vehicle.trip.route_id in ['A', 'B', 'C']:

                    location = {
                        'lat': vehicle.position.latitude,
                        'lon': vehicle.position.longitude,
                        'train_id': vehicle.vehicle.id,
                        'route_id': vehicle.trip.route_id,
                        'trip_id': vehicle.trip.trip_id,
                        'timestamp': datetime.fromtimestamp(vehicle.timestamp),
                        'speed': vehicle.position.speed if vehicle.position.HasField('speed') else None,
                        'bearing': vehicle.position.bearing if vehicle.position.HasField('bearing') else None,
                        # Fixed typo: diretion_id -> direction_id
                        'direction_id': vehicle.trip.direction_id
                    }
                    train_locations.append(location)

        return train_locations

    except Exception as e:
        print(f"Error fetching train locations: {e}")
        return []

def load_stations():
    # Ensure you have a stations.csv file in the same directory
    # Format should be: StationName, POINT_X (lon), POINT_Y (lat)
    try:
        stations_df = pd.read_csv('stations.csv')
        return stations_df
    except FileNotFoundError:
        print("stations.csv not found. Please provide a CSV file.")
        # Return empty DF to prevent crash, though plot will be empty of stations
        return pd.DataFrame(columns=['StationName', 'POINT_X', 'POINT_Y'])

def check_trains_near_stations(train_locations, stations_df, threshold_km=0.5):
    if stations_df.empty:
        return []

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

        if min_distance <= threshold_km and closest_station_idx is not None:
            stations_have_trains[closest_station_idx] = True

    return stations_have_trains

class TrainPlotter:
    def __init__(self, stations_df):
        self.stations_df = stations_df
        self.fig, self.ax = plt.subplots(figsize=(12, 8))

        # Define colors based on (Route_ID, Direction_ID)
        # Direction 0 is usually Outbound/North/East, 1 is Inbound/South/West
        self.color_map = {
            ('A', 0): 'red',
            ('A', 1): 'darkred',
            ('B', 0): 'royalblue',
            ('B', 1): 'navy',
            ('C', 0): 'limegreen',
            ('C', 1): 'darkgreen',
            # Add a generic fallback logic in the update loop
        }

        self.setup_plot()

    def setup_plot(self):
        # Plot stations
        if not self.stations_df.empty:
            self.ax.scatter(self.stations_df['POINT_X'], self.stations_df['POINT_Y'],
                          c='black', marker='s', label='Stations', zorder=1)

            # Add station labels
            for idx, station in self.stations_df.iterrows():
                self.ax.annotate(station['StationName'],
                               (station['POINT_X'], station['POINT_Y']),
                               xytext=(5, 5), textcoords='offset points',
                               fontsize=8)

        self.ax.set_title('Valley Metro Train Locations (Color by Route/Dir)')
        self.ax.set_xlabel('Longitude')
        self.ax.set_ylabel('Latitude')

        # Create legend elements manually for the specific routes we care about
        from matplotlib.lines import Line2D
        legend_elements = [
            Line2D([0], [0], marker='s', color='w', markerfacecolor='black', label='Stations'),
            Line2D([0], [0], marker='o', color='w', markerfacecolor='gold', label='Active Station'),
            # Route A
            Line2D([0], [0], marker='^', color='w', markerfacecolor='red', label='Route A (Dir 0)'),
            Line2D([0], [0], marker='^', color='w', markerfacecolor='darkred', label='Route A (Dir 1)'),
            # Route B
            Line2D([0], [0], marker='^', color='w', markerfacecolor='royalblue', label='Route B (Dir 0)'),
            Line2D([0], [0], marker='^', color='w', markerfacecolor='navy', label='Route B (Dir 1)'),
            # Route C
            Line2D([0], [0], marker='^', color='w', markerfacecolor='limegreen', label='Route C (Dir 0)'),
            Line2D([0], [0], marker='^', color='w', markerfacecolor='darkgreen', label='Route C (Dir 1)'),
            # Unknown
            Line2D([0], [0], marker='^', color='w', markerfacecolor='gray', label='Other/Unknown'),
        ]
        self.ax.legend(handles=legend_elements, loc='upper right', fontsize='small')

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
            self.active_station_scatter = None

        # Group trains by unique keys: (route_id, direction_id)
        # We use a dictionary where key = (route, dir) and value = lists of coordinates
        grouped_trains = {}

        for train in train_locations:
            r_id = train['route_id']
            d_id = train['direction_id']
            key = (r_id, d_id)

            if key not in grouped_trains:
                grouped_trains[key] = {'lons': [], 'lats': []}

            grouped_trains[key]['lons'].append(train['lon'])
            grouped_trains[key]['lats'].append(train['lat'])

        # Plot trains by group
        for key, coords in grouped_trains.items():
            # Determine color: check map, else default to gray
            color = self.color_map.get(key, 'gray')

            self.train_scatters[key] = self.ax.scatter(
                coords['lons'],
                coords['lats'],
                c=color,
                marker='^',
                s=100,
                zorder=2
            )

        # Highlight active stations
        if not self.stations_df.empty:
            active_stations = self.stations_df[stations_with_trains]
            if not active_stations.empty:
                self.active_station_scatter = self.ax.scatter(
                    active_stations['POINT_X'],
                    active_stations['POINT_Y'],
                    c='gold', marker='o', s=150, alpha=0.6,
                    zorder=3)

        # Print status update
        print(f"\nUpdate at {datetime.now().strftime('%H:%M:%S')}")
        print(f"Number of trains detected: {len(train_locations)}")

        # Optional: Print details about detected routes/directions
        for key in grouped_trains:
            count = len(grouped_trains[key]['lons'])
            print(f"Route {key[0]} (Dir {key[1]}): {count} trains")

        return tuple(self.train_scatters.values()) + (self.active_station_scatter,) if self.active_station_scatter else tuple(self.train_scatters.values())

def main():
    print("Starting Valley Metro train tracker...")

    # Load stations data
    stations_df = load_stations()

    # Create plotter and animate
    plotter = TrainPlotter(stations_df)

    # Note: interval is in milliseconds
    ani = FuncAnimation(plotter.fig, plotter.update,
                        interval=5000,  # Update every 5 seconds
                        blit=False) # blit=False is often more stable for varying numbers of artists

    plt.show()

if __name__ == "__main__":
    # Required packages:
    # pip install requests protobuf gtfs-realtime-bindings pandas geopy matplotlib
    main()
