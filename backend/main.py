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
    exact_matches = [item for item in candidate_results if item["bucket"] == "exact_matches"]
    same_player_different_number = [
        item for item in candidate_results if item["bucket"] == "same_player_different_number"
    ]
    same_player_other_variant = [
        item for item in candidate_results if item["bucket"] == "same_player_other_variant"
    ]
    different_player_same_card_type = [
        item for item in candidate_results if item["bucket"] == "different_player_same_card_type"
    ]
    low_relevance_results = [
        item for item in candidate_results if item["bucket"] == "low_relevance_results"
    ]

    return {
        "parsed_query": parsed_query,
        "candidate_results": candidate_results,
        "exact_matches": exact_matches,
        "same_player_different_number": same_player_different_number,
        "same_player_other_variant": same_player_other_variant,
        "different_player_same_card_type": different_player_same_card_type,
        "low_relevance_results": low_relevance_results,
    }
