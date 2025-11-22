"""Moonraker WebSocket client for real-time printer status updates."""
import asyncio
import json
import logging
import websockets
from typing import Dict, Any, Optional, Callable
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class MoonrakerClient:
    """WebSocket client for Moonraker JSON-RPC 2.0 API."""
    
    def __init__(self, ws_url: str, on_status_update: Callable[[Dict[str, Any]], None]):
        """
        Initialize Moonraker client.
        
        Args:
            ws_url: WebSocket URL (e.g., ws://printer.local/websocket)
            on_status_update: Callback function for status updates
        """
        self.ws_url = ws_url
        self.on_status_update = on_status_update
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.connected = False
        self._reconnect_delay = 1
        self._max_reconnect_delay = 60
        self._request_id = 0
        self._subscription_id: Optional[int] = None
        self._pending_requests: Dict[int, asyncio.Future] = {}
        
    def _get_next_request_id(self) -> int:
        """Get next JSON-RPC request ID."""
        self._request_id += 1
        return self._request_id
    
    async def _send_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send JSON-RPC 2.0 request and wait for response."""
        if not self.websocket:
            raise ConnectionError("WebSocket not connected")
        
        request_id = self._get_next_request_id()
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "id": request_id
        }
        
        if params:
            request["params"] = params
            
        # Create a future to wait for the response
        future = asyncio.get_running_loop().create_future()
        self._pending_requests[request_id] = future
        
        try:
            await self.websocket.send(json.dumps(request))
            logger.debug(f"Sent request: {method} (id: {request_id})")
            
            # Wait for response via the listen loop
            response_data = await future
            
            if "error" in response_data:
                error = response_data["error"]
                raise Exception(f"Moonraker error: {error.get('message', 'Unknown error')}")
            
            return response_data
        finally:
            # Clean up the pending request
            self._pending_requests.pop(request_id, None)
    
    async def get_file_metadata(self, filename: str) -> Dict[str, Any]:
        """
        Get metadata for a specific file.
        
        Args:
            filename: The name of the file (including path relative to gcodes root)
            
        Returns:
            Dictionary containing file metadata
        """
        try:
            # Ensure filename has correct prefix if needed, but usually Moonraker expects just the path
            # server.files.metadata expects "filename" param
            params = {"filename": filename}
            response = await self._send_request("server.files.metadata", params)
            return response.get("result", {})
        except Exception as e:
            logger.error(f"Failed to get metadata for {filename}: {e}")
            return {}
    
    async def connect(self):
        """Connect to Moonraker WebSocket."""
        try:
            # Parse URL and convert to WebSocket URL if needed
            parsed = urlparse(self.ws_url)
            if parsed.scheme == "http":
                ws_url = self.ws_url.replace("http://", "ws://") + "/websocket"
            elif parsed.scheme == "https":
                ws_url = self.ws_url.replace("https://", "wss://") + "/websocket"
            else:
                ws_url = self.ws_url
            
            logger.info(f"Connecting to Moonraker at {ws_url}")
            self.websocket = await websockets.connect(ws_url)
            self.connected = True
            self._reconnect_delay = 1
            logger.info("Connected to Moonraker WebSocket")
            
            # Subscribe to printer status updates
            # Note: This calls _send_request, which now relies on the listen loop being active.
            # However, we haven't started the listen loop yet. 
            # We need to start the listen loop concurrently or change how we subscribe.
            # Ideally, subscribe should happen after listen starts, or listen should handle the handshake.
            # But since we are in a simple script, we can't easily split them without major refactor.
            # Wait! If we call subscribe here, it will await _send_request -> await future.
            # But nothing is resolving the future because listen() isn't running!
            # FIX: We should NOT subscribe here. We should subscribe in the listen loop or 
            # start a background task for listening immediately after connect.
            
            # For now, let's just return and let the caller call listen().
            # But wait, the caller calls listen() which blocks.
            # We need to change the architecture slightly.
            # The listen loop handles ALL incoming messages.
            # We should probably send the subscribe request *after* the listen loop starts?
            # Or, we can spawn the listen loop as a task?
            
            # Let's modify the main.py to start listen as a task?
            # Or better, let's make subscribe_to_status fire-and-forget or handle it differently.
            
            # Actually, the cleanest way is to have listen() be the main driver.
            # But we need to send the subscribe request.
            
            # Let's change connect to NOT subscribe.
            # And add a method `on_connect` that sends the subscription.
            # But `on_connect` needs to be async and awaited.
            
            # Alternative: In `listen`, we can check if we are subscribed. If not, subscribe.
            
        except Exception as e:
            logger.error(f"Failed to connect to Moonraker: {e}")
            self.connected = False
            raise
            
    async def subscribe_to_status(self):
        """Subscribe to printer object status updates."""
        try:
            # Subscribe to printer objects
            # Based on actual printer objects: heater_bed, heaters, print_stats, display_status, etc.
            params = {
                "objects": {
                    "heater_bed": None,
                    "extruder": None,  # Direct extruder object for temperature
                    "heaters": None,  # May contain additional heater info
                    "print_stats": None,
                    "display_status": None,
                    "gcode_move": None,
                    "virtual_sdcard": None
                }
            }

            response = await self._send_request("printer.objects.subscribe", params)
            result = response.get("result", {})
            self._subscription_id = result.get("subscription_id")

            # Get initial status from subscription response
            status = result.get("status", {})
            if status:
                logger.info("Received initial status from subscription")
                self.on_status_update(status)

            if self._subscription_id:
                logger.info(f"Subscribed to printer status updates (subscription_id: {self._subscription_id})")
            else:
                logger.warning("Subscription successful but no subscription_id returned")

        except Exception as e:
            logger.error(f"Failed to subscribe to status updates: {e}")
            # Don't raise here to avoid crashing the loop if subscription fails temporarily
    
    async def listen(self):
        """Listen for messages from Moonraker."""
        if not self.websocket:
            raise ConnectionError("WebSocket not connected")
        
        # Start subscription as a background task once we start listening
        # This ensures the listen loop is running to handle the response
        asyncio.create_task(self.subscribe_to_status())
        
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    
                    # Handle responses to pending requests
                    if "id" in data and data["id"] in self._pending_requests:
                        request_id = data["id"]
                        future = self._pending_requests[request_id]
                        if not future.done():
                            future.set_result(data)
                        continue
                    
                    # Handle notifications (status updates)
                    if "method" in data and data["method"] == "notify_status_update":
                        # Moonraker sends params as an array: [subscription_id, {status_data}]
                        params = data.get("params", [])
                        if len(params) >= 2 and isinstance(params[1], dict):
                            status_data = params[1]
                            logger.debug("Received status update from Moonraker")
                            self.on_status_update(status_data)
                        elif len(params) >= 1 and isinstance(params[0], dict):
                            # Fallback: sometimes it's just the status data
                            status_data = params[0]
                            logger.debug("Received status update from Moonraker")
                            self.on_status_update(status_data)
                    
                    # Handle other notifications
                    elif "method" in data:
                        logger.debug(f"Received notification: {data['method']}")
                    
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse message: {e}")
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.warning("WebSocket connection closed")
            self.connected = False
            # Cancel all pending requests
            for future in self._pending_requests.values():
                if not future.done():
                    future.cancel()
            self._pending_requests.clear()
            raise
        except Exception as e:
            logger.error(f"Error in listen loop: {e}")
            self.connected = False
            raise
    
    async def disconnect(self):
        """Disconnect from Moonraker WebSocket."""
        if self.websocket:
            await self.websocket.close()
            self.connected = False
            logger.info("Disconnected from Moonraker")
    
    async def reconnect(self):
        """Reconnect to Moonraker with exponential backoff."""
        while True:
            try:
                await self.connect()
                return
            except Exception as e:
                logger.warning(
                    f"Reconnection attempt failed: {e}. "
                    f"Retrying in {self._reconnect_delay} seconds..."
                )
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(
                    self._reconnect_delay * 2,
                    self._max_reconnect_delay
                )

