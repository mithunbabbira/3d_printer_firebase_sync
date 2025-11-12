# Quick Setup Guide

## Step-by-Step Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Up Firebase Service Account Key

**Option A: Download from Firebase Console (Recommended)**

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Select your project (or create a new one)
3. Click the gear icon ⚙️ next to "Project Overview"
4. Go to **Project Settings** > **Service Accounts** tab
5. Click **Generate New Private Key**
6. A JSON file will download (e.g., `your-project-firebase-adminsdk-xxxxx.json`)

7. **Save the file:**
   ```bash
   # Create the directory if it doesn't exist
   mkdir -p firebase_credentials
   
   # Move the downloaded file to the correct location
   # Replace 'downloaded-file.json' with your actual downloaded filename
   mv ~/Downloads/your-project-firebase-adminsdk-xxxxx.json firebase_credentials/serviceAccountKey.json
   ```

**Option B: Copy/Paste JSON Content**

If you already have the JSON content:

1. Create the directory:
   ```bash
   mkdir -p firebase_credentials
   ```

2. Create the file and paste the JSON:
   ```bash
   # On Mac/Linux
   nano firebase_credentials/serviceAccountKey.json
   # Or use any text editor
   ```

3. Paste the entire JSON content (it should start with `{` and end with `}`)
4. Save the file

**Important:** The file must be valid JSON and saved as `firebase_credentials/serviceAccountKey.json`

### 3. Enable Firestore Database

1. In Firebase Console, go to **Firestore Database**
2. Click **Create Database**
3. Choose your security mode:
   
   **Option A: Start in test mode** (Recommended for initial setup)
   - ✅ Allows read/write access for 30 days (good for testing)
   - ✅ Quick setup, no security rules to configure initially
   - ⚠️ **Important:** After 30 days, you MUST set up proper security rules
   - ⚠️ Not secure for production - anyone with your database URL can read/write
   
   **Option B: Start in production mode** (Recommended for production)
   - ✅ More secure from the start
   - ✅ Requires setting up security rules immediately
   - ⚠️ You need to configure rules before the app can write data
   
   **For this project:** Start with **test mode** to get it working quickly, then set up proper security rules later.
   
4. Select a location for your database (choose closest to you)
5. Click **Enable**

### 4. Create Configuration File

```bash
# Copy the template
cp env.template .env

# Edit the .env file with your settings
nano .env
# Or use any text editor
```

Edit `.env` with your values:

```env
# Moonraker WebSocket Configuration
MOONRAKER_WS_URL=ws://printer.local/websocket

# Firebase Configuration
FIREBASE_PROJECT_ID=your-actual-project-id
FIREBASE_SERVICE_ACCOUNT_KEY=firebase_credentials/serviceAccountKey.json
FIRESTORE_COLLECTION=printer_status

# Optional: Logging Level (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=INFO
```

**To find your Firebase Project ID:**
- Go to Firebase Console
- Click the gear icon ⚙️ > **Project Settings**
- Your **Project ID** is shown at the top (e.g., `my-printer-dashboard-12345`)

### 5. Test the Setup (Optional)

Test connectivity to your printer:

```bash
python explore_moonraker_api.py
```

This will verify:
- ✅ Printer is accessible
- ✅ Firebase credentials are valid (if you've set them up)

### 6. Run the Application

```bash
python main.py
```

You should see output like:
```
2024-01-01 12:00:00 - __main__ - INFO - Starting Moonraker to Firebase sync...
2024-01-01 12:00:00 - __main__ - INFO - Configuration validated
2024-01-01 12:00:00 - __main__ - INFO - Firebase initialized
2024-01-01 12:00:00 - moonraker_client - INFO - Connecting to Moonraker at ws://printer.local/websocket
2024-01-01 12:00:00 - moonraker_client - INFO - Connected to Moonraker WebSocket
2024-01-01 12:00:00 - moonraker_client - INFO - Subscribed to printer status updates
```

## Troubleshooting

### "Firebase service account key not found"
- Make sure the file exists at: `firebase_credentials/serviceAccountKey.json`
- Check the file path in `.env` matches the actual file location
- Verify the file is valid JSON (open it and check it starts with `{`)

### "FIREBASE_PROJECT_ID is required"
- Make sure you created a `.env` file
- Check that `FIREBASE_PROJECT_ID` is set in `.env`
- Get your Project ID from Firebase Console > Project Settings

### "Could not connect to Moonraker"
- Verify your printer is accessible at `http://printer.local`
- Try accessing it in a browser first
- Check if Moonraker is running on your Raspberry Pi
- You might need to use the IP address instead: `ws://192.168.1.XXX/websocket`

### "Permission denied" or Firebase errors
- Make sure Firestore is enabled in Firebase Console
- Check that the service account has proper permissions
- Verify the JSON key file is not corrupted

## File Structure

After setup, your directory should look like:

```
dashboard_data_sync/
├── .env                          # Your configuration (create this)
├── firebase_credentials/
│   └── serviceAccountKey.json    # Firebase key (download this)
├── main.py
├── moonraker_client.py
├── firebase_sync.py
├── config.py
├── requirements.txt
└── ... (other files)
```

## Next Steps

Once running successfully:
1. Check Firebase Firestore Console
2. Look for the `printer_status` collection
3. You should see a document named `current` with your printer data
4. The data will update in real-time as your printer status changes

