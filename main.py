"""Main application entry point for Moonraker to Firebase sync."""
import asyncio
import logging
import signal
import sys
from typing import Optional
from moonraker_client import MoonrakerClient
from firebase_sync import FirebaseSync
from config import Config

# Configure logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)


class PrinterDataSync:
    """Main application class for syncing printer data."""
    
    def __init__(self):
        """Initialize the sync application."""
        self.firebase_sync = FirebaseSync()
        self.moonraker_client: MoonrakerClient = None
        self.running = False
        self._sync_task: Optional[asyncio.Task] = None
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(sig, frame):
            logger.info("Received shutdown signal, shutting down gracefully...")
            self.running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def _on_status_update(self, status_data):
        """Callback for Moonraker status updates."""
        try:
            # Store the update but don't sync immediately
            # Sync will happen periodically via the sync task
            self.firebase_sync.update_status(status_data)
        except Exception as e:
            logger.error(f"Error handling status update: {e}")
    
    async def _periodic_sync(self):
        """Periodic task to sync status to Firebase."""
        sync_interval = Config.SYNC_INTERVAL
        logger.info(f"Starting periodic sync task (interval: {sync_interval} seconds)")
        
        while self.running:
            try:
                await asyncio.sleep(sync_interval)
                if self.running:
                    # Sync the latest status to Firebase
                    self.firebase_sync.sync_status()
            except asyncio.CancelledError:
                logger.info("Periodic sync task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in periodic sync: {e}")
    
    async def start(self):
        """Start the sync application."""
        logger.info("Starting Moonraker to Firebase sync...")
        
        try:
            # Validate configuration
            Config.validate()
            logger.info("Configuration validated")
            
            # Initialize Firebase
            self.firebase_sync.initialize()
            logger.info("Firebase initialized")
            
            # Initialize Moonraker client
            self.moonraker_client = MoonrakerClient(
                Config.MOONRAKER_WS_URL,
                self._on_status_update
            )
            
            self.running = True
            
            # Start periodic sync task
            self._sync_task = asyncio.create_task(self._periodic_sync())
            logger.info(f"Periodic sync task started (every {Config.SYNC_INTERVAL} seconds)")
            
            # Main loop with reconnection logic
            while self.running:
                try:
                    # Connect to Moonraker
                    if not self.moonraker_client.connected:
                        await self.moonraker_client.connect()
                    
                    # Listen for updates
                    await self.moonraker_client.listen()
                    
                except Exception as e:
                    logger.error(f"Error in main loop: {e}")
                    
                    if self.running:
                        logger.info("Attempting to reconnect...")
                        await self.moonraker_client.reconnect()
                    else:
                        break
        
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """Shutdown the application gracefully."""
        logger.info("Shutting down...")
        
        # Cancel periodic sync task
        if self._sync_task and not self._sync_task.done():
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
        
        # Sync final status before shutdown
        if self.firebase_sync:
            logger.info("Syncing final status before shutdown...")
            self.firebase_sync.sync_status()
        
        if self.moonraker_client:
            await self.moonraker_client.disconnect()
        
        logger.info("Shutdown complete")


async def main():
    """Main entry point."""
    app = PrinterDataSync()
    await app.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application terminated by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)
        sys.exit(1)

