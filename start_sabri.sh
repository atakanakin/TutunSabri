#!/bin/bash

# Navigate to the project directory
cd /home/atakan/Documents/Projects/TutunSabri/

# Start tmux session
tmux new-session -d -s sabri

# Execute wrapper script - this will start the bot - python wrapper.py
tmux send-keys -t sabri "python wrapper.py" C-m