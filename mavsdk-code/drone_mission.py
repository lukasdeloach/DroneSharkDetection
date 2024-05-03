#!/usr/bin/env python3
# Author - Lukas DeLoach
import asyncio
import json
import math
import sys

import cv2
import torch
from geopy.distance import great_circle
from LifeguardStand import LifeGuardStand
from mavsdk import System
from mavsdk.offboard import (
    OffboardError,
    PositionGlobalYaw,
    PositionNedYaw,
    VelocityBodyYawspeed,
    VelocityNedYaw,
)
from SharkAlerts import SharkAlert

# Initial coordinates
initial_lat = 29.043192
initial_lng = -80.897632
# Number of lifeguard stands to populate
num_stands = 10

# Determine the total number of frames in the video
video_file = '../images/exampleVideo2.mp4'
vidcap = cv2.VideoCapture(video_file)
FPS = 200
total_frames = int(vidcap.get(cv2.CAP_PROP_FRAME_COUNT))

# Calculate the duration of the video in seconds
# Assuming 'fps' is the frame rate of the video
video_duration_seconds = total_frames / FPS

# Calculate the time interval between frames for 30 FPS
time_interval = 1 / 30  # seconds
WIDTH = 800
HEIGHT = 500
LAT = 29.043192
LNG = -80.897632
THRESHOLD = .125
# Dictionary to keep track of how many sharks were detected in the entirety of the simulation.
SHARKS = {}

# Loading up the pre-trained yolov5 model/
model = torch.hub.load('ultralytics/yolov5', 'custom', path='../best.pt')


async def run():

    drone = System(mavsdk_server_address='localhost', port=50051)
    await drone.connect(system_address="udp://:14540")

    print("Waiting for drone to connect...")
    async for state in drone.core.connection_state():
        if state.is_connected:
            print(f"-- Connected to drone!")
            break

    print("Waiting for drone to have a global position estimate...")
    async for health in drone.telemetry.health():
        if health.is_global_position_ok and health.is_home_position_ok:
            print("-- Global position estimate OK")
            break

    print("-- Arming")
    await drone.action.arm()

    print("-- Setting initial setpoint")
    await drone.offboard.set_position_global(PositionGlobalYaw(LAT, LNG, 0.0, 0.0, PositionGlobalYaw.AltitudeType(0)))
    await get_drone_position(drone)

    print("-- Starting offboard")
    try:
        await drone.offboard.start()
    except OffboardError as error:
        print(f"Starting offboard mode failed \
                with error code: {error._result.result}")
        print("-- Disarming")
        await drone.action.disarm()
        return

    print("-- Go 0m North, 0m East, -5m Down \
            within local coordinate system, turn to face east.")
    await drone.offboard.set_position_ned(
        PositionNedYaw(0.0, 0.0, -10.0, 0.0))
    await asyncio.sleep(8)
    await get_drone_position(drone)

    # Go east out to ocean first
    print("-- Go 0m North, 7500m East, -5m Down \
            within local coordinate system, Turn to face the east")
    await drone.offboard.set_position_ned(
        PositionNedYaw(0.0, 250.0, -10.0, 70.0))
    await asyncio.sleep(15)
    await get_drone_position(drone)

    await drone.offboard.set_velocity_ned(VelocityNedYaw(0.0, 0.0, 0.0, -5.0))
    await asyncio.sleep(5)

    # Turning north to scan for sharks
    print("-- Go 100m North, 0m East, -10m Down \
            within local coordinate system, Turn to face the North and Scan for Sharks")
    await drone.offboard.set_position_ned(
        PositionNedYaw(100.0, 120.0, -10.0, -15.0))
    await asyncio.sleep(10)
    await get_drone_position(drone)

    elapsed_time = 0
    initial_location = await update_location(elapsed_time)
    location_x = initial_location[1]
    location_y = initial_location[2]
    angle = 90 - math.degrees(math.atan2(location_y, location_x))
    # Calculate drone's distance from the point (Assumes starting at origin)
    distance = math.sqrt(location_x ** 2 + location_y ** 2)
    # Mark the halfway point from the destination
    half_distance = 10000

    print(f"Detected a Shark! Drone Distance from shark: {distance}. ")
    print(f"-- Turn to face {angle}")
    await drone.offboard.set_velocity_ned(VelocityNedYaw(0.0, 0.0, 0.0, angle))
    await asyncio.sleep(2)
    input("Press Enter to continue...")

    # Change speed depending on the drone's distance from the point
    speed = speed_function(distance)
    await drone.offboard.set_velocity_body(VelocityBodyYawspeed(speed, 0.0, 0.0, 0.0))

    origin_x = origin_y = 0
    speed_x = speed_y = 0
    i = counter = 0
    last_found_location = [0, 0, 0]
    update_feed = True
    j = 0

    async for pos in drone.telemetry.position_velocity_ned():
        print("\n")
        j+=1
        if update_feed:
            i += 1
            location = await update_location(i * FPS)
            update_feed = False
        if location[0] is None and location[1] is None and location[2] is None and location[3] is None:
            break
        else:
            counter += 1
            location_x = location[1]
            location_y = location[2]
            found_shark = location[3]
            alert = location[4]
            previous_distance = distance
            distance = math.sqrt((origin_x + location_x - pos.position.east_m) ** 2 + (
                origin_y + location_y - pos.position.north_m) ** 2)

            if found_shark:
                drone_location = await get_drone_position(drone)
                notify_nearest_stand(drone_location, alert)
                if distance < half_distance or (previous_distance < distance and counter > 50):  # If less than halfway to the shark, slow down
                    print("Drone is very close to the shark -- slowing down.")
                    half_distance = distance / 2
                    await drone.offboard.set_velocity_body(VelocityBodyYawspeed(0.0, 0.0, 0.0, angle))
                    update_feed = True
                    counter = 0
                else:
                    print(
                        f"Distance: {distance}, Half Way Distance: {half_distance}, Speed: {speed}")
                if update_feed:  # If more than halfway, fly towards the shark
                    angle = 90-math.degrees(math.atan2(location_y, location_x))
                    origin_x = pos.position.east_m
                    origin_y = pos.position.north_m
                    # Change speed depending on the drone's distance from the point
                    speed_y = speed_x = 0

                    # Calculate the vertical and horizontal distance from the last found location
                    delta_y = location_y - last_found_location[1]
                    delta_x = location_x - last_found_location[0]

                    # Adjust drone's speed and direction based on shark's movement
                    # If shark has moved significantly in vertical direction
                    if abs(delta_y) > THRESHOLD:
                        # Adjust drone's vertical speed proportional to shark's movement
                        speed_y = speed_function(
                            abs(delta_y+half_distance)) * (1 if delta_y > 0 else -1)
                        print(
                            f"Shark has moved {'up' if delta_y > 0 else 'down'} by {abs(delta_y)}m. Drone facing towards {angle}")

                    # If shark has moved significantly in horizontal direction
                    if abs(delta_x) > THRESHOLD:
                        # Adjust drone's horizontal speed proportional to shark's movement
                        speed_x = speed_function(
                            abs(delta_x+half_distance)) * (1 if delta_x > 0 else -1)
                        print(
                            f"Shark has moved {'right' if delta_x > 0 else 'left'} by {abs(delta_x)}m. Drone facing towards {angle}")

                    # If both delta_x and delta_y are within threshold, hold position
                    if abs(delta_y) <= THRESHOLD and abs(delta_x) <= THRESHOLD:
                        print(
                            "Drone is in a good position -- shark is in center frame -- Holding position.")

                    await drone.offboard.set_velocity_ned(VelocityNedYaw(speed_y, speed_x, 0.0, angle))
                    last_found_location = [location_x, location_y, angle]
                    print(
                        f"Distance: {distance}, Half Way Distance: {half_distance}, Speed: {speed}")
            else:
                print("There was no shark found. Continuing to fly towards the last position of the detected shark.")
                update_feed = True
                await drone.offboard.set_velocity_ned(VelocityNedYaw(speed_y, speed_x, 0, last_found_location[2]))

    print("-- Returning Back to shore and landing")
    await drone.offboard.set_position_ned(
        PositionNedYaw(0.0, 0.0, -5.0, 0.0))
    await asyncio.sleep(25)

    print("-- Landing")
    await drone.offboard.set_position_ned(
        PositionNedYaw(0, 0, 0.0, 0.0))
    await asyncio.sleep(20)

    print("-- Stopping offboard")
    try:
        await drone.offboard.stop()
    except OffboardError as error:
        print(f"Stopping offboard mode failed \
                with error code: {error._result.result}")


async def update_location(time_passed):
    global SHARKS  # Access the global SHARKS dictionary
    persons = []

    vidcap = cv2.VideoCapture(video_file)
    vidcap.set(cv2.CAP_PROP_POS_MSEC, time_passed)
    success, frame = vidcap.read()
    if not success:
        print("Video ended")
        return None, None, None, None  # Return None if video ended

    # Perform object detection on the frame
    resized_frame = cv2.resize(frame, (WIDTH, HEIGHT))
    results = model(resized_frame)
    results_np = results.xyxy[0].numpy()
    shark_box_x = shark_box_y = 0
    found_shark = False
    found_person = False

    # Draw bounding boxes on the resized frame
    for result in results_np:
        person_threshold = 0.35
        shark_threshold = 0.60
        boat_threshold = other_threshold = 0.85
        detection_type = ""
        x1, y1, x2, y2, conf, cls = result

        if cls == 3 and conf >= shark_threshold:
            detection_type = "Shark"
            shark_id = None
            shark_box_x = (x1 + x2) / 2
            shark_box_y = (y1 + y2) / 2

            # Check if any existing SHARKS are close to the current detection
            for id_, (prev_x, prev_y) in SHARKS.items():
                distance = calculate_distance_between_objects(
                    shark_box_x, shark_box_y, prev_x, prev_y)
                if distance < 200:  # Assuming a threshold of 200 pixels for proximity add a global variable to set this?
                    shark_id = id_
                    break

            # If no existing shark is close, assign a new ID
            if shark_id is None:
                shark_id = len(SHARKS) + 1

            SHARKS[shark_id] = (shark_box_x, shark_box_y)
            print(
                f"Shark {shark_id} Box Location ({shark_box_x}, {shark_box_y})")

            cv2.rectangle(resized_frame, (int(x1), int(y1)),
                          (int(x2), int(y2)), (0, 255, 0), 2)
            cv2.putText(resized_frame, f'{detection_type} {shark_id}: {conf:.2f}', (int(x1), int(y1) - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            found_shark = True  # Set found_shark to True whenever a shark is detected

        elif cls == 2 and conf > person_threshold:
            detection_type = "Person"
            cv2.rectangle(resized_frame, (int(x1), int(y1)),
                          (int(x2), int(y2)), (0, 255, 0), 2)
            cv2.putText(resized_frame, f'{detection_type}: {conf:.2f}', (int(x1), int(y1) - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            person_box_x = (x1 + x2) / 2
            person_box_y = (y1 + y2) / 2
            persons.append((person_box_x, person_box_y))
            found_person = True

        elif cls == 3 and conf > boat_threshold:
            detection_type = "Boat"
            cv2.rectangle(resized_frame, (int(x1), int(y1)),
                          (int(x2), int(y2)), (0, 255, 0), 2)
            cv2.putText(resized_frame, f'{detection_type}: {conf:.2f}', (int(x1), int(y1) - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        elif cls == 4 and conf > other_threshold:
            detection_type = "Other Animal"
            cv2.rectangle(resized_frame, (int(x1), int(y1)),
                          (int(x2), int(y2)), (0, 255, 0), 2)
            cv2.putText(resized_frame, f'{detection_type}: {conf:.2f}', (int(x1), int(y1) - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    first_shark_location = SHARKS[1]
    shark_location_x = shark_location_y = 0
    alert = None
    if found_shark:
        shark_location_x, shark_location_y = normalize_location(
            first_shark_location)
        alert = SharkAlert.INFO
        if found_person:
            alert = update_alert_based_on_distance(
                (shark_location_x, shark_location_y), persons)

    cv2.imshow('Shark Detection', resized_frame)
    cv2.waitKey(1)
    vidcap.release()

    return [resized_frame, shark_location_x, shark_location_y, found_shark, alert]


def normalize_location(object_location):
    center_x = WIDTH / 2
    center_y = HEIGHT / 2
    box_x, box_y = object_location
    offset_x = box_x - center_x
    offset_y = -(box_y - center_y)

    # This would have to be calculated based off of the drone/camera altitude
    # Since I am using an existing video on to simulate the detection, I do not know the altitude at which the video was taken from.
    # Therefore, I cannot accurately calculate distance from the video pixels.
    # Based off the video, I am estimating 1" per pixel.
    inches_per_pixel = 0.1

    location_x = offset_x * inches_per_pixel
    location_y = offset_y * inches_per_pixel
    return (location_x, location_y)


DANGER_THRESHOLD = 30.0  # Distance threshold for danger (in feet)
WARNING_THRESHOLD = 45.0  # Distance threshold for warning (in feet)


def update_alert_based_on_distance(shark_location, persons):
    shark_location_x, shark_location_y = shark_location
    smallest_distance = sys.maxsize
    alert = None
    for person in persons:
        person_location_x, person_location_y = normalize_location(person)
        distance = calculate_distance_between_objects(
            person_location_x, person_location_y,shark_location_x, shark_location_y)
        if distance < smallest_distance:
            smallest_distance = distance
    if smallest_distance < DANGER_THRESHOLD:
        alert = SharkAlert.DANGER
    elif smallest_distance < WARNING_THRESHOLD:
        alert = SharkAlert.WARNING
    print(f"{alert.value}: There was a detected SHARK {smallest_distance} feet away from a detected PERSON." if alert is not None else "")
    return alert


def calculate_distance_between_objects(x1, y1, x2, y2):
    # Calculate Euclidean distance between two points
    return ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5


def notify_nearest_stand(drone_location, alert):
    smallest_distance = sys.maxsize
    smallest_stand = None
    for stand in lifeguard_stands:
        stand_location = (stand.latitude, stand.longitude)
        distance = great_circle(drone_location, stand_location)
        if distance < smallest_distance:
            smallest_distance = distance
            smallest_stand = stand
    print(
        f"Notifying this stand {smallest_stand.name}, which is {smallest_distance}m away from the detected shark")

    with open('../frontend/notification.txt', 'w') as file:
        file.write(f"{smallest_stand.name}, {smallest_stand.latitude}, {smallest_stand.longitude}, {distance}, {alert.value + ': ' if alert is not None else ''}")

    return (smallest_stand, smallest_distance)


def populate_life_guard_stands():
    # Initialize an empty list to store lifeguard stands
    lifeguard_stands = []

    with open("../frontend/lifeguard_stand_data.json") as f:
        lifeguard_stand_data = json.load(f)

    for stand in lifeguard_stand_data:
        lifeguard_stands.append(LifeGuardStand(
            name=stand["name"], latitude=stand["lat"], longitude=stand["lng"]))

    return lifeguard_stands


async def get_drone_position(drone):
    position = await drone.telemetry.position().__anext__()
    latitude = position.latitude_deg
    longitude = position.longitude_deg
    print(
        f"Drone Position Update: --- Latitude: {latitude} --- Longitude: {longitude}")
    return (latitude, longitude)


def speed_function(distance):
    # Current function: ln(2x+1) with no values exceeding 4
    speed = math.log(2 * distance + 1)
    if speed > 4:
        speed = 4
    return speed


if __name__ == "__main__":
    # Populate lifeguard stands
    lifeguard_stands = populate_life_guard_stands()

    # Print the details of each lifeguard stand
    for stand in lifeguard_stands:
        print(f"{stand.name}: Latitude {stand.latitude}, Longitude {stand.longitude}")
    asyncio.run(run())
