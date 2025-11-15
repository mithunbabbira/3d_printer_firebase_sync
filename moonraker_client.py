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
        
        await self.websocket.send(json.dumps(request))
        logger.debug(f"Sent request: {method} (id: {request_id})")
        
        # Wait for response
        response = await self.websocket.recv()
        response_data = json.loads(response)
        
        if "error" in response_data:
            error = response_data["error"]
            raise Exception(f"Moonraker error: {error.get('message', 'Unknown error')}")
        
        return response_data
    
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
            await self.subscribe_to_status()
            
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
            raise
    
    async def listen(self):
        """Listen for messages from Moonraker."""
        if not self.websocket:
            raise ConnectionError("WebSocket not connected")
        
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    
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
                    
                    # Handle responses (ignore for now, handled in _send_request)
                    elif "result" in data or "error" in data:
                        logger.debug(f"Received response: {data.get('id', 'unknown')}")
                    
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse message: {e}")
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.warning("WebSocket connection closed")
            self.connected = False
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

