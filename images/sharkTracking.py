import cv2
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from inference_sdk import InferenceHTTPClient

# Initialize InferenceHTTPClient
CLIENT = InferenceHTTPClient(
    api_url="https://detect.roboflow.com",
    api_key="KKa6U3olUUcxXpaykO7j"
)

# Load the video
video_path = "Screen Recording 2024-03-25 at 10.18.14 PM.mov"  # Change to your video file path
cap = cv2.VideoCapture(video_path)

# Get the video properties
frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fps = int(cap.get(cv2.CAP_PROP_FPS))
frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

# Define the codec and create VideoWriter object
out = cv2.VideoWriter('output_video.mp4', cv2.VideoWriter_fourcc(*'mp4v'), fps, (frame_width, frame_height))

# Loop through each frame of the video
while True:
    ret, frame = cap.read()
    if not ret:
        break  # Break the loop if no frame is returned

    # Perform inference
    result = CLIENT.infer(frame, model_id="shark-detection-z5b2z/3")

    # Draw bounding boxes on the frame
    for bounding_box in result['predictions']:
        x = int(bounding_box['x'])
        y = int(bounding_box['y'])
        width = int(bounding_box['width'])
        height = int(bounding_box['height'])
        confidence = bounding_box['confidence']

        # Draw bounding box
        cv2.rectangle(frame, (x - width//2, y - height//2), (x + width//2, y + height//2), (0, 255, 0), 2)

        # Add confidence as text
        cv2.putText(frame, f"Confidence: {confidence:.2f}", (x, y - height//2 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    # Write the frame into the output video
    out.write(frame)

    # Display the frame
    cv2.imshow('Frame', frame)
    
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Release everything if job is finished
cap.release()
out.release()
cv2.destroyAllWindows()
