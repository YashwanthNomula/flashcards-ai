"""Card/deck models and the JSON store on disk."""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

from .sm2 import Schedule


def _default_home() -> Path:
    env = os.environ.get("FLASHCARDS_HOME")
    if env:
        return Path(env)
    return Path.home() / ".flashcards-ai"


@dataclass
class Card:
    front: str
    back: str
    tags: list[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    created: str = field(default_factory=lambda: date.today().isoformat())
    reviews: int = 0
    lapses: int = 0
    schedule: Schedule = field(default_factory=Schedule)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["schedule"]["due"] = self.schedule.due.isoformat() if self.schedule.due else None
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Card":
        sched = data.get("schedule", {})
        due = sched.get("due")
        schedule = Schedule(
            easiness=sched.get("easiness", 2.5),
            interval=sched.get("interval", 0),
            reps=sched.get("reps", 0),
            due=date.fromisoformat(due) if due else None,
        )
        return cls(
            front=data["front"],
            back=data["back"],
            tags=data.get("tags", []),
            id=data.get("id", uuid.uuid4().hex[:8]),
            created=data.get("created", date.today().isoformat()),
            reviews=data.get("reviews", 0),
            lapses=data.get("lapses", 0),
            schedule=schedule,
        )


@dataclass
class Deck:
    name: str
    cards: list[Card] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"name": self.name, "cards": [c.to_dict() for c in self.cards]}

    @classmethod
    def from_dict(cls, data: dict) -> "Deck":
        return cls(name=data["name"], cards=[Card.from_dict(c) for c in data.get("cards", [])])


class Store:
    """JSON-file store: one file per deck inside the home directory."""

    def __init__(self, home: Path | None = None):
        self.home = home or _default_home()
        self.home.mkdir(parents=True, exist_ok=True)

    def _path(self, name: str) -> Path:
        safe = "".join(ch if ch.isalnum() or ch in "-_ " else "_" for ch in name).strip()
        return self.home / f"{safe}.json"

    def deck_names(self) -> list[str]:
        return sorted(p.stem for p in self.home.glob("*.json"))

    def load(self, name: str) -> Deck:
        path = self._path(name)
        if not path.exists():
            return Deck(name=name)
        return Deck.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def save(self, deck: Deck) -> None:
        path = self._path(deck.name)
        path.write_text(json.dumps(deck.to_dict(), indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")

    def delete(self, name: str) -> bool:
        path = self._path(name)
        if path.exists():
            path.unlink()
            return True
        return False
