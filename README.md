# Drone Shark Detection and Lifeguard Assistance System

## Author

- **Lukas DeLoach** - [GitHub](https://github.com/lukasdeloach)

## Introduction

This Python project simulates a drone equipped with a camera to detect sharks in the ocean and assist lifeguards in managing potential dangers to swimmers.
The system employs object detection techniques to identify sharks and nearby individuals, and it calculates distances to determine alert levels for lifeguard assistance.

## Features

- **Shark Detection**: Utilizes YOLOv5 model for real-time shark detection in the video feed.
- **Object Detection**: Identifies persons, boats, and other animals in the vicinity.
- **Distance Calculation**: Calculates distances between sharks and individuals for determining alert levels.
- **Lifeguard Assistance**: Notifies the nearest lifeguard stand for appropriate action based on alert levels.

## Dependencies

- Python 3.x
- OpenCV
- PyTorch
- GeoPy
- MAVSDK

## Usage

1. Install the required dependencies by running `pip install -r requirements.txt`.
2. Install PX4 for your machine: https://docs.px4.io/main/en/dev_setup/dev_env.html
3. Start the MAVSDK server in terminal 1:
   ```bash
   mavsdk_server -p 50051
   ```
4. Open another terminal and in the PX4 folder run the command: `make px4_sitl jmavsim`
5. Ensure the drone is connected and ready for offboard control.
6. Navigate into the frontend folder, create a local server, and navigate to the webpage to view the lifeguard stand alert visualization:
   ```bash
   cd frontend/
   python3 -m http.server
   ```
8. Run the main script using `python drone_shark_detection.py`.
9. Monitor the console for real-time updates on shark detection and lifeguard assistance.

## Configuration

- This project was based out of New Smyrna Beach Florida. The lifguard visualization is a picture from the beaches of NSB.
- In order to visualize the drone flying along the stretches of this beach:
  1. Download QGroundControl: https://qgroundcontrol.com/
  2. In the PX4 Folder, set the PX4 home location parameters before running the SITL simulator (The Lat and Lng parameters are a point on NSB):
     ```bash
     export PX4_HOME_LAT=29.043192
     export PX4_HOME_LON=-80.897632
     export PX4_HOME_ALT=0
     ```

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.


## Acknowledgments

Special thanks to the contributors and maintainers of the YOLOv5 model and the MAVSDK library for enabling drone-based object detection and control.
