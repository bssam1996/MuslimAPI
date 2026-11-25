import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from utils.metrics import MetricsMiddleware, metrics
# from .routes.hadith import hadith
import routes.hadith as hadith
import routes.quizes as quizes
import routes.prayer_times as prayer_times


ALLOWED_ORIGINS = ["https://bssam1996.github.io","*"]


@asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(metrics.watch_event_loop())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


app = FastAPI(
    title="Muslim API",
    description="An API for Muslim resources",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)
app.add_middleware(MetricsMiddleware, metrics=metrics)
metrics.info.info({"version": app.version})

app.include_router(hadith.router)
app.include_router(quizes.router)
app.include_router(prayer_times.router)

@app.get("/")
@metrics.track_function
async def root():
    return {"message": "Hello From Muslim API"}


@app.get("/metrics", include_in_schema=False)
def prometheus_metrics():
    return Response(generate_latest(metrics.registry), headers={
        "Content-Type": CONTENT_TYPE_LATEST,
        "Cache-Control": "no-store",
    })

@app.exception_handler(status.HTTP_404_NOT_FOUND)
async def handle_404(e, request):
    return JSONResponse(status_code=404, content={"message": "Invalid route"})
