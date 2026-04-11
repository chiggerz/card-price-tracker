from fastapi import FastAPI
from pydantic import BaseModel

from parser import parse_card_query

app = FastAPI()


class SearchRequest(BaseModel):
    query: str


@app.get("/")
def read_root() -> dict[str, str]:
    return {"status": "running"}


@app.post("/search")
def search_cards(payload: SearchRequest) -> dict:
    parsed_query = parse_card_query(payload.query)
    return parsed_query
