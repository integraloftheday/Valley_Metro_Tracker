import requests
import pandas as pd
from geopy.distance import geodesic
from google.transit import gtfs_realtime_pb2
from datetime import datetime
import asyncio
import aiohttp


class ValleyMetroTracker:
    def __init__(self, stations_csv, gtfs_url):
        self.stations_df = pd.read_csv(stations_csv)  # Load station data
        self.gtfs_url = gtfs_url
        self.train_locations = []  # Store train locations
        self.update_interval = 5  # Interval to ping the endpoint (seconds)
        self.direction_colors = {
            'eastbound': 'red',
            'westbound': 'blue',
            'unknown': 'gray'
        }

    def determine_train_direction(self, train):
        """Determine if a train is eastbound or westbound."""
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

    async def fetch_train_data(self):
        """Async fetch GTFS data and update train locations."""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(self.gtfs_url) as response:
                    response_data = await response.read()
                    feed = gtfs_realtime_pb2.FeedMessage()
                    feed.ParseFromString(response_data)
                    self.train_locations = [
                        {
                            'lat': entity.vehicle.position.latitude,
                            'lon': entity.vehicle.position.longitude,
                            'train_id': entity.vehicle.vehicle.id,
                            'route_id': entity.vehicle.trip.route_id,
                            'trip_id': entity.vehicle.trip.trip_id,
                            'timestamp': datetime.fromtimestamp(entity.vehicle.timestamp),
                            'speed': entity.vehicle.position.speed if entity.vehicle.position.HasField('speed') else None,
                            'bearing': entity.vehicle.position.bearing if entity.vehicle.position.HasField('bearing') else None,
                            'direction': self.determine_train_direction({
                                'trip_id': entity.vehicle.trip.trip_id,
                                'bearing': entity.vehicle.position.bearing if entity.vehicle.position.HasField('bearing') else None,
                            })
                        }
                        for entity in feed.entity if entity.HasField('vehicle') and entity.vehicle.trip.route_id.startswith('RAIL')
                    ]
            except Exception as e:
                print(f"Error fetching train data: {e}")
                self.train_locations = []

    async def start_tracker(self):
        """Continuously ping the GTFS endpoint."""
        while True:
            await self.fetch_train_data()
            print(f"Updated train data at {datetime.now()}")
            await asyncio.sleep(self.update_interval)
            
    async def run_tracker(self):
        await self.fetch_train_data()
        print(f"Updated train data at {datetime.now()}")
        await asyncio.sleep(self.update_interval)

    def get_train_locations(self):
        """
        Return a list of trains with their locations and direction.
        Format: [{'lat': float, 'lon': float, 'train_id': str, 'direction': str}, ...]
        """
        return [
            {
                'lat': train['lat'],
                'lon': train['lon'],
                'train_id': train['train_id'],
                'direction': train['direction']
            }
            for train in self.train_locations
        ]

    def get_train_closest_stations(self):
        """
        For each train, determine the closest station and direction.
        Format: [{'train_id': str, 'station_name': str, 'LED_ID': int, 'direction': str}, ...]
        """
        closest_stations = []

        for train in self.train_locations:
            min_distance = float('inf')
            closest_station = None

            train_coords = (train['lat'], train['lon'])
            for idx, station in self.stations_df.iterrows():
                station_coords = (station['POINT_Y'], station['POINT_X'])
                distance = geodesic(train_coords, station_coords).kilometers

                if distance < min_distance:
                    min_distance = distance
                    closest_station = station

            if closest_station is not None:
                closest_stations.append({
                    'train_id': train['train_id'],
                    'station_name': closest_station['StationName'],
                    'LED_ID': closest_station['LED_ID'],
                    'direction': train['direction']
                })

        return closest_stations


# Example Usage
if __name__ == "__main__":
    # Set up the tracker
    tracker = ValleyMetroTracker(
        stations_csv='stations.csv',
        gtfs_url="https://app.mecatran.com/utw/ws/gtfsfeed/vehicles/valleymetro?apiKey=4f22263f69671d7f49726c3011333e527368211f"
    )

    async def main():
        # Start the tracker in the background
        asyncio.create_task(tracker.start_tracker())

        # Example usage after fetching data
        while True:
            await asyncio.sleep(5)  # Wait for some updates
            print("\nTrain Locations:")
            print(tracker.get_train_locations())

            print("\nClosest Stations:")
            print(tracker.get_train_closest_stations())

    asyncio.run(main())
