"""Configuration management for Moonraker to Firebase sync."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Application configuration."""
    
    # Moonraker WebSocket Configuration
    MOONRAKER_WS_URL = os.getenv(
        "MOONRAKER_WS_URL",
        "ws://printer.local/websocket"
    )
    
    # Firebase Configuration
    FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID")
    FIREBASE_SERVICE_ACCOUNT_KEY = os.getenv(
        "FIREBASE_SERVICE_ACCOUNT_KEY",
        "firebase_credentials/serviceAccountKey.json"
    )
    FIRESTORE_COLLECTION = os.getenv(
        "FIRESTORE_COLLECTION",
        "printer_status"
    )
    
    # Logging Configuration
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    @classmethod
    def validate(cls):
        """Validate that required configuration is present."""
        errors = []
        
        if not cls.FIREBASE_PROJECT_ID:
            errors.append("FIREBASE_PROJECT_ID is required")
        
        service_account_path = Path(cls.FIREBASE_SERVICE_ACCOUNT_KEY)
        if not service_account_path.exists():
            errors.append(
                f"Firebase service account key not found: {service_account_path}"
            )
        
        if errors:
            raise ValueError("Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors))
        
        return True

