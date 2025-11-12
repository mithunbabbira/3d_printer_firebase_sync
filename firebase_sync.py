"""Firebase Firestore integration for syncing printer status."""
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import firebase_admin
from firebase_admin import credentials, firestore
from config import Config

logger = logging.getLogger(__name__)


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
        transformed = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        # Extract temperature data
        # Based on actual printer objects: heater_bed and heaters (which may contain extruder)
        temperatures = {}
        
        # Bed temperature from heater_bed
        if "heater_bed" in status_data:
            bed_heater = status_data["heater_bed"]
            temperatures["bed"] = {
                "actual": bed_heater.get("temperature", 0.0),
                "target": bed_heater.get("target", 0.0)
            }
        
        # Extruder temperature - check heaters object or look for extruder heater
        # Heaters object may contain multiple heaters, look for extruder
        if "heaters" in status_data:
            heaters = status_data["heaters"]
            # Heaters might be a dict with heater names as keys
            if isinstance(heaters, dict):
                # Look for extruder heater (could be "extruder", "heater_generic extruder", etc.)
                for heater_name, heater_data in heaters.items():
                    if "extruder" in heater_name.lower() or heater_name == "extruder":
                        if isinstance(heater_data, dict):
                            temperatures["extruder"] = {
                                "actual": heater_data.get("temperature", 0.0),
                                "target": heater_data.get("target", 0.0)
                            }
                            break
        
        # Also check for direct extruder object (some configs have it)
        if "extruder" in status_data and "extruder" not in temperatures:
            extruder_heater = status_data["extruder"]
            if isinstance(extruder_heater, dict):
                temperatures["extruder"] = {
                    "actual": extruder_heater.get("temperature", 0.0),
                    "target": extruder_heater.get("target", 0.0)
                }
        
        if temperatures:
            transformed["temperatures"] = temperatures
        
        # Extract heater power data
        if "heater_bed" in status_data:
            bed_heater = status_data["heater_bed"]
            if isinstance(bed_heater, dict):
                transformed["heater_bed"] = {
                    "power": bed_heater.get("power", 0.0),
                    "target": bed_heater.get("target", 0.0),
                    "temperature": bed_heater.get("temperature", 0.0)
                }
        
        # Extract extruder heater power if available
        if "heaters" in status_data:
            heaters = status_data["heaters"]
            if isinstance(heaters, dict):
                for heater_name, heater_data in heaters.items():
                    if "extruder" in heater_name.lower() or heater_name == "extruder":
                        if isinstance(heater_data, dict):
                            transformed["extruder"] = {
                                "power": heater_data.get("power", 0.0),
                                "target": heater_data.get("target", 0.0),
                                "temperature": heater_data.get("temperature", 0.0)
                            }
                            break
        
        # Also check for direct extruder object
        if "extruder" in status_data and "extruder" not in transformed:
            extruder_heater = status_data["extruder"]
            if isinstance(extruder_heater, dict):
                transformed["extruder"] = {
                    "power": extruder_heater.get("power", 0.0),
                    "target": extruder_heater.get("target", 0.0),
                    "temperature": extruder_heater.get("temperature", 0.0)
                }
        
        # Extract print stats
        if "print_stats" in status_data:
            print_stats = status_data["print_stats"]
            if isinstance(print_stats, dict):
                transformed["print_stats"] = {
                    "state": print_stats.get("state", "unknown"),
                    "print_duration": print_stats.get("print_duration", 0),
                    "filename": print_stats.get("filename", ""),
                    "progress": print_stats.get("progress", 0.0),
                    "time_remaining": print_stats.get("total_duration", 0) - print_stats.get("print_duration", 0) if print_stats.get("total_duration") else None
                }
        
        # Extract virtual_sdcard (print progress)
        if "virtual_sdcard" in status_data:
            sdcard = status_data["virtual_sdcard"]
            if isinstance(sdcard, dict):
                file_position = sdcard.get("file_position", 0)
                file_size = sdcard.get("file_size", 0)
                progress = (file_position / file_size * 100) if file_size > 0 else 0.0
                
                if "print_stats" not in transformed:
                    transformed["print_stats"] = {}
                transformed["print_stats"]["progress"] = progress
                transformed["print_stats"]["file_position"] = file_position
                transformed["print_stats"]["file_size"] = file_size
        
        # Extract gcode_move (current position, speed, etc.)
        if "gcode_move" in status_data:
            gcode_move = status_data["gcode_move"]
            if isinstance(gcode_move, dict):
                transformed["gcode_move"] = {
                    "speed_factor": gcode_move.get("speed_factor", 1.0),
                    "speed": gcode_move.get("speed", 0.0),
                    "extrude_factor": gcode_move.get("extrude_factor", 1.0)
                }
        
        # Extract display status if available
        if "display_status" in status_data:
            display = status_data["display_status"]
            if isinstance(display, dict):
                transformed["display_status"] = {
                    "progress": display.get("progress", 0.0),
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
            # Transform data
            transformed_data = self.transform_status_data(status_data)
            
            # Update Firestore document
            doc_ref = self.db.collection(Config.FIRESTORE_COLLECTION).document("current")
            doc_ref.set(transformed_data, merge=True)
            
            logger.debug("Synced printer status to Firestore")
            
        except Exception as e:
            logger.error(f"Failed to sync status to Firestore: {e}")
            # Don't raise - we want to continue even if one sync fails

