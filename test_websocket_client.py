#!/usr/bin/env python
"""
Simple WebSocket client for testing the headless server.

Connects to the game server and sends sample input actions.
Usage: python test_websocket_client.py [--host localhost] [--port 8000]
"""

import asyncio
import json
import sys
from typing import Optional

try:
    import websockets
except ImportError:
    print("ERROR: websockets library not found. Install with: pip install websockets")
    sys.exit(1)


async def test_client(host: str = "localhost", port: int = 8000):
    """Connect to the game server and send test inputs."""
    uri = f"ws://{host}:{port}"

    print(f"Connecting to {uri}...")

    try:
        async with websockets.connect(uri) as websocket:
            print(f"✓ Connected!")
            print(f"  Server: {websocket.remote_address}")

            # Send a simple movement action
            actions = [
                {"action": "move", "direction": "north", "distance": 1},
                {"action": "move", "direction": "east", "distance": 1},
                {"action": "attack", "target_direction": "south"},
                {"action": "move", "direction": "west", "distance": 2},
            ]

            for i, action in enumerate(actions, 1):
                print(f"\n[{i}] Sending: {action}")
                await websocket.send(json.dumps(action))

                # Wait for acknowledgement
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    ack = json.loads(response)
                    print(f"    Ack: {ack.get('message')} ({ack.get('status')})")
                except asyncio.TimeoutError:
                    print("    ⚠ No acknowledgement received (timeout)")
                except Exception as e:
                    print(f"    ✗ Error: {e}")

                await asyncio.sleep(0.5)

            print("\n✓ Test complete! Keeping connection open for 5 seconds...")
            await asyncio.sleep(5)

    except ConnectionRefusedError:
        print(f"✗ Connection refused. Is the server running on {uri}?")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test WebSocket client for PyRogue server")
    parser.add_argument("--host", default="localhost", help="Server host (default: localhost)")
    parser.add_argument("--port", type=int, default=8000, help="Server port (default: 8000)")

    args = parser.parse_args()

    asyncio.run(test_client(args.host, args.port))
