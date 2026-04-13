from __future__ import annotations

import json
from pathlib import Path
from typing import Any


_DATA_PATH = Path(__file__).resolve().parent / "data" / "checklists.json"


class ChecklistStore:
    """In-memory accessor for checklist-backed guided search options."""

    def __init__(self, raw_data: dict[str, Any]) -> None:
        sets = raw_data.get("sets", {})
        if not isinstance(sets, dict):
            raise ValueError("Invalid checklist format: 'sets' must be an object")
        self._sets: dict[str, dict[str, list[str]]] = {}

        for set_name, set_data in sets.items():
            if not isinstance(set_data, dict):
                continue
            players = set_data.get("players", {})
            if not isinstance(players, dict):
                continue

            normalized_players: dict[str, list[str]] = {}
            for player_name, card_types in players.items():
                if not isinstance(card_types, list):
                    continue
                normalized_players[player_name] = [card_type for card_type in card_types if isinstance(card_type, str)]

            self._sets[set_name] = normalized_players

    @classmethod
    def from_file(cls, path: Path = _DATA_PATH) -> "ChecklistStore":
        with path.open("r", encoding="utf-8") as fp:
            data = json.load(fp)
        return cls(data)

    def list_sets(self) -> list[str]:
        return sorted(self._sets.keys())

    def has_set(self, set_name: str) -> bool:
        return set_name in self._sets

    def list_players(self, set_name: str) -> list[str]:
        return sorted(self._sets[set_name].keys())

    def has_player(self, set_name: str, player_name: str) -> bool:
        return player_name in self._sets[set_name]

    def list_card_types(self, set_name: str, player_name: str) -> list[str]:
        return sorted(self._sets[set_name][player_name])

    def has_card_type(self, set_name: str, player_name: str, card_type: str) -> bool:
        return card_type in self._sets[set_name][player_name]
