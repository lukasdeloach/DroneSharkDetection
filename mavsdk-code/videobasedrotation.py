#!/usr/bin/env python3

import math

import asyncio
from mavsdk import System
from mavsdk.offboard import (OffboardError, PositionNedYaw, VelocityBodyYawspeed, VelocityNedYaw, PositionGlobalYaw)
import geopy.distance
from life_guard_stand import LifeGuardStand

# Initial coordinates
initial_lat = 29.043192
initial_lng = -80.897632

# Number of lifeguard stands to populate
num_stands = 10
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
            PositionNedYaw(0.0, 0.0, -5.0, 80.0))
    await asyncio.sleep(5)
    await print_lat_lng(drone)
    
    print("-- Go 0m North, 7500m East, -5m Down \
            within local coordinate system, Turn to face the north")
    await drone.offboard.set_position_ned(
            PositionNedYaw(0.0, 7500.0, -5.0, 80.0))
    await asyncio.sleep(17)
    await print_lat_lng(drone)
    print("-- Go 10000m North, 0m East, -5m Down \
            within local coordinate system, turn to face east.")
    await drone.offboard.set_position_ned(
            PositionNedYaw(100000000000.0, 0, -5.0, 0.0))
    await asyncio.sleep(100)
    await print_lat_lng(drone)
   

    # print("-- Go 0m North, 200m East, -5m Down \
    #         within local coordinate system, turn to face North.")
    # await drone.offboard.set_position_ned(
    #         PositionNedYaw(0, 5000, -5.0, 0.0))
    # await asyncio.sleep(10)
    # await print_lat_lng(drone)
         

    print("-- Stopping offboard")
    try:
        await drone.offboard.stop()
    except OffboardError as error:
        print(f"Stopping offboard mode failed \
                with error code: {error._result.result}")
        

async def print_lat_lng(drone):
    position = await drone.telemetry.position().__anext__()
    latitude = position.latitude_deg
    longitude = position.longitude_deg
    print("Latitude:", latitude)
    print("Longitude:", longitude)	


if __name__ == "__main__":
    # Run the asyncio loop
    asyncio.run(run())

