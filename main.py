from fastapi import FastAPI
import models
from routers.user_router import router as user_router
from fastapi.middleware.cors import CORSMiddleware
from redis import asyncio as aioredis
from settings import settings
from contextlib import asynccontextmanager
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from routers.position_router import router as position_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis = aioredis.from_url(
        f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}",
        encoding="utf-8",
        decode_responses=True,
    )
    redis_backend = RedisBackend(redis)
    FastAPICache.init(redis_backend, prefix="fastapi-cache")
    yield
    await redis.close()

app = FastAPI(lifespan=lifespan)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(user_router)
app.include_router(position_router)

@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}
