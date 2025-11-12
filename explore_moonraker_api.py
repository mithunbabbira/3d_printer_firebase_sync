"""Temporary script to explore Moonraker API endpoints and available data."""
import requests
import json
from typing import Dict, Any, List
import sys

BASE_URL = "http://printer.local"


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_json(data: Any, indent: int = 2):
    """Pretty print JSON data."""
    print(json.dumps(data, indent=indent, default=str))


def test_endpoint(method: str, endpoint: str, params: Dict[str, Any] = None, data: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Test an API endpoint.
    
    Args:
        method: HTTP method (GET, POST, etc.)
        endpoint: API endpoint path
        params: Query parameters
        data: Request body data
        
    Returns:
        Response data as dictionary
    """
    url = f"{BASE_URL}{endpoint}"
    
    try:
        if method.upper() == "GET":
            response = requests.get(url, params=params, timeout=5)
        elif method.upper() == "POST":
            response = requests.post(url, json=data, params=params, timeout=5)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        response.raise_for_status()
        return response.json()
    
    except requests.exceptions.ConnectionError:
        print(f"❌ Connection Error: Could not connect to {BASE_URL}")
        print("   Make sure your printer is accessible at this address.")
        return None
    except requests.exceptions.Timeout:
        print(f"❌ Timeout: Request to {endpoint} timed out")
        return None
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP Error {e.response.status_code}: {e.response.text}")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def explore_server_info():
    """Explore server information endpoints."""
    print_section("Server Information")
    
    # Server info
    print("\n📡 Server Info:")
    result = test_endpoint("GET", "/server/info")
    if result:
        print_json(result.get("result", {}))
    
    # Server config
    print("\n⚙️  Server Config:")
    result = test_endpoint("GET", "/server/config")
    if result:
        print_json(result.get("result", {}))
    
    # Server temperature store
    print("\n🌡️  Temperature Store:")
    result = test_endpoint("GET", "/server/temperature_store")
    if result:
        print_json(result.get("result", {}))


def explore_printer_info():
    """Explore printer information endpoints."""
    print_section("Printer Information")
    
    # Printer info
    print("\n🖨️  Printer Info:")
    result = test_endpoint("GET", "/printer/info")
    if result:
        print_json(result.get("result", {}))
    
    # Printer objects list
    print("\n📋 Available Printer Objects:")
    result = test_endpoint("GET", "/printer/objects/list")
    if result:
        objects = result.get("result", {}).get("objects", [])
        print(f"Found {len(objects)} objects:")
        for obj in objects[:20]:  # Show first 20
            print(f"  - {obj}")
        if len(objects) > 20:
            print(f"  ... and {len(objects) - 20} more")
    
    # Printer objects query (get current status)
    print("\n📊 Current Printer Status (printer.objects.query):")
    result = test_endpoint("GET", "/printer/objects/query", params={
        "heater_bed": None,
        "extruder": None,
        "temperature_sensor bed": None,
        "temperature_sensor extruder": None,
        "print_stats": None,
        "display_status": None,
        "gcode_move": None,
        "virtual_sdcard": None
    })
    if result:
        print_json(result.get("result", {}).get("status", {}))


def explore_print_status():
    """Explore print status and job information."""
    print_section("Print Status & Jobs")
    
    # Print status
    print("\n🖨️  Print Status:")
    result = test_endpoint("GET", "/printer/objects/query", params={"print_stats": None})
    if result:
        print_stats = result.get("result", {}).get("status", {}).get("print_stats", {})
        print_json(print_stats)
    
    # Job queue status
    print("\n📋 Job Queue Status:")
    result = test_endpoint("GET", "/server/job_queue/status")
    if result:
        print_json(result.get("result", {}))
    
    # History
    print("\n📜 Print History:")
    result = test_endpoint("GET", "/server/history/list", params={"limit": 5})
    if result:
        print_json(result.get("result", {}))


def explore_temperature_data():
    """Explore temperature-related data."""
    print_section("Temperature Data")
    
    # Query all temperature-related objects
    print("\n🌡️  Temperature Sensors & Heaters:")
    result = test_endpoint("GET", "/printer/objects/query", params={
        "heater_bed": None,
        "extruder": None,
        "temperature_sensor bed": None,
        "temperature_sensor extruder": None
    })
    if result:
        status = result.get("result", {}).get("status", {})
        
        if "heater_bed" in status:
            print("\n🔥 Heater Bed:")
            print_json(status["heater_bed"])
        
        if "extruder" in status:
            print("\n🔥 Extruder:")
            print_json(status["extruder"])
        
        if "temperature_sensor bed" in status:
            print("\n🌡️  Temperature Sensor (Bed):")
            print_json(status["temperature_sensor bed"])
        
        if "temperature_sensor extruder" in status:
            print("\n🌡️  Temperature Sensor (Extruder):")
            print_json(status["temperature_sensor extruder"])


def explore_websocket_info():
    """Show WebSocket connection information."""
    print_section("WebSocket Information")
    
    print("\n🔌 WebSocket Endpoint:")
    print(f"   URL: ws://printer.local/websocket")
    print(f"   Protocol: JSON-RPC 2.0")
    print("\n📝 Available WebSocket Methods:")
    print("   - printer.objects.subscribe")
    print("   - printer.objects.query")
    print("   - printer.info")
    print("   - server.info")
    print("   - server.config")
    print("\n💡 Notification Methods:")
    print("   - notify_status_update (sent when subscribed objects change)")


def explore_all_objects():
    """Query all available printer objects to see their structure."""
    print_section("All Available Printer Objects (Sample Data)")
    
    # First get the list
    result = test_endpoint("GET", "/printer/objects/list")
    if not result:
        return
    
    objects = result.get("result", {}).get("objects", [])
    if not objects:
        print("No objects found")
        return
    
    print(f"\nFound {len(objects)} objects. Querying sample data...\n")
    
    # Query all objects (limit to first 10 to avoid overwhelming output)
    objects_to_query = objects[:10]
    params = {obj: None for obj in objects_to_query}
    
    result = test_endpoint("GET", "/printer/objects/query", params=params)
    if result:
        status = result.get("result", {}).get("status", {})
        for obj_name in objects_to_query:
            if obj_name in status:
                print(f"\n📦 {obj_name}:")
                print_json(status[obj_name])
    
    if len(objects) > 10:
        print(f"\n... and {len(objects) - 10} more objects available")


def main():
    """Main exploration function."""
    print("\n" + "=" * 80)
    print("  Moonraker API Explorer")
    print("  Exploring: " + BASE_URL)
    print("=" * 80)
    
    # Test basic connectivity
    print("\n🔍 Testing connectivity...")
    result = test_endpoint("GET", "/server/info")
    if not result:
        print("\n❌ Cannot connect to Moonraker. Please check:")
        print("   1. Is the printer accessible at http://printer.local?")
        print("   2. Is Moonraker running?")
        print("   3. Can you access it from a browser?")
        sys.exit(1)
    
    print("✅ Connected successfully!\n")
    
    # Explore different aspects
    explore_server_info()
    explore_printer_info()
    explore_temperature_data()
    explore_print_status()
    explore_websocket_info()
    
    # Ask if user wants to see all objects
    print("\n" + "=" * 80)
    response = input("\nDo you want to see data from all available printer objects? (y/n): ")
    if response.lower() == 'y':
        explore_all_objects()
    
    print("\n" + "=" * 80)
    print("  Exploration Complete!")
    print("=" * 80)
    print("\n💡 Next Steps:")
    print("   1. Review the data structures above")
    print("   2. Update moonraker_client.py subscription if needed")
    print("   3. Update firebase_sync.py transformation if needed")
    print("   4. Run main.py to start syncing to Firebase\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

