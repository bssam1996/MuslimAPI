from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
import json
import random
from utils.hadith import utils as hadith_utils

router = APIRouter(
    prefix="/hadith",
    tags=["Hadith"],
)

LIST_OF_HADITH_BOOKS = [
    "muslim"
]
@router.get("/")
async def read_items():
    return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Hadith route works!"})

@router.get("/get_random_hadith")
async def get_random_hadith():
    hadiths = []
    data = {}
    with open(f"data/hadith/random/data.json", encoding="utf8") as f:
        f = f.read()
        data = json.loads(f)
        hadiths = data["hadiths"]
    if len(hadiths) == 0:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": "No hadiths found"})
    data = random.choice(hadiths)
    return JSONResponse(status_code=status.HTTP_200_OK, content=data)

@router.get("/find_hadith")
async def find_hadith(searchQuery: str):
    if searchQuery == "":
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"message": "Search query cannot be empty"})
    
    # Get data
    data = hadith_utils.getSimilarHadiths(searchQuery)
    if not data:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": "No hadiths found"})
    # data = hadith_utils.generateMockData()
    # data = hadith_utils.generateEmptyResponse()
    if not data.get("ahadith"):
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": "No hadiths found"})

    results = data["ahadith"].get("result")
    if not results:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": "No hadiths found"})
    cleanedResults = hadith_utils.cleanSimilarHadithResults(results)
    if len(cleanedResults) == 0:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": "No hadiths found"})
    return JSONResponse(status_code=status.HTTP_200_OK, content={"results": cleanedResults})