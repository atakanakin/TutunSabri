"""
This script takes a picture using the Raspberry Pi camera and saves it to the img_path.
Usage: python take_picture.py <img_path>
Example: python take_picture.py /home/pi/Desktop/selfie.jpg
"""
import sys
import picamera

img_path = sys.argv[1]

# Initialize the camera
camera = picamera.PiCamera()

# Capture a picture
camera.capture(img_path)

# Close the camera
camera.close()
