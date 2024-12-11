#!/bin/bash

# Add a delay of 10 seconds because my little raspi tidin tidin -goes crazy- on startup
sleep 10

# Navigate to the project directory
cd /home/atakan/Documents/Projects/TutunSabri/

# Start tmux session
tmux new-session -d -s sabri /bin/bash

# Execute main script - this will start the bot - python main.py
tmux send-keys -t sabri "echo 'Starting...'; python main.py; echo 'Terminated'; sleep 5; echo 'Trying again'; python main.py; sleep 5; sudo reboot" C-m
