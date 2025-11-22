# Deployment Guide for Raspberry Pi

This guide provides step-by-step instructions to deploy the **Moonraker to Firebase Sync** application on a Raspberry Pi and configure it to run automatically on boot.

## Prerequisites

-   Raspberry Pi running Raspberry Pi OS (or similar Linux distro).
-   Internet connection.
-   `git` installed.
-   Python 3.8 or higher.
-   Root/Sudo access.

## Step 1: Prepare the Environment

1.  **Update your system:**
    ```bash
    sudo apt update && sudo apt upgrade -y
    ```

2.  **Install system dependencies:**
    ```bash
    sudo apt install -y git python3 python3-pip python3-venv
    ```

## Step 2: Clone the Repository

1.  **Navigate to your projects directory:**
    ```bash
    cd /home/pi
    mkdir -p projects
    cd projects
    ```

2.  **Clone the repository:**
    ```bash
    git clone https://github.com/mithunbabbira/3d_printer_firebase_sync.git
    cd 3d_printer_firebase_sync
    ```

## Step 3: Set Up Python Environment

1.  **Create a virtual environment:**
    ```bash
    python3 -m venv venv
    ```

2.  **Activate the virtual environment:**
    ```bash
    source venv/bin/activate
    ```

3.  **Install Python dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Step 4: Configuration

1.  **Environment Variables:**
    -   Copy the template:
        ```bash
        cp env.template .env
        ```
    -   Edit `.env`:
        ```bash
        nano .env
        ```
    -   Update the values:
        -   `MOONRAKER_WS_URL`: Usually `ws://localhost/websocket` or `ws://printer.local/websocket`.
        -   `FIREBASE_PROJECT_ID`: Your Firebase Project ID.
        -   `WHATSAPP_API_URL`: Your local WhatsApp API endpoint (e.g., `http://localhost:3001/send`).

2.  **Firebase Credentials:**
    -   Create the directory:
        ```bash
        mkdir -p firebase_credentials
        ```
    -   **Securely transfer** your `serviceAccountKey.json` to this directory.
    -   Path should be: `/home/pi/projects/3d_printer_firebase_sync/firebase_credentials/serviceAccountKey.json`

## Step 5: Run as a Service (Auto-start on Boot)

1.  **Create a systemd service file:**
    ```bash
    sudo nano /etc/systemd/system/moonraker-sync.service
    ```

2.  **Paste the following configuration:**
    *(Adjust paths if your username is not `pi` or you cloned it elsewhere)*

    ```ini
    [Unit]
    Description=Moonraker to Firebase Sync Service
    After=network-online.target
    Wants=network-online.target

    [Service]
    Type=simple
    User=pi
    WorkingDirectory=/home/pi/projects/3d_printer_firebase_sync
    # Use the python executable from the virtual environment
    ExecStart=/home/pi/projects/3d_printer_firebase_sync/venv/bin/python main.py
    Restart=always
    RestartSec=10
    
    # Environment variables can be set here or loaded from .env by the app
    # Environment=PYTHONUNBUFFERED=1

    [Install]
    WantedBy=multi-user.target
    ```

3.  **Reload systemd daemon:**
    ```bash
    sudo systemctl daemon-reload
    ```

4.  **Enable the service to start on boot:**
    ```bash
    sudo systemctl enable moonraker-sync.service
    ```

5.  **Start the service immediately:**
    ```bash
    sudo systemctl start moonraker-sync.service
    ```

## Step 6: Verification

1.  **Check service status:**
    ```bash
    sudo systemctl status moonraker-sync.service
    ```
    You should see `Active: active (running)`.

2.  **View logs:**
    ```bash
    journalctl -u moonraker-sync.service -f
    ```

## Maintenance

-   **Stop the service:** `sudo systemctl stop moonraker-sync.service`
-   **Restart the service:** `sudo systemctl restart moonraker-sync.service`
-   **Update code:**
    ```bash
    cd /home/pi/projects/3d_printer_firebase_sync
    git pull
    sudo systemctl restart moonraker-sync.service
    ```
