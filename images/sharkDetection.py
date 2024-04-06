import torch 
import ssl
image = './image.png'
ssl._create_default_https_context = ssl._create_unverified_context
model = torch.hub.load('ultralytics/yolov5', 'custom', 'yolov5/runs/train/shark_detection/weights/best.pt',  force_reload=True)

results = model(image)
results_np = results.xyxy[0].numpy()

print(results_np)

