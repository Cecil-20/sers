import asyncio
import websockets


async def test():
    uri = "ws://127.0.0.1:8000/ws/incidents/"

    try:
        async with websockets.connect(uri) as ws:
            print("Connected:", ws)

            # Keep the connection open briefly
            await asyncio.sleep(5)

    except Exception as e:
        print("WebSocket connection failed:", e)


asyncio.run(test())
