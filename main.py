from SimpleLEDController import SimpleLEDController
from ValleyMetroTracker import ValleyMetroTracker
import asyncio

async def main():
    # Create instance of LED controller
    controller = SimpleLEDController()
    
    # Wait for connection
    await asyncio.sleep(2)
    
    # Set the board ID (replace with your actual board ID)
    controller.set_board("main",send_to_all=True)
    
    # Set up the tracker
    tracker = ValleyMetroTracker(
        stations_csv='stations.csv',
        gtfs_url="https://app.mecatran.com/utw/ws/gtfsfeed/vehicles/valleymetro?apiKey=4f22263f69671d7f49726c3011333e527368211f"
    )
    
    # Start the tracker in the background
    # tracker_task = asyncio.create_task(tracker.start_tracker())
    print("Starting Valley Metro train tracker...")
    
    try:
        while True:
            await asyncio.sleep(5)
            await tracker.run_tracker()
            closest_stations = tracker.get_train_closest_stations()
            west_bound_stations = []
            east_bound_stations = []
            
            for station in closest_stations:
                if station['direction'] == 'westbound':
                    west_bound_stations.append(station)
                else:
                    east_bound_stations.append(station)

            west_stations = {station['LED_ID'] for station in west_bound_stations}
            east_stations = {station['LED_ID'] for station in east_bound_stations}

            print("West-bound stations:", west_stations)
            print("East-bound stations:", east_stations)
            
            both_directions = west_stations.intersection(east_stations)
            for station_num in both_directions:
                controller.set_led(station_num, 255, 0, 255)  # Purple

            west_only = west_stations - east_stations
            for station_num in west_only:
                controller.set_led(station_num, 255, 0, 0)  # Red

            east_only = east_stations - west_stations
            for station_num in east_only:
                controller.set_led(station_num, 0, 0, 255)  # Blue

            # for all other stations (0-40) with no trains set to off 
            for i in range(41):
                if i not in both_directions and i not in west_only and i not in east_only:
                    controller.set_led(i, 0, 0, 0)
                
    except Exception as e:
        print(f"Error: {e}")
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        # Cancel the tracker task
        tracker_task.cancel()
        try:
            await tracker_task
        except asyncio.CancelledError:
            pass
        controller.client.loop_stop()
        controller.set_all_off()

if __name__ == "__main__":
    asyncio.run(main())
