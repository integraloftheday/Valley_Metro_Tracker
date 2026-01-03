import pandas as pd
from geopy.distance import geodesic
from google.transit import gtfs_realtime_pb2
from datetime import datetime
import asyncio
import aiohttp

class ValleyMetroTracker:
    def __init__(self, stations_csv, gtfs_url):
        # Load station data
        try:
            self.stations_df = pd.read_csv(stations_csv)
        except FileNotFoundError:
            print(f"Warning: {stations_csv} not found. Station logic will be empty.")
            self.stations_df = pd.DataFrame(columns=['StationName', 'POINT_X', 'POINT_Y', 'LED_ID'])

        self.gtfs_url = gtfs_url
        self.train_locations = []  # Store train locations
        self.update_interval = 5  # Interval to ping the endpoint (seconds)

    async def fetch_train_data(self):
        """Async fetch GTFS data and update train locations."""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(self.gtfs_url) as response:
                    if response.status != 200:
                        print(f"Error fetching data: HTTP {response.status}")
                        return

                    response_data = await response.read()
                    feed = gtfs_realtime_pb2.FeedMessage()
                    feed.ParseFromString(response_data)

                    new_locations = []

                    for entity in feed.entity:
                        if entity.HasField('vehicle'):
                            vehicle = entity.vehicle

                            # Optional: Filter by route if necessary
                            # if vehicle.trip.route_id not in ['A', 'B', 'C']: continue

                            r_id = vehicle.trip.route_id
                            d_id = vehicle.trip.direction_id


                            train_data = {
                                'lat': vehicle.position.latitude,
                                'lon': vehicle.position.longitude,
                                'train_id': vehicle.vehicle.id,
                                'route_id': r_id,
                                'trip_id': vehicle.trip.trip_id,
                                'timestamp': datetime.fromtimestamp(vehicle.timestamp),
                                'speed': vehicle.position.speed if vehicle.position.HasField('speed') else None,
                                'bearing': vehicle.position.bearing if vehicle.position.HasField('bearing') else None,
                                'direction_id': d_id
                            }
                            new_locations.append(train_data)

                    self.train_locations = new_locations

            except Exception as e:
                print(f"Error fetching train data: {e}")
                # Don't clear old data immediately on error to prevent flickering,
                # or clear if you prefer strict real-time accuracy:
                # self.train_locations = []

    async def start_tracker(self):
        """Continuously ping the GTFS endpoint."""
        print("Tracker started...")
        while True:
            await self.fetch_train_data()
            # print(f"Updated train data at {datetime.now()}") # Optional log
            await asyncio.sleep(self.update_interval)

    async def run_tracker(self):
        """Run a single update."""
        await self.fetch_train_data()
        print(f"Updated train data at {datetime.now()}")

    def get_train_locations(self):
        """
        Return a list of trains with their locations, ids, route info, and color.
        """
        return [
            {
                'lat': train['lat'],
                'lon': train['lon'],
                'train_id': train['train_id'],
                'route_id': train['route_id'],
                'direction_id': train['direction_id'],
                'color': train['color']
            }
            for train in self.train_locations
        ]

    def get_train_closest_stations(self):
        """
        For each train, determine the closest station.
        """
        closest_stations = []

        if self.stations_df.empty:
            return closest_stations

        for train in self.train_locations:
            min_distance = float('inf')
            closest_station = None

            train_coords = (train['lat'], train['lon'])

            for idx, station in self.stations_df.iterrows():
                # Ensure coordinate column names match your CSV
                station_coords = (station['POINT_Y'], station['POINT_X'])
                distance = geodesic(train_coords, station_coords).kilometers

                if distance < min_distance:
                    min_distance = distance
                    closest_station = station

            if closest_station is not None:
                closest_stations.append({
                    'train_id': train['train_id'],
                    'station_name': closest_station['StationName'],
                    # Check if LED_ID exists in CSV, else default to 0/None
                    'LED_ID': closest_station.get('LED_ID', 0),
                    'route_id': train['route_id'],
                    'direction_id': train['direction_id'],
                    'distance_km': round(min_distance, 3)
                })

        return closest_stations


# Example Usage
if __name__ == "__main__":
    # Ensure you have 'stations.csv' in the same directory
    # pip install aiohttp protobuf geopy pandas

    tracker = ValleyMetroTracker(
        stations_csv='stations.csv',
        gtfs_url="https://app.mecatran.com/utw/ws/gtfsfeed/vehicles/valleymetro?apiKey=4f22263f69671d7f49726c3011333e527368211f"
    )

    async def main():
        # Start the tracker task
        task = asyncio.create_task(tracker.start_tracker())

        # Example loop to print status every few seconds
        try:
            while True:
                await asyncio.sleep(5)
                locations = tracker.get_train_locations()
                stations = tracker.get_train_closest_stations()

                print(f"\n--- Status at {datetime.now().strftime('%H:%M:%S')} ---")
                print(f"Active Trains: {len(locations)}")

                if locations:
                    print("Sample Train Data:", locations[0])

                # Check for trains very close to stations (e.g., < 0.2km)
                for s in stations:
                    if s['distance_km'] < 0.2:
                        print(f"  -> Train {s['train_id']} ({s['route_id']}) is at {s['station_name']}")

        except KeyboardInterrupt:
            print("Stopping...")
            task.cancel()

    asyncio.run(main())
