from fastapi import APIRouter
from fastapi.responses import JSONResponse
import json
import random

router = APIRouter(
    prefix="/hadith",
    tags=["Hadith"],
)

LIST_OF_HADITH_BOOKS = [
    "muslim"
]
@router.get("/")
async def read_items():
    return JSONResponse(status_code=200, content={"message": "Hadith route works!"})

@router.get("/get_random_hadith")
async def get_random_hadith():
    hadiths = []
    data = {}
    with open(f"data/hadith/random/data.json", encoding="utf8") as f:
        f = f.read()
        data = json.loads(f)
        hadiths = data["hadiths"]
    if len(hadiths) == 0:
        return JSONResponse(status_code=404, content={"message": "No hadiths found"})
    data = random.choice(hadiths)
    return JSONResponse(status_code=200, content=data)