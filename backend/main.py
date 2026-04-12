# IMPORTANT:
# All imports must use the "backend." package prefix.
# Do NOT use:
#   from parser import ...
#   from matcher import ...
# Always use:
#   from backend.parser import parse_card_query
#   from backend.matcher import match_candidates

from fastapi import FastAPI
from pydantic import BaseModel

from backend.parser import parse_card_query
from backend.matcher import match_candidates

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


@app.post("/search/match")
def search_match(payload: SearchRequest) -> dict:
    parsed_query = parse_card_query(payload.query)
    candidate_results = match_candidates(parsed_query)
    included_results = [item for item in candidate_results if item["included"]]
    excluded_results = [item for item in candidate_results if not item["included"]]

    return {
        "parsed_query": parsed_query,
        "candidate_results": candidate_results,
        "included_results": included_results,
        "excluded_results": excluded_results,
    }
