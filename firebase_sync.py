"""Firebase Firestore integration for syncing printer status."""
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Union
import firebase_admin
from firebase_admin import credentials, firestore
from config import Config

logger = logging.getLogger(__name__)


def round_value(value: Union[float, int], decimals: int = 2) -> Union[float, int]:
    """
    Round a numeric value to specified decimal places.
    
    Args:
        value: The value to round
        decimals: Number of decimal places (default: 2)
        
    Returns:
        Rounded value (returns int if decimals=0 and value is whole number)
    """
    if value is None:
        return None
    if isinstance(value, int):
        return value
    rounded = round(float(value), decimals)
    # Return as int if it's a whole number
    if decimals == 0 or rounded == int(rounded):
        return int(rounded)
    return rounded


class FirebaseSync:
    """Handles syncing printer status to Firebase Firestore."""
    
    def __init__(self):
        """Initialize Firebase Admin SDK."""
        self.db: Optional[firestore.Client] = None
        self._initialized = False
    
    def initialize(self):
        """Initialize Firebase Admin SDK."""
        if self._initialized:
            return
        
        try:
            # Check if Firebase app already exists
            try:
                firebase_admin.get_app()
                logger.info("Firebase app already initialized")
            except ValueError:
                # Initialize Firebase Admin SDK
                cred_path = Config.FIREBASE_SERVICE_ACCOUNT_KEY
                cred = credentials.Certificate(cred_path)
                
                firebase_admin.initialize_app(cred, {
                    'projectId': Config.FIREBASE_PROJECT_ID,
                })
                logger.info("Firebase Admin SDK initialized")
            
            # Get Firestore client
            self.db = firestore.client()
            self._initialized = True
            logger.info("Firestore client initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {e}")
            raise
    
    def transform_status_data(self, status_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform Moonraker status data to Firestore document format.
        
        Args:
            status_data: Raw status data from Moonraker
            
        Returns:
            Transformed data structure for Firestore
        """
        transformed = {}

        # Extract heater bed data
        # Only include if values are actually present (not None)
        if "heater_bed" in status_data:
            bed_heater = status_data["heater_bed"]
            if isinstance(bed_heater, dict):
                bed_data = {}
                # Only include fields that have actual values
                if "target" in bed_heater and bed_heater["target"] is not None:
                    bed_data["target"] = round_value(bed_heater["target"], 0)  # Whole numbers for targets
                if "temperature" in bed_heater and bed_heater["temperature"] is not None:
                    bed_data["temperature"] = round_value(bed_heater["temperature"], 1)  # 1 decimal for temps

                # Only add heater_bed if we have at least one valid value
                if bed_data:
                    transformed["heater_bed"] = bed_data
        
        # Extract extruder heater data if available
        if "heaters" in status_data:
            heaters = status_data["heaters"]
            if isinstance(heaters, dict):
                for heater_name, heater_data in heaters.items():
                    if "extruder" in heater_name.lower() or heater_name == "extruder":
                        if isinstance(heater_data, dict):
                            extruder_data = {}
                            # Only include fields that have actual values
                            if "target" in heater_data and heater_data["target"] is not None:
                                extruder_data["target"] = round_value(heater_data["target"], 0)  # Whole numbers for targets
                            if "temperature" in heater_data and heater_data["temperature"] is not None:
                                extruder_data["temperature"] = round_value(heater_data["temperature"], 1)  # 1 decimal for temps

                            # Only add extruder if we have at least one valid value
                            if extruder_data:
                                transformed["extruder"] = extruder_data
                            break

        # Also check for direct extruder object
        if "extruder" in status_data and "extruder" not in transformed:
            extruder_heater = status_data["extruder"]
            if isinstance(extruder_heater, dict):
                extruder_data = {}
                # Only include fields that have actual values
                if "target" in extruder_heater and extruder_heater["target"] is not None:
                    extruder_data["target"] = round_value(extruder_heater["target"], 0)  # Whole numbers for targets
                if "temperature" in extruder_heater and extruder_heater["temperature"] is not None:
                    extruder_data["temperature"] = round_value(extruder_heater["temperature"], 1)  # 1 decimal for temps

                # Only add extruder if we have at least one valid value
                if extruder_data:
                    transformed["extruder"] = extruder_data
        
        # Extract print stats
        if "print_stats" in status_data:
            print_stats = status_data["print_stats"]
            if isinstance(print_stats, dict):
                total_duration = print_stats.get("total_duration")
                print_duration = print_stats.get("print_duration", 0)
                time_remaining = None
                if total_duration is not None:
                    time_remaining = round_value(total_duration - print_duration, 0)  # Whole seconds

                transformed["print_stats"] = {
                    "state": print_stats.get("state", "unknown"),
                    "print_duration": round_value(print_duration, 1),  # 1 decimal for duration
                    "time_remaining": time_remaining
                }

        # Extract virtual_sdcard for file_size, filename, and progress
        if "virtual_sdcard" in status_data:
            sdcard = status_data["virtual_sdcard"]
            if isinstance(sdcard, dict):
                if "print_stats" not in transformed:
                    transformed["print_stats"] = {}

                # Get filename from virtual_sdcard (file_path field) - always set it
                file_path = sdcard.get("file_path") or ""
                transformed["print_stats"]["filename"] = file_path

                # Get progress directly from virtual_sdcard (already a percentage 0-1, convert to 0-100)
                progress = sdcard.get("progress", 0.0)
                if progress is not None:
                    transformed["print_stats"]["progress"] = round_value(progress * 100, 2)  # Convert 0-1 to 0-100

                # Get file size
                file_size = sdcard.get("file_size", 0)
                if file_size > 0:
                    transformed["print_stats"]["file_size"] = round_value(file_size, 0)
        
        # Extract display status if available
        if "display_status" in status_data:
            display = status_data["display_status"]
            if isinstance(display, dict):
                transformed["display_status"] = {
                    "progress": round_value(display.get("progress", 0.0), 2),  # 2 decimals for progress
                    "message": display.get("message", "")
                }
        
        return transformed
    
    def sync_status(self, status_data: Dict[str, Any]):
        """
        Sync printer status to Firestore.

        Args:
            status_data: Raw status data from Moonraker
        """
        if not self._initialized or not self.db:
            logger.error("Firebase not initialized")
            return

        try:
            # Log incoming data for debugging
            logger.info(f"Received status update with keys: {list(status_data.keys())}")
            if "print_stats" in status_data:
                logger.info(f"print_stats data: {status_data['print_stats']}")
            if "virtual_sdcard" in status_data:
                logger.info(f"virtual_sdcard data: {status_data['virtual_sdcard']}")

            # Transform data
            transformed_data = self.transform_status_data(status_data)

            # Log transformed data
            if "print_stats" in transformed_data:
                logger.info(f"Transformed print_stats: {transformed_data['print_stats']}")

            # Update Firestore document
            doc_ref = self.db.collection(Config.FIRESTORE_COLLECTION).document("current")
            doc_ref.set(transformed_data, merge=True)

            logger.debug("Synced printer status to Firestore")

        except Exception as e:
            logger.error(f"Failed to sync status to Firestore: {e}")
            # Don't raise - we want to continue even if one sync fails

