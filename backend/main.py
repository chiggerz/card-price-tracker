# IMPORTANT:
# All imports must use the "backend." package prefix.
# Do NOT use:
#   from parser import ...
#   from matcher import ...
# Always use:
#   from backend.parser import parse_card_query
#   from backend.matcher import match_candidates

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from backend.checklists import ChecklistStore
from backend.ebay_client import EbayConfigurationError, EbayRequestError, search_sold_items
from backend.parser import parse_card_query
from backend.matcher import match_candidates

app = FastAPI()
checklist_store = ChecklistStore.from_file()


class SearchRequest(BaseModel):
    query: str


class StructuredSearchRequest(BaseModel):
    set_name: str
    player_name: str
    card_type: str
    numbering: str | None = None


def group_candidate_results(candidate_results: list[dict]) -> dict[str, list[dict]]:
    return {
        "exact_matches": [item for item in candidate_results if item["bucket"] == "exact_matches"],
        "same_player_different_number": [
            item for item in candidate_results if item["bucket"] == "same_player_different_number"
        ],
        "same_player_other_variant": [
            item for item in candidate_results if item["bucket"] == "same_player_other_variant"
        ],
        "different_player_same_card_type": [
            item for item in candidate_results if item["bucket"] == "different_player_same_card_type"
        ],
        "low_relevance_results": [
            item for item in candidate_results if item["bucket"] == "low_relevance_results"
        ],
    }


def empty_grouped_results() -> dict[str, list[dict]]:
    return {
        "exact_matches": [],
        "same_player_different_number": [],
        "same_player_other_variant": [],
        "different_player_same_card_type": [],
        "low_relevance_results": [],
    }


def fetch_and_match(parsed_query: dict, ebay_query: str) -> tuple[list[dict], str | None]:
    try:
        sold_listings = search_sold_items(ebay_query)
    except EbayConfigurationError as exc:
        return [], str(exc)
    except EbayRequestError as exc:
        return [], f"Unable to fetch sold listings from eBay right now. {exc}"

    candidate_results = match_candidates(parsed_query, sold_listings)
    if not sold_listings:
        return candidate_results, "No sold/completed eBay listings were found for this query."
    return candidate_results, None


@app.get("/")
def read_root() -> dict[str, str]:
    return {"status": "running"}


@app.get("/sets")
def list_sets() -> dict[str, list[str]]:
    return {"sets": checklist_store.list_sets()}


@app.get("/players")
def list_players_for_set(set_name: str) -> dict[str, str | list[str]]:
    if not checklist_store.has_set(set_name):
        raise HTTPException(status_code=404, detail=f"Unknown set_name: {set_name}")
    return {"set_name": set_name, "players": checklist_store.list_players(set_name)}


@app.get("/card-types")
def list_card_types_for_player(set_name: str, player_name: str) -> dict[str, list[str] | str]:
    if not checklist_store.has_set(set_name):
        raise HTTPException(status_code=404, detail=f"Unknown set_name: {set_name}")
    if not checklist_store.has_player(set_name, player_name):
        raise HTTPException(
            status_code=404,
            detail=f"Unknown player_name '{player_name}' for set '{set_name}'",
        )
    return {
        "set_name": set_name,
        "player_name": player_name,
        "card_types": checklist_store.list_card_types(set_name, player_name),
    }


@app.post("/search")
def search_cards(payload: SearchRequest) -> dict:
    parsed_query = parse_card_query(payload.query)
    return parsed_query


@app.post("/search/match")
def search_match(payload: SearchRequest) -> dict:
    parsed_query = parse_card_query(payload.query)
    candidate_results, message = fetch_and_match(parsed_query, payload.query)

    grouped_results = group_candidate_results(candidate_results) if candidate_results else empty_grouped_results()

    response = {
        "parsed_query": parsed_query,
        "candidate_results": candidate_results,
        **grouped_results,
    }
    if message:
        response["message"] = message
    return response


@app.post("/search/structured")
def search_structured(payload: StructuredSearchRequest) -> dict:
    if not checklist_store.has_set(payload.set_name):
        raise HTTPException(status_code=404, detail=f"Unknown set_name: {payload.set_name}")

    if not checklist_store.has_player(payload.set_name, payload.player_name):
        raise HTTPException(
            status_code=404,
            detail=f"Unknown player_name '{payload.player_name}' for set '{payload.set_name}'",
        )

    if not checklist_store.has_card_type(payload.set_name, payload.player_name, payload.card_type):
        raise HTTPException(
            status_code=404,
            detail=(
                f"Unknown card_type '{payload.card_type}' for player '{payload.player_name}' "
                f"in set '{payload.set_name}'"
            ),
        )

    query_parts = [payload.player_name, payload.set_name, payload.card_type]
    if payload.numbering:
        query_parts.append(payload.numbering)
    normalized_query = " ".join(part.strip() for part in query_parts if part and part.strip())

    parsed_from_text = parse_card_query(normalized_query)
    parsed_query = {
        "player_name": payload.player_name,
        "product": payload.set_name,
        "subset": None if payload.card_type.lower() == "base" else payload.card_type,
        "numbering": payload.numbering,
        "is_auto": "auto" in payload.card_type.lower() or bool(parsed_from_text.get("is_auto")),
    }

    candidate_results, message = fetch_and_match(parsed_query, normalized_query)
    grouped_results = group_candidate_results(candidate_results) if candidate_results else empty_grouped_results()

    response = {
        "normalized_query": normalized_query,
        "parsed_query": parsed_query,
        **grouped_results,
    }
    if message:
        response["message"] = message
    return response
