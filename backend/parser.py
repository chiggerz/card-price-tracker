from typing import Any


def parse_card_query(query: str) -> dict[str, Any]:
    """Parse a card search query into simple structured fields."""
    normalized_query = query.strip()
    lowered = normalized_query.lower()

    numbering = None
    for part in normalized_query.split():
        if part.startswith("/") and len(part) > 1:
            numbering = part
            break

    is_auto = "auto" in lowered

    player_name = None
    product = None
    subset = None

    if "topps chrome sapphire" in lowered:
        split_index = lowered.index("topps chrome sapphire")
        player_name = normalized_query[:split_index].strip() or None
        product = "Topps Chrome"
        subset = "Sapphire"
    else:
        tokens = normalized_query.split()
        if len(tokens) >= 2:
            player_name = " ".join(tokens[:2])
            if len(tokens) > 2:
                product = " ".join(tokens[2:])
        elif tokens:
            player_name = tokens[0]

    return {
        "player_name": player_name,
        "product": product,
        "subset": subset,
        "numbering": numbering,
        "is_auto": is_auto,
    }
