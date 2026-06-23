import json
import random
from pathlib import Path

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse


router = APIRouter(
    prefix="/quizes",
    tags=["Quizes"],
)

QUIZ_DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "quizes" / "quizes.json"


def load_quizes():
    with QUIZ_DATA_FILE.open(encoding="utf8") as file:
        data = json.load(file)
    return data.get("quizes", [])


@router.get("/")
async def read_items():
    return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Quizes route works!"})


@router.get("/get_random_quiz")
async def get_random_quiz():
    quizes = load_quizes()
    if len(quizes) == 0:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": "No quizes found"})

    data = random.choice(quizes)
    return JSONResponse(status_code=status.HTTP_200_OK, content=data, headers={"Access-Control-Allow-Origin": "*"})


@router.get("/get_random_question")
async def get_random_question():
    return await get_random_quiz()
