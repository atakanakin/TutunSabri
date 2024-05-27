#!/bin/bash

# Add a delay of 10 seconds because my little raspi tidin tidin -goes crazy- on startup
sleep 10

# Navigate to the project directory
cd /home/atakan/Documents/Projects/TutunSabri/

# Start tmux session
tmux new-session -d -s sabri

# Execute wrapper script - this will start the bot - python wrapper.py
tmux send-keys -t sabri "echo 'Starting...' ; python wrapper.py ; echo 'Terminated' ; echo 'Restarting connection...' ; sudo systemctl restart NetworkManager ; sleep 5; echo 'Trying again' ; python wrapper.py ; sleep 5 ; sudo reboot" C-m