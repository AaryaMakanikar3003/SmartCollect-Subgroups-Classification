import asyncio
import websockets
import json

async def test():
    async with websockets.connect("ws://127.0.0.1:8000/ws/analyze") as ws:
        await ws.send(json.dumps({"campaign_id": 1524, "days": 30}))
        while True:
            msg = json.loads(await ws.recv())
            print(msg.get("status"), "-", msg.get("message", ""))
            if msg["status"] in ("done", "error"):
                if msg["status"] == "done":
                    print(json.dumps(msg["result"], indent=2, ensure_ascii=False))
                break

asyncio.run(test())