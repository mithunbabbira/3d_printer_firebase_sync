"""Main application entry point for Moonraker to Firebase sync."""
import asyncio
import logging
import signal
import sys
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
            self.firebase_sync.sync_status(status_data)
        except Exception as e:
            logger.error(f"Error handling status update: {e}")
    
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

