from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from fetch_definitions import DefinitionFetcher
import json
import asyncio
from typing import Any

redis_client = None

app = FastAPI(title="Dictionary API", version="0.1")

fetcher = DefinitionFetcher()

# readiness flag
app.state.ready = False

class Pronunciation(BaseModel):
    text: Optional[str]
    audio: Optional[str]

class DefinitionsResponse(BaseModel):
    word: str
    pronunciation: Optional[dict]
    definitions: dict


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.on_event("startup")
async def startup_checks():
    allow = os.environ.get('ALLOW_STARTUP_WITHOUT_KEY', 'false').lower() in ('1', 'true', 'yes')
    key = os.environ.get('MERRIAM_KEY')
    if not key and not allow:
        raise RuntimeError('MERRIAM_KEY missing; set it in env or .env')

    app.state.ready = True

    # Initialize Redis client if configured
    cache_url = os.environ.get('CACHE_URL')
    if cache_url:
        try:
            import aioredis
            global redis_client
            redis_client = aioredis.from_url(cache_url, encoding='utf-8', decode_responses=True)
            # simple ping
            await redis_client.ping()
        except Exception:
            import logging
            logging.getLogger(__name__).warning('Unable to connect to Redis at CACHE_URL; continuing without cache')


@app.get("/ready")
async def ready():
    return {"ready": bool(app.state.ready)}


@app.get("/api/define/{word}", response_model=DefinitionsResponse)
async def define(word: str):
    key = os.environ.get('MERRIAM_KEY')
    if not key:
        raise HTTPException(status_code=500, detail="MERRIAM_KEY not configured on server")

    try:
        # Check cache first (async)
        cache_key = f"define:{word.lower()}"
        if redis_client:
            cached = await redis_client.get(cache_key)
            if cached:
                return json.loads(cached)

        result = fetcher.fetch_definitions(word, key)

        # Store in cache
        if redis_client:
            ttl = int(os.environ.get('CACHE_TTL', '3600'))
            await redis_client.set(cache_key, json.dumps(result, ensure_ascii=False), ex=ttl)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
