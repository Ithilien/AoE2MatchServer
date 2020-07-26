#!/bin/sh

# Runs flask server for AoE2 match maker

export API_KEY="AIzaSyD4HDVH2uD8lLTwK29fVRJUi0MFhhGWld8"
export FLASK_APP=$PWD/aoe2_ms.py

flask run -p 5414 -h 0.0.0.0
