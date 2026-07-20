from datetime import date

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio

from app.config import DB_CONFIG
from app.data.postgres_source import PostgresDataSource
from app.data.results_store import ResultsStore
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
results_store = ResultsStore()


# @app.get("/banks")
# def list_banks():
#     return source.get_banks()


# @app.get("/campaigns")
# def list_campaigns(bank_id: int):
#     return source.get_campaigns(bank_id)


# @app.get("/conversations/summary")
# def conversations_summary(campaign_id: int, from_date: date, to_date: date):
#     return get_category_counts(source, campaign_id, from_date, to_date)


# @app.get("/runs")
# def list_runs(campaign_id: int | None = None):
#     return results_store.list_runs(campaign_id)


# @app.get("/runs/{run_id}")
# def get_run(run_id: int):
#     run = results_store.get_run(run_id)
#     if run is None:
#         raise HTTPException(status_code=404, detail="Run not found")
#     return run


# @app.websocket("/ws/analyze")
# async def analyze_ws(websocket: WebSocket):
#     await websocket.accept()
#     try:
#         params = await websocket.receive_json()
#         campaign_id = params["campaign_id"]
#         from_date = params["from_date"]
#         to_date = params["to_date"]
#         category = params["category"]
#         limit = params.get("limit")

#         loop = asyncio.get_event_loop()

#         def on_progress(msg):
#             asyncio.run_coroutine_threadsafe(
#                 websocket.send_json({"status": "progress", "message": msg}), loop
#             )

#         result = await loop.run_in_executor(
#             None,
#             lambda: run_pipeline(source, campaign_id, from_date, to_date, category, limit, on_progress),
#         )

#         await websocket.send_json({"status": "done", "result": result})
#     except WebSocketDisconnect:
#         pass
#     except Exception as e:
#         await websocket.send_json({"status": "error", "message": str(e)})

# @app.websocket("/ws/analyze-direct")
# async def analyze_direct_ws(websocket: WebSocket):
#     await websocket.accept()
#     try:
#         params = await websocket.receive_json()
#         campaign_id = params["campaign_id"]
#         from_date = params["from_date"]
#         to_date = params["to_date"]
#         category = params.get("category")
#         limit = params.get("limit")

#         loop = asyncio.get_event_loop()

#         def on_progress(msg):
#             asyncio.run_coroutine_threadsafe(
#                 websocket.send_json({"status": "progress", "message": msg}), loop
#             )

#         result = await loop.run_in_executor(
#             None,
#             lambda: run_direct_pipeline(
#                 source, campaign_id, from_date, to_date,
#                 category=category, limit=limit, on_progress=on_progress
#             ),
#         )

#         run_id = None
#         try:
#             run_id = results_store.save_result(campaign_id, category, from_date, to_date, result)
#         except Exception as e:
#             # never let a save failure lose the analysis result the user already waited for
#             print(f"[results_store] failed to save run: {e}")

#         await websocket.send_json({"status": "done", "result": result, "run_id": run_id})
#     except WebSocketDisconnect:
#         pass
#     except Exception as e:
#         await websocket.send_json({"status": "error", "message": str(e)})



from app.data.source_registry import get_source, all_sources

@app.get("/banks")
def list_banks():
    banks = []
    for source_key, source in all_sources().items():
        for b in source.get_banks():
            banks.append({**b, "source": source_key})
    return banks


@app.get("/campaigns")
def list_campaigns(bank_id: int, source: str = "default"):
    return get_source(source).get_campaigns(bank_id)


@app.get("/conversations/summary")
def conversations_summary(campaign_id: int, from_date: date, to_date: date, source: str = "default"):
    return get_category_counts(get_source(source), campaign_id, from_date, to_date)


@app.get("/runs")
def list_runs(campaign_id: int | None = None):
    return results_store.list_runs(campaign_id)


@app.get("/runs/{run_id}")
def get_run(run_id: int):
    run = results_store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


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
        source_key = params.get("source", "default")
        src = get_source(source_key)

        loop = asyncio.get_event_loop()

        def on_progress(msg):
            asyncio.run_coroutine_threadsafe(
                websocket.send_json({"status": "progress", "message": msg}), loop
            )

        result = await loop.run_in_executor(
            None,
            lambda: run_direct_pipeline(
                src, campaign_id, from_date, to_date,
                category=category, limit=limit, on_progress=on_progress
            ),
        )

        run_id = None
        try:
            run_id = results_store.save_result(campaign_id, category, from_date, to_date, result)
        except Exception as e:
            print(f"[results_store] failed to save run: {e}")

        await websocket.send_json({"status": "done", "result": result, "run_id": run_id})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({"status": "error", "message": str(e)})