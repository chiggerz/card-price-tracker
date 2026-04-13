from typing import Any


def parse_card_query(query: str) -> dict[str, Any]:
    """Parse a card search query into simple structured fields."""
    normalized_query = query.strip()
    tokens = normalized_query.split()

    product_names = [
        ("topps chrome sapphire", "Topps Chrome Sapphire"),
        ("arsenal team set", "Arsenal Team Set"),
        ("topps chrome", "Topps Chrome"),
    ]
    subset_names = [
        ("northern stars", "Northern Stars"),
        ("golazo", "Golazo"),
        ("sapphire selections", "Sapphire Selections"),
        ("collector's corner", "Collector's Corner"),
        ("pitch pursuits", "Pitch Pursuits"),
    ]

    numbering = None
    filtered_tokens: list[str] = []
    for part in tokens:
        if part.startswith("/") and len(part) > 1 and part[1:].isdigit():
            if numbering is None:
                numbering = part
            continue
        filtered_tokens.append(part)

    normalized_query_without_numbering = " ".join(filtered_tokens)
    lowered_without_numbering = normalized_query_without_numbering.lower()
    lowered = normalized_query.lower()

    is_auto = "auto" in lowered

    player_name = None
    product = None
    subset = None

    matched_product = None
    for product_key, product_value in product_names:
        if product_key in lowered_without_numbering:
            matched_product = (product_key, product_value)
            break

    if matched_product:
        product_key, product_value = matched_product
        split_index = lowered_without_numbering.index(product_key)
        player_name = normalized_query_without_numbering[:split_index].strip() or None
        if player_name and player_name.isdigit():
            player_name = None
        product = product_value

    matched_subset = None
    for subset_key, subset_value in subset_names:
        if subset_key in lowered_without_numbering:
            matched_subset = subset_value
            break

    if matched_subset:
        subset = matched_subset

    if not player_name and not matched_product:
        if len(filtered_tokens) >= 2:
            player_name = " ".join(filtered_tokens[:2])
        elif filtered_tokens:
            player_name = filtered_tokens[0]

    if not product and len(filtered_tokens) > 2:
        product = " ".join(filtered_tokens[2:])

    return {
        "player_name": player_name,
        "product": product,
        "subset": subset,
        "numbering": numbering,
        "is_auto": is_auto,
    }
