from SimpleLEDController import SimpleLEDController
from ValleyMetroTracker import ValleyMetroTracker
import asyncio

#PULLING INTERVAL
FETCH_INTERVAL = 10
#Number of LEDS
NUM_LEDS = 41
#Assign Bit mask directions
A_WEST = 1<<0  #0001
A_EAST = 1<<1  #0010
B_NORTH = 1<<2 #0100
B_SOUTH = 1<<3 #1000
NO_TRAIN = 0 #0000


#define color mapping for station and direction
COLOR_CONFIG = {
    A_WEST:            (128, 0, 0),    # Maroon
    A_EAST:            (255, 0, 128),  # Magenta/Bright Purple
    A_WEST | A_EAST:   (102, 0, 102),  # Deep Purple (Combined A)

    B_NORTH:           (0, 160, 220),  # Valley Metro Blue
    B_SOUTH:           (0, 255, 255),  # Cyan
    B_NORTH | B_SOUTH: (0, 100, 150),  # Steel Blue (Combined B)

    A_WEST | B_NORTH:  (200, 200, 200), # Silver/Grey Transfer

    A_WEST | A_EAST | B_NORTH | B_SOUTH: (255, 255, 255), # White (Hub)
    0: (0,0,0) # NO TRAIN
}

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
            await asyncio.sleep(FETCH_INTERVAL)
            await tracker.run_tracker()
            closest_stations = tracker.get_train_closest_stations()
            a_west_bound_stations = []
            a_east_bound_stations = []
            b_north_bound_stations = []
            b_south_bound_stations = []

            # create LED array
            LEDS = [0] * NUM_LEDS # Empty array of length

            for station in closest_stations:
                if((station['route_id'],station['direction_id']) == ('A',1)): # A_WEST
                    LEDS[station["LED_ID"]] = LEDS[station["LED_ID"]] | A_WEST
                elif((station['route_id'],station['direction_id']) == ('A',0)): #A_EAST
                    LEDS[station["LED_ID"]] = LEDS[station["LED_ID"]] | A_EAST
                elif((station['route_id'],station['direction_id']) == ('B',1)):
                    LEDS[station["LED_ID"]] = LEDS[station["LED_ID"]] | B_NORTH
                elif((station['route_id'],station['direction_id']) == ('B',0)):
                    LEDS[station["LED_ID"]] = LEDS[station["LED_ID"]] | B_SOUTH
            #setting colors
            for i in range(NUM_LEDS):
                color_r, color_g, color_b = COLOR_CONFIG.get(LEDS[i],(0,0,0))
                controller.set_led(i, color_r,color_g,color_b)
                
    except Exception as e:
        print(f"Error: {e}")
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        # Cancel the tracker task
        #tracker_task.cancel()
        #try:
        #    await tracker_task
        #except asyncio.CancelledError:
        #    pass
        #controller.client.loop_stop()
        controller.set_all_off()

if __name__ == "__main__":
    asyncio.run(main())
