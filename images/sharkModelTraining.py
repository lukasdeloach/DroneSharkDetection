from PIL import Image
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from inference_sdk import InferenceHTTPClient

# Initialize InferenceHTTPClient
CLIENT = InferenceHTTPClient(
    api_url="https://detect.roboflow.com",
    api_key="KKa6U3olUUcxXpaykO7j"
)

# Load the image
image_path = "image copy.png"
image = Image.open(image_path)

# Perform inference
result = CLIENT.infer(image_path, model_id="shark-detection-z5b2z/3")
print(result)

# Display the image
plt.imshow(image)
ax = plt.gca()

# Draw bounding boxes on the image
for bounding_box in result['predictions']:
    x = bounding_box['x']
    y = bounding_box['y']
    width = bounding_box['width']
    height = bounding_box['height']
    confidence = bounding_box['confidence']
    # Create a Rectangle patch
    rect = patches.Rectangle((x - width/2, y - height/2), width, height, linewidth=4, edgecolor='g', facecolor='none' )
    # Add the patch to the Axes
    ax.add_patch(rect)
    # Add confidence as text
    ax.text(x, y - height/2 - 10, f"Confidence: {confidence:.2f}", color='g', fontsize=14, ha='center', fontweight='bold')

plt.show()
