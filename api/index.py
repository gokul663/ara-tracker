import os
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
from pymongo import UpdateOne


app = FastAPI(title="Atlanta Route Planner API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

_client = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(doc: dict[str, Any]) -> dict[str, Any]:
    doc.pop("_id", None)
    return doc


def _get_env():
    mongo_uri = os.getenv("MONGO_URI", "").strip().strip('"').strip("'")
    mongo_db = os.getenv("MONGO_DB", "atlanta_tracker").strip()
    collection = os.getenv("COLLECTION", "stop_states").strip()
    return mongo_uri, mongo_db, collection


def _get_collection():
    global _client

    mongo_uri, mongo_db, collection = _get_env()

    if not mongo_uri:
        raise HTTPException(status_code=500, detail="MONGO_URI is missing")

    if not mongo_uri.startswith("mongodb+srv://") and not mongo_uri.startswith("mongodb://"):
        raise HTTPException(
            status_code=500,
            detail=f"MONGO_URI is malformed. It starts with: {mongo_uri[:20]}",
        )

    if _client is None:
        _client = AsyncIOMotorClient(
            mongo_uri,
            serverSelectionTimeoutMS=8000,
            connectTimeoutMS=8000,
        )

    return _client[mongo_db][collection]


class StopState(BaseModel):
    stop_key: str
    store_name: str = ""
    brand: str = ""
    installer_name: str = ""
    status: str = "Incomplete"
    comment: str = ""
    modem: bool = False
    updatedBy: str = ""

    model_config = {"extra": "allow"}


@app.get("/api/debug-env")
async def debug_env():
    mongo_uri, mongo_db, collection = _get_env()
    return {
        "mongo_uri_present": bool(mongo_uri),
        "mongo_uri_start": mongo_uri[:25] if mongo_uri else None,
        "mongo_uri_contains_parenthesis": "(" in mongo_uri or ")" in mongo_uri,
        "db": mongo_db,
        "collection": collection,
    }


@app.get("/api/health")
async def health():
    try:
        col = _get_collection()
        await col.database.client.admin.command("ping")
        return {
            "status": "ok",
            "db": col.database.name,
            "collection": col.name,
            "ts": _now(),
        }
    except Exception as e:
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "detail": str(e),
            "ts": _now(),
        }


@app.get("/api/state")
async def get_all_state():
    try:
        col = _get_collection()
        result = {}

        async for doc in col.find({}):
            doc = _clean(doc)
            if "stop_key" in doc:
                result[doc["stop_key"]] = doc

        return result

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"MongoDB state read failed: {type(e).__name__}: {str(e)}",
        )


@app.get("/api/state/{stop_key:path}")
async def get_stop(stop_key: str):
    try:
        col = _get_collection()
        doc = await col.find_one({"stop_key": stop_key})

        if not doc:
            raise HTTPException(status_code=404, detail=f"Stop not found: {stop_key}")

        return _clean(doc)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"MongoDB single read failed: {type(e).__name__}: {str(e)}",
        )


@app.post("/api/state")
async def upsert_stop(payload: StopState):
    try:
        col = _get_collection()

        data = payload.model_dump()
        data["updatedAt"] = _now()

        await col.update_one(
            {"stop_key": data["stop_key"]},
            {"$set": data},
            upsert=True,
        )

        return {
            "ok": True,
            "stop_key": data["stop_key"],
            "updatedAt": data["updatedAt"],
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"MongoDB update failed: {type(e).__name__}: {str(e)}",
        )


@app.post("/api/state/bulk")
async def bulk_upsert(payload: list[StopState]):
    try:
        col = _get_collection()

        if not payload:
            return {"ok": True, "upserted": 0, "ts": _now()}

        ts = _now()
        ops = []

        for item in payload:
            data = item.model_dump()
            data["updatedAt"] = ts
            ops.append(
                UpdateOne(
                    {"stop_key": data["stop_key"]},
                    {"$set": data},
                    upsert=True,
                )
            )

        result = await col.bulk_write(ops, ordered=False)

        return {
            "ok": True,
            "upserted": result.upserted_count + result.modified_count,
            "ts": ts,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"MongoDB bulk update failed: {type(e).__name__}: {str(e)}",
        )


@app.delete("/api/state/{stop_key:path}")
async def delete_stop(stop_key: str):
    try:
        col = _get_collection()
        result = await col.delete_one({"stop_key": stop_key})

        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail=f"Stop not found: {stop_key}")

        return {"ok": True, "deleted": stop_key}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"MongoDB delete failed: {type(e).__name__}: {str(e)}",
        )