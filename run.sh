#!/bin/bash

# Function to clean up background processes if the script exits
cleanup() {
    echo "Stopping all processes..."
    kill $(jobs -p)
}

# Function to check for an active internet connection
check_internet() {
    echo "Checking for an internet connection..."
    while ! ping -q -c 1 -W 1 8.8.8.8 >/dev/null; do
        echo "No internet connection detected. Waiting..."
        sleep 60  # Wait and recheck after 60 seconds
    done
    echo "Internet connection detected. Continuing execution."
}

# Function to fetch changes from GitHub
fetch_changes_and_update_requirements() {
    check_internet
    echo "Fetching changes from GitHub..."
    git fetch --all
    git pull origin main  # Change 'main' to your default branch if different

    $python_version -m pip install -r "assets/requirements.txt"
}

# Function to start a script and auto-restart on failure
start_script() {
    local script_name=$1
    local python_version=$2

    while true; do
        check_internet  # Ensure there is an internet connection before starting the script
        echo "Starting $script_name..."
        $python_version $script_name

        if [ $? -ne 0 ]; then
            echo "$script_name failed. Waiting and Restarting..."
            sleep 60
        fi

        # After the script fails, check again if there is an internet connection
        check_internet
    done
}

# Trap script exit to run cleanup
trap cleanup EXIT

# Check if an argument is provided for the Python version
if [ -z "$1" ]; then
    echo "No argument provided. Using default Python version."
    python_version="python"
else
    echo "Using: $1"
    python_version="$1"
fi

# Fetch changes from GitHub
fetch_changes

# Start scripts and auto-restart on failure
start_script "main.py" $python_version &
start_script "discord_bot.py" $python_version &

# Wait for all background processes to finish
wait
