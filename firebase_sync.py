"""Firebase Firestore integration for syncing printer status."""
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Union, List
import threading
import requests
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
        self._latest_status: Dict[str, Any] = {}  # Store latest merged status data
        self._last_synced_data: Dict[str, Any] = {}  # Store last data synced to Firestore
        self._current_file_metadata: Dict[str, Any] = {}  # Store metadata for current file
        self._queue_listener = None
    
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
            
            # Setup queue listener
            self._setup_queue_listener()
            
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {e}")
            raise
            raise
    
    def update_metadata(self, metadata: Dict[str, Any]):
        """
        Update current file metadata.
        
        Args:
            metadata: File metadata from Moonraker
        """
        self._current_file_metadata = metadata
        logger.info(f"Updated file metadata (estimated_time: {metadata.get('estimated_time')})")
    
    def transform_status_data(self, status_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform Moonraker status data to Firestore document format.
        
        Args:
            status_data: Raw status data from Moonraker
            
        Returns:
            Transformed data structure for Firestore
        """
        transformed = {}
        progress = None  # Initialize progress to avoid UnboundLocalError

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
                if "print_stats" not in transformed:
                    transformed["print_stats"] = {}

                # Only add fields that are actually present
                if "state" in print_stats:
                    transformed["print_stats"]["state"] = print_stats["state"]

                if "filename" in print_stats and print_stats["filename"]:
                    transformed["print_stats"]["filename"] = print_stats["filename"]

                # Duration and time remaining
                total_duration = print_stats.get("total_duration")
                print_duration = print_stats.get("print_duration")
                if print_duration is not None:
                    transformed["print_stats"]["print_duration"] = round_value(print_duration, 1)

                if total_duration is not None and print_duration is not None:
                    # Calculate time remaining using estimated_time from metadata if available
                    estimated_time = self._current_file_metadata.get("estimated_time")
                    
                    if estimated_time:
                        # If we have metadata, use estimated_time - print_duration
                        time_remaining = max(0, round_value(estimated_time - print_duration, 0))
                    elif progress and progress > 0:
                        # Fallback: Estimate based on progress
                        # (print_duration / progress) = total_estimated_time
                        total_estimated = print_duration / progress
                        time_remaining = max(0, round_value(total_estimated - print_duration, 0))
                    else:
                        # Last resort: just use what we have (though likely incorrect as it includes pause)
                        time_remaining = max(0, round_value(total_duration - print_duration, 0))
                        
                    transformed["print_stats"]["time_remaining"] = time_remaining

        # Extract virtual_sdcard for file_size, filename, and progress
        if "virtual_sdcard" in status_data:
            sdcard = status_data["virtual_sdcard"]
            if isinstance(sdcard, dict):
                if "print_stats" not in transformed:
                    transformed["print_stats"] = {}

                # Only add filename if file_path is present and not null
                file_path = sdcard.get("file_path")
                if file_path:
                    transformed["print_stats"]["filename"] = file_path

                # Get progress directly from virtual_sdcard (already a percentage 0-1, convert to 0-100)
                progress = sdcard.get("progress")
                if progress is not None:
                    transformed["print_stats"]["progress"] = round_value(progress * 100, 2)  # Convert 0-1 to 0-100

                # Get file size
                file_size = sdcard.get("file_size")
                if file_size and file_size > 0:
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
    
    def _merge_status_update(self, new_status: Dict[str, Any]):
        """
        Merge new status update into the latest status.
        Moonraker sends partial updates, so we need to merge them.
        
        Args:
            new_status: New status data from Moonraker
        """
        # Deep merge the status data
        for key, value in new_status.items():
            if key in self._latest_status and isinstance(self._latest_status[key], dict) and isinstance(value, dict):
                # Recursively merge dictionaries
                self._latest_status[key].update(value)
            else:
                # Replace or add new key
                self._latest_status[key] = value
    
    def update_status(self, status_data: Dict[str, Any]):
        """
        Update the latest status data (does not sync to Firebase immediately).
        This method is called for each status update from Moonraker.

        Args:
            status_data: Raw status data from Moonraker
        """
        # Merge the new status into our stored status
        self._merge_status_update(status_data)
        logger.debug(f"Updated latest status (keys: {list(status_data.keys())})")
    
    def sync_status(self, status_data: Optional[Dict[str, Any]] = None):
        """
        Sync printer status to Firestore.
        If status_data is provided, it will be merged and synced.
        Otherwise, the latest stored status will be synced.

        Args:
            status_data: Optional raw status data from Moonraker (will be merged if provided)
        """
        if not self._initialized or not self.db:
            logger.error("Firebase not initialized")
            return

        try:
            # If new data provided, merge it first
            if status_data:
                self._merge_status_update(status_data)
            
            # If no status data stored, nothing to sync
            if not self._latest_status:
                logger.debug("No status data to sync")
                return

            # Transform the latest merged status
            transformed_data = self.transform_status_data(self._latest_status)

            # Check if data has changed since last sync
            if transformed_data == self._last_synced_data:
                logger.debug("Status has not changed, skipping sync")
                return

            # Log what we're syncing
            logger.debug(f"Syncing status to Firestore (keys: {list(transformed_data.keys())})")
            if "print_stats" in transformed_data:
                logger.debug(f"Print stats: {transformed_data['print_stats']}")

            # Update Firestore document
            doc_ref = self.db.collection(Config.FIRESTORE_COLLECTION).document("current")
            doc_ref.set(transformed_data, merge=True)
            
            # Update last synced data
            self._last_synced_data = transformed_data.copy()

            logger.info("Synced printer status to Firestore")

        except Exception as e:
            logger.error(f"Failed to sync status to Firestore: {e}")
            # Don't raise - we want to continue even if one sync fails

    def _setup_queue_listener(self):
        """Setup listener for print queue changes."""
        try:
            doc_ref = self.db.collection("print_queue").document("main")
            self._queue_listener = doc_ref.on_snapshot(self._on_queue_snapshot)
            logger.info("Print queue listener started")
        except Exception as e:
            logger.error(f"Failed to setup queue listener: {e}")

    def _on_queue_snapshot(self, doc_snapshot, changes, read_time):
        """
        Callback for print queue snapshot updates.
        
        Args:
            doc_snapshot: List of DocumentSnapshot (should be length 1)
            changes: List of changes
            read_time: Time of read
        """
        try:
            for doc in doc_snapshot:
                data = doc.to_dict()
                if not data or "queue" not in data:
                    continue

                queue_list = data["queue"]
                if not isinstance(queue_list, list):
                    continue

                updated = False
                new_queue = []
                
                for item in queue_list:
                    # Check if item needs notification
                    if (isinstance(item, dict) and 
                        item.get("status") == "printing" and 
                        not item.get("start_msg_sent", False)):
                        
                        user_id = item.get("requested_by")
                        if user_id:
                            stream_preference = item.get("stream_preference", "public")
                            private_link = item.get("private_stream_link")
                            
                            logger.info(f"Found new printing job for user {user_id}, sending notification...")
                            if self._send_notification(user_id, stream_preference, private_link):
                                item["start_msg_sent"] = True
                                updated = True
                    
                    new_queue.append(item)

                # If we modified any items, update the document
                if updated:
                    doc.reference.update({"queue": new_queue})
                    logger.info("Updated print queue with notification status")

        except Exception as e:
            logger.error(f"Error in queue snapshot listener: {e}")

    def _send_notification(self, user_id: str, stream_preference: str = "public", private_link: Optional[str] = None) -> bool:
        """
        Send WhatsApp notification to user.
        
        Args:
            user_id: The user ID to notify
            stream_preference: "public" or "private"
            private_link: YouTube link for private stream
            
        Returns:
            True if notification sent successfully, False otherwise
        """
        try:
            # 1. Get user's phone number and name
            user_doc = self.db.collection("users").document(user_id).get()
            if not user_doc.exists:
                logger.warning(f"User {user_id} not found")
                return False
            
            user_data = user_doc.to_dict()
            phone_number = user_data.get("phone_number")
            user_name = user_data.get("display_name") or user_data.get("name") or "User"
            
            if not phone_number:
                logger.warning(f"No phone number for user {user_id}")
                return False
            
            # 2. Determine stream link
            if stream_preference == "private" and private_link:
                stream_link = private_link
            else:
                stream_link = "https://controlthisonweb.com/"
            
            # 3. Construct message
            message = f"Hello {user_name}, Your 3D printing has started. You can watch the live stream here: {stream_link}"
            
            # 4. Call local API to send WhatsApp message
            api_url = Config.WHATSAPP_API_URL
            payload = {
                "number": phone_number,
                "message": message
            }
            
            logger.debug(f"Calling WhatsApp API for {phone_number}")
            response = requests.post(
                api_url, 
                json=payload, 
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"WhatsApp message sent successfully to {phone_number}")
                return True
            else:
                logger.error(f"Failed to send WhatsApp message. Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
            return False

