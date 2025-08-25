from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import routes.hadith as hadith

app = FastAPI(
    title="Muslim API",
    description="An API for Muslim resources",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(hadith.router)

@app.get("/")
async def root():
    return {"message": "Hello From Muslim API"}

@app.exception_handler(status.HTTP_404_NOT_FOUND)
async def handle_404(e, request):
    return JSONResponse(status_code=404, content={"message": "Invalid route"})