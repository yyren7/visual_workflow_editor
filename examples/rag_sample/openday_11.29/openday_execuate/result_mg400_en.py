
import json
import time
from dobot_api import DobotApiDashboard, DobotApiMove

# Function to connect to the robot
def connect_robot(ip, port):
    dashboard = DobotApiDashboard(ip, port)
    move = DobotApiMove(ip, port)
    return dashboard, move

# Load points from JSON file
def load_points(file_path):
    with open(file_path, 'r') as file:
        points = json.load(file)
    return points

# Main pick-and-place function
def pick_and_place_task(dashboard, move, pick_points, place_points, do_pin):
    k = 0  # Counter for tasks
    while True:
        for pick, place in zip(pick_points, place_points):
            # Move to 40 cm above the pick position
            x, y, z, r = float(pick['x']), float(pick['y']), float(pick['z']) + 40, float(pick['r'])
            move.MovJ(x, y, z, r)
            move.Sync()  # Synchronize to ensure the robot reaches the position

            # Move down to the pick position
            z = float(pick['z'])
            move.MovJ(x, y, z, r)
            move.Sync()

            # Activate digital output (DO=1) and wait 0.2 seconds
            dashboard.DO(do_pin, 1)
            time.sleep(0.2)

            # Ascend 40 cm from the pick position
            z += 40
            move.MovJ(x, y, z, r)
            move.Sync()

            # Move to 40 cm above the place position
            x, y, z, r = float(place['x']), float(place['y']), float(place['z']) + 40, float(place['r'])
            move.MovJ(x, y, z, r)
            move.Sync()

            # Move down to the place position
            z = float(place['z'])
            move.MovJ(x, y, z, r)
            move.Sync()

            # Deactivate digital output (DO=0) and wait 0.2 seconds
            dashboard.DO(do_pin, 0)
            time.sleep(0.2)

            # Ascend 40 cm from the place position
            z += 40
            move.MovJ(x, y, z, r)
            move.Sync()

            # Increment task counter and print completion message
            k += 1
            print(f"[Task {k} completed]")

        # Reset task counter and print all tasks completed
        k = 0
        print("[All tasks completed]")

        # Swap pick and place positions for the next iteration
        pick_points, place_points = place_points, pick_points

# Main program
if __name__ == "__main__":
    # Robot IP and port
    ip = "192.168.250.101"
    port = 29999

    # Connect to the robot
    dashboard, move = connect_robot(ip, port)

    # Activate the robot and wait 2 seconds
    dashboard.EnableRobot()
    time.sleep(2)

    # Set robot speed to 50%
    dashboard.SpeedFactor(50)

    # Load points from JSON file
    points = load_points('./generated_points.json')
    pick_points = points['groups'][0]['coordinates']
    place_points = points['groups'][1]['coordinates']

    # Start the pick-and-place task
    pick_and_place_task(dashboard, move, pick_points, place_points, do_pin=1)
