#!/usr/bin/env python3
# Author - Lukas DeLoach
import math

import asyncio
from mavsdk import System
from mavsdk.offboard import (OffboardError, PositionNedYaw, VelocityBodyYawspeed, VelocityNedYaw, PositionGlobalYaw)
import geopy.distance
from life_guard_stand import LifeGuardStand
import torch
import cv2
from PIL import Image
import tkinter
from tkinter import *
from PIL import Image, ImageTk

# Initial coordinates
initial_lat = 29.043192
initial_lng = -80.897632
# Number of lifeguard stands to populate
num_stands = 10

# Determine the total number of frames in the video
vidcap = cv2.VideoCapture('../images/shark.mp4')
fps = 30
total_frames = int(vidcap.get(cv2.CAP_PROP_FRAME_COUNT))

# Calculate the duration of the video in seconds
video_duration_seconds = total_frames / fps  # Assuming 'fps' is the frame rate of the video

# Calculate the time interval between frames for 30 FPS
time_interval = 1 / 30  # seconds
print(video_duration_seconds)

model = torch.hub.load('ultralytics/yolov5', 'custom', path='../best.pt')


async def run():
    """ Does Offboard control using position NED coordinates. """
    

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
    
    lat = 29.043192
    lng = -80.897632
    
    print("-- Setting initial setpoint")
    await drone.offboard.set_position_global(PositionGlobalYaw(lat, lng, 0.0, 0.0, PositionGlobalYaw.AltitudeType(0)))
    await print_lat_lng(drone)

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
            PositionNedYaw(0.0, 0.0, -10.0, 80.0))
    await asyncio.sleep(8)
    await print_lat_lng(drone)

    # Go east out to ocean first
    print("-- Go 0m North, 7500m East, -5m Down \
            within local coordinate system, Turn to face the north")
    await drone.offboard.set_position_ned(
            PositionNedYaw(0.0, 7500.0, -10.0, 80.0))
    await asyncio.sleep(12)
    await print_lat_lng(drone)

    elapsed_time = 0
    initial_location = await update_location(elapsed_time)
    drone_latitude = initial_location[1]
    drone_longitude = initial_location[2]
    print()
    angle = 90+math.degrees(math.atan2(drone_latitude, drone_longitude))

    print(f"-- Turn to face {angle}")
    await drone.offboard.set_velocity_ned(VelocityNedYaw(0.0, 0.0, 0.0, angle))
    await asyncio.sleep(2)
    input("Press Enter to continue...")

    # Calculate drone's distance from the point (Assumes starting at origin)
    distance = math.sqrt(initial_location[1] ** 2 + initial_location[2] ** 2)
    
    # Mark the halfway point from the destination
    half_distance = distance / 2

    # Change speed depending on the drone's distance from the point
    speed = speed_function(distance)
    await drone.offboard.set_velocity_body(VelocityBodyYawspeed(speed, 0.0, 0.0, 0.0))

    for i in range(int(video_duration_seconds*30)):
       initial_location = await update_location(int(i*fps))
       drone_latitude = initial_location[1]
       drone_longitude = initial_location[2]
       angle = 90+math.degrees(math.atan2(drone_latitude, drone_longitude))
       print(f"-- Turn to face {angle}")
       await drone.offboard.set_velocity_ned(VelocityNedYaw(0.0, 0.0, 0.0, angle))
       await asyncio.sleep(1)
       distance = math.sqrt(initial_location[1] ** 2 + initial_location[2] ** 2)
       half_distance = distance / 2
       speed = speed_function(distance)
       await drone.offboard.set_velocity_body(VelocityBodyYawspeed(speed, 0.0, 0.0, 0.0))
       await asyncio.sleep(1)
         

    print("-- Stopping offboard")
    try:
        await drone.offboard.stop()
    except OffboardError as error:
        print(f"Stopping offboard mode failed \
                with error code: {error._result.result}")
        

async def update_location(time_passed):
    vidcap = cv2.VideoCapture('../images/shark.mp4')
    height = vidcap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    width = vidcap.get(cv2.CAP_PROP_FRAME_WIDTH)
    vidcap.set(cv2.CAP_PROP_POS_MSEC, time_passed)
    height = vidcap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    width = vidcap.get(cv2.CAP_PROP_FRAME_WIDTH)
    success, frame = vidcap.read()
    if not success:
        print("Video ended")
        return None, None, None  # Return None if video ended

    # Perform object detection on the frame
    results = model(frame)
    results_np = results.xyxy[0].numpy()
    box_x = 0
    box_y = 0

    # Draw bounding boxes on the frame
    for result in results_np:
        threshold = .35
        detection_type = ""
        x1, y1, x2, y2, conf, cls = result
        if cls == 3:
            detection_type = "Shark"
            threshold = .70
            box_x = (x1+x2)/2
            box_y = (y1+y2)/2
            print(f"Shark Box Location ({box_x, box_y})")
        elif cls == 2:
            detection_type = "Person"
        
        if conf > threshold:
            cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
            cv2.putText(frame, f'{detection_type}: {conf:.2f}', (int(x1), int(y1) - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    center_x = width / 2
    center_y = height / 2

    # Find the distance of the box from the center
    offset_x = box_x - center_x
    offset_y = -(box_y - center_y)
    print(f"Horizontal distance from image center: {offset_x}")
    print(f"Vertical distance from image center: {offset_y}")   
    meters_per_pixel = 0.1
    location_x = offset_x * meters_per_pixel
    location_y = offset_y * meters_per_pixel
    print(f"Location ({location_x, location_y})")
    cv2.imshow('Frame', frame)
    cv2.waitKey(1)
    vidcap.release()


    return [frame, location_x, location_y]


def populate_life_guard_stands(initial_lat, initial_lng, num_stands):
    # Initialize an empty list to store lifeguard stands
    lifeguard_stands = []

    # Define the distance between lifeguard stands (in yards)
    distance_between_stands_yards = 50

    # Convert distance to meters for geopy.distance library
    distance_between_stands_meters = distance_between_stands_yards * 0.9144

    # Create the first lifeguard stand at the initial coordinates
    lifeguard_stands.append(LifeGuardStand(name="Lifeguard Stand 1", latitude=initial_lat, longitude=initial_lng))

    # Calculate and add subsequent lifeguard stands
    for i in range(2, num_stands + 1):
        # Calculate the coordinates of the next lifeguard stand
        next_point = geopy.distance.geodesic(meters=distance_between_stands_meters).destination((initial_lat, initial_lng), 90)
        next_lat = next_point.latitude
        next_lng = next_point.longitude

        # Create the lifeguard stand object and add it to the list
        lifeguard_stands.append(LifeGuardStand(name=f"Lifeguard Stand {i}", latitude=next_lat, longitude=next_lng))

        # Update initial coordinates for the next iteration
        initial_lat, initial_lng = next_lat, next_lng

    return lifeguard_stands
        
# Populate lifeguard stands
lifeguard_stands = populate_life_guard_stands(initial_lat, initial_lng, num_stands)

# Print the details of each lifeguard stand
for stand in lifeguard_stands:
    print(f"{stand.name}: Latitude {stand.latitude}, Longitude {stand.longitude}")

async def print_lat_lng(drone):
    position = await drone.telemetry.position().__anext__()
    latitude = position.latitude_deg
    longitude = position.longitude_deg
    print("Latitude:", latitude)
    print("Longitude:", longitude)


def speed_function(distance):
    # Current function: ln(2x+1) with no values exceeding 4
    speed = math.log(2 * distance + 1)
    if speed > 4:
        speed = 4
    return speed


if __name__ == "__main__":
    # Run the asyncio loop
    asyncio.run(run())