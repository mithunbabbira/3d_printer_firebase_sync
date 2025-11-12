# Moonraker to Firebase Real-Time Data Sync

This application syncs real-time 3D printer status data from Moonraker (running on Raspberry Pi with Klipper) to Firebase Firestore.

## Features

- Real-time WebSocket connection to Moonraker
- Automatic reconnection with exponential backoff
- Syncs printer status to Firebase Firestore:
  - Bed and extruder temperatures (actual and target)
  - Print statistics (state, duration, filename, progress, time remaining)
  - Heater power levels
  - Display status (if available)

## Prerequisites

- Python 3.8 or higher
- Raspberry Pi 4 running Klipper and Moonraker
- Firebase project with Firestore enabled
- Firebase service account key (JSON file)

## Installation

1. Clone or download this repository

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up Firebase:
   - Create a Firebase project at [Firebase Console](https://console.firebase.google.com/)
   - Enable Firestore Database
   - Go to Project Settings > Service Accounts
   - Generate a new private key and download the JSON file
   - Save the JSON file as `firebase_credentials/serviceAccountKey.json`

4. Configure the application:
   - Copy `env.template` to `.env`
   - Edit `.env` with your configuration:
     ```
     MOONRAKER_WS_URL=ws://printer.local/websocket
     FIREBASE_PROJECT_ID=your-project-id
     FIREBASE_SERVICE_ACCOUNT_KEY=firebase_credentials/serviceAccountKey.json
     FIRESTORE_COLLECTION=printer_status
     LOG_LEVEL=INFO
     ```

## Usage

### Step 1: Explore Available APIs (Optional but Recommended)

Before running the main sync, you can explore what data is available from your printer:

```bash
python explore_moonraker_api.py
```

This script will:
- Test connectivity to your printer
- Show all available API endpoints
- Display current printer status and data structures
- Help you understand what data is available for syncing

### Step 2: Run the Main Sync Application

Run the application:
```bash
python main.py
```

The application will:
1. Connect to Moonraker WebSocket
2. Subscribe to printer status updates
3. Sync all updates to Firebase Firestore in real-time

## Firestore Data Structure

The application creates/updates a document at `printer_status/current` with the following structure:

```json
{
  "timestamp": "2024-01-01T12:00:00Z",
  "temperatures": {
    "bed": {"actual": 60.0, "target": 60.0},
    "extruder": {"actual": 210.0, "target": 210.0}
  },
  "print_stats": {
    "state": "printing",
    "print_duration": 3600,
    "filename": "model.gcode",
    "progress": 45.5,
    "time_remaining": 1800
  },
  "heater_bed": {"power": 0.5, "target": 60.0},
  "extruder": {"power": 0.8, "target": 210.0}
}
```

## Configuration

### Environment Variables

- `MOONRAKER_WS_URL`: WebSocket URL for Moonraker (default: `ws://printer.local/websocket`)
- `FIREBASE_PROJECT_ID`: Your Firebase project ID (required)
- `FIREBASE_SERVICE_ACCOUNT_KEY`: Path to Firebase service account JSON key (default: `firebase_credentials/serviceAccountKey.json`)
- `FIRESTORE_COLLECTION`: Firestore collection name (default: `printer_status`)
- `LOG_LEVEL`: Logging level - DEBUG, INFO, WARNING, ERROR (default: `INFO`)

## Running as a Service

To run the application as a systemd service on Raspberry Pi:

1. Create a service file `/etc/systemd/system/moonraker-sync.service`:
```ini
[Unit]
Description=Moonraker to Firebase Sync
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/path/to/dashboard_data_sync
ExecStart=/usr/bin/python3 /path/to/dashboard_data_sync/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

2. Enable and start the service:
```bash
sudo systemctl enable moonraker-sync.service
sudo systemctl start moonraker-sync.service
```

3. Check status:
```bash
sudo systemctl status moonraker-sync.service
```

## Troubleshooting

### Connection Issues

- Verify Moonraker is running and accessible at the configured URL
- Check firewall settings on Raspberry Pi
- Ensure WebSocket endpoint is correct (usually `/websocket`)

### Firebase Issues

- Verify service account key file exists and is valid
- Check Firebase project ID is correct
- Ensure Firestore is enabled in Firebase Console
- Check service account has Firestore write permissions

### Logging

Set `LOG_LEVEL=DEBUG` in `.env` for detailed logging to troubleshoot issues.

## License

This project is provided as-is for personal use.

