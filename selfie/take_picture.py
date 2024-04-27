import sys
import picamera

img_path = sys.argv[1]

# Initialize the camera
camera = picamera.PiCamera()

# Capture a picture
camera.capture(img_path)

# Close the camera
camera.close()
