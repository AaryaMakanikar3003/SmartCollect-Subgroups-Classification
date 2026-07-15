from datetime import date

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio

from app.config import DB_CONFIG
from app.data.postgres_source import PostgresDataSource
from app.pipeline.orchestrator import run_pipeline, get_category_counts
from app.aiml.direct_pipeline import run_direct_pipeline

app = FastAPI(title="SmartCollect Subgroup Classifier")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

source = PostgresDataSource(DB_CONFIG)


@app.get("/banks")
def list_banks():
    return source.get_banks()


@app.get("/campaigns")
def list_campaigns(bank_id: int):
    return source.get_campaigns(bank_id)


@app.get("/conversations/summary")
def conversations_summary(campaign_id: int, from_date: date, to_date: date):
    return get_category_counts(source, campaign_id, from_date, to_date)


@app.websocket("/ws/analyze")
async def analyze_ws(websocket: WebSocket):
    await websocket.accept()
    try:
        params = await websocket.receive_json()
        campaign_id = params["campaign_id"]
        from_date = params["from_date"]
        to_date = params["to_date"]
        category = params["category"]
        limit = params.get("limit")

        loop = asyncio.get_event_loop()

        def on_progress(msg):
            asyncio.run_coroutine_threadsafe(
                websocket.send_json({"status": "progress", "message": msg}), loop
            )

        result = await loop.run_in_executor(
            None,
            lambda: run_pipeline(source, campaign_id, from_date, to_date, category, limit, on_progress),
        )

        await websocket.send_json({"status": "done", "result": result})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({"status": "error", "message": str(e)})

@app.websocket("/ws/analyze-direct")
async def analyze_direct_ws(websocket: WebSocket):
    await websocket.accept()
    try:
        params = await websocket.receive_json()
        campaign_id = params["campaign_id"]
        from_date = params["from_date"]
        to_date = params["to_date"]
        category = params.get("category")   
        limit = params.get("limit")          

        loop = asyncio.get_event_loop()

        def on_progress(msg):
            asyncio.run_coroutine_threadsafe(
                websocket.send_json({"status": "progress", "message": msg}), loop
            )

        result = await loop.run_in_executor(
            None,
            lambda: run_direct_pipeline(
                source, campaign_id, from_date, to_date,
                category=category, limit=limit, on_progress=on_progress
            ),
        )

        await websocket.send_json({"status": "done", "result": result})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({"status": "error", "message": str(e)})