#!/usr/bin/env python3
# Author - Lukas DeLoach
import asyncio
import json
import math
import sys
import time
import tkinter as tk
from tkinter import *

import cv2
import torch
from geopy.distance import great_circle
from life_guard_stand import LifeGuardStand
from mavsdk import System
from mavsdk.offboard import (
    OffboardError,
    PositionGlobalYaw,
    PositionNedYaw,
    VelocityBodyYawspeed,
    VelocityNedYaw,
)
from PIL import Image, ImageTk

# Initial coordinates
initial_lat = 29.043192
initial_lng = -80.897632
print(sys.maxsize)
# Number of lifeguard stands to populate
num_stands = 10

# Determine the total number of frames in the video
video_file = '../images/shark.mp4'
vidcap = cv2.VideoCapture(video_file)
fps = 50
total_frames = int(vidcap.get(cv2.CAP_PROP_FRAME_COUNT))

# Calculate the duration of the video in seconds
video_duration_seconds = total_frames / fps  # Assuming 'fps' is the frame rate of the video

# Calculate the time interval between frames for 30 FPS
time_interval = 1 / 30  # seconds
WIDTH = 800
HEIGHT = 500
LAT = 29.043192
LNG = -80.897632

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


    # Go east out to ocean first
    print("-- Go 100m North, 0m East, -10m Down \
            within local coordinate system, Turn to face the North and Scan for Sharks")
    await drone.offboard.set_position_ned(
            PositionNedYaw(100.0, 120.0, -10.0, -15.0))
    await asyncio.sleep(10)
    await get_drone_position(drone)

    elapsed_time = 0
    initial_location = await update_location(elapsed_time)
    location_x= initial_location[1]
    location_y = initial_location[2]
    angle = 90 - math.degrees(math.atan2(location_y, location_x))

    print(f"-- Turn to face {angle}")
    await drone.offboard.set_velocity_ned(VelocityNedYaw(0.0, 0.0, 0.0, angle))
    await asyncio.sleep(2)
    input("Press Enter to continue...")

    # Calculate drone's distance from the point (Assumes starting at origin)
    distance = math.sqrt(location_x ** 2 + location_y ** 2)
    
    # Mark the halfway point from the destination
    half_distance = distance / 2

    # Change speed depending on the drone's distance from the point
    speed = speed_function(distance)
    await drone.offboard.set_velocity_body(VelocityBodyYawspeed(speed, 0.0, 0.0, 0.0))

    origin_x = 0
    origin_y = 0
    i = 0

    async for pos in drone.telemetry.position_velocity_ned():
        i += 1
        location = await update_location(i * fps)
        if location[0] is None and location[1] is None and location[2] is None and location[3] is None:
            break
        else:
            location_x = location[1]
            location_y = location[2]
            found_shark = location[3]
            point = location[4]
            distance = math.sqrt((origin_x + location_x - pos.position.east_m) ** 2 + (
                    origin_y + location_y - pos.position.north_m) ** 2)
            print(distance, "distance")
            speed = 0
            
            if found_shark:
                drone_location = await get_drone_position(drone)
                notify_nearest_stand(drone_location)
                if distance < half_distance:  # If less than halfway to the shark, slow down
                    print("Drone is very close to the shark -- slowing down.")
                    await drone.offboard.set_velocity_body(VelocityBodyYawspeed(speed, 0.0, 0.0, angle))
                else:  # If more than halfway, fly towards the shark
                  angle = 90-math.degrees(math.atan2(location_y, location_x))
                  half_distance = distance / 2
                  origin_x = pos.position.east_m
                  origin_y = pos.position.north_m
                  # Change speed depending on the drone's distance from the point
                  speed = speed_function(half_distance)
                  print(f"{location_y} compared to height {500}" )
                  if(point[1]<HEIGHT):
                    print(f"--- Moving up by 5m and facing towards {angle}")
                    await drone.offboard.set_velocity_ned(VelocityNedYaw(speed,0,0.0,angle))
                  elif(point[1]>HEIGHT):
                    print(f"--- Moving down by 5m and facing towards {angle}")
                    speed = -speed
                    await drone.offboard.set_velocity_ned(VelocityNedYaw(speed,0,0.0,angle))
                    
                  print(f"{location_x} compared to width {800}" )
                  if(point[0]<WIDTH):
                    print(f"--- Moving with a speed of {speed} towards the angle1 {angle}")
                    await drone.offboard.set_velocity_ned(VelocityNedYaw(speed,0,0,angle))

                  elif(point[0]>WIDTH):
                    print(f"Moving with a speed of {speed} towards the angle2 {angle}")
                    await drone.offboard.set_velocity_ned(VelocityNedYaw(speed,0,0,angle))

                distance = math.sqrt((origin_x + location_x - pos.position.east_m) ** 2 + (
						origin_y + location_y - pos.position.north_m) ** 2)
                half_distance = distance / 2
                print(f"Distance: {distance}, Half Way Distance: {half_distance}, Speed: {speed}")
            else:
                print("There was no shark found. Holding position")
                await drone.offboard.set_velocity_ned(VelocityNedYaw(0,0,0,-40))

    
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
    box_x = 0
    box_y = 0
    found_shark = False
    point = []

    # Draw bounding boxes on the resized frame
    for result in results_np:
        threshold = .35
        shark_threshold = .65
        detection_type = ""
        x1, y1, x2, y2, conf, cls = result
        if cls == 3 and conf >= shark_threshold:
            found_shark = True
            detection_type = "Shark"
            box_x = (x1+x2)/2
            box_y = (y1+y2)/2
            print(f"Shark Box Location ({box_x, box_y})")
            point = [int(x1+(x2/2)), int((y1+(y2/2)))] ## Center of the Bounding box where the shark is could use this or other??
            cv2.rectangle(resized_frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
            cv2.putText(resized_frame, f'{detection_type}: {conf:.2f}', (int(x1), int(y1) - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        elif cls == 2 and conf > .50:
            detection_type = "Person"
            cv2.rectangle(resized_frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
            cv2.putText(resized_frame, f'{detection_type}: {conf:.2f}', (int(x1), int(y1) - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        elif cls == 3 and conf > .70:
            detection_type = "Boat"
            cv2.rectangle(resized_frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
            cv2.putText(resized_frame, f'{detection_type}: {conf:.2f}', (int(x1), int(y1) - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        

    center_x = WIDTH / 2
    center_y = HEIGHT / 2

    # Find the distance of the box from the center
    offset_x = box_x - center_x
    offset_y = -(box_y - center_y)
    print(f"offset is")
    print(f"Horizontal distance from image center: {offset_x}")
    print(f"Vertical distance from image center: {offset_y}")   
    meters_per_pixel = 0.1
    location_x = offset_x * meters_per_pixel
    location_y = offset_y * meters_per_pixel

    print(f"Location ({location_x, location_y})")
    cv2.imshow('Shark Detection', resized_frame)
    cv2.waitKey(1)
    vidcap.release()

    return [resized_frame, location_x, location_y, found_shark, point]


def notify_nearest_stand(drone_location):
    print(sys.maxsize)
    smallest_distance = sys.maxsize
    smallest_stand = None
    for stand in lifeguard_stands:
        stand_location = (stand.latitude, stand.longitude)
        distance = great_circle(drone_location, stand_location)
        if distance < smallest_distance:
            smallest_distance = distance
            smallest_stand = stand
    print(f"Notifying this stand {smallest_stand.name}, which is {smallest_distance} away from the detected shark")

    with open('../frontend/notification.txt', 'w') as file:
        file.write(f"{smallest_stand.name}, {smallest_stand.latitude}, {smallest_stand.longitude}, {distance}")

    return (smallest_stand, smallest_distance)

        

def populate_life_guard_stands():
    # Initialize an empty list to store lifeguard stands
    lifeguard_stands = []

    with open("../frontend/lifeguard_stand_data.json") as f:
        lifeguard_stand_data = json.load(f)
    
    for stand in lifeguard_stand_data:
        lifeguard_stands.append(LifeGuardStand(name=stand["name"], latitude=stand["lat"], longitude=stand["lng"]))

    return lifeguard_stands

async def get_drone_position(drone):
    position = await drone.telemetry.position().__anext__()
    latitude = position.latitude_deg
    longitude = position.longitude_deg
    print("Latitude:", latitude)
    print("Longitude:", longitude)
    return (latitude, longitude)


def speed_function(distance):
    # Current function: ln(2x+1) with no values exceeding 4
    speed = math.log(2 * distance + 1)
    if speed > 3:
        speed = 3
    return speed


if __name__ == "__main__":
    # Populate lifeguard stands
    lifeguard_stands = populate_life_guard_stands()

    # Print the details of each lifeguard stand
    for stand in lifeguard_stands:
        print(f"{stand.name}: Latitude {stand.latitude}, Longitude {stand.longitude}")
    asyncio.run(run())