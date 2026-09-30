"""flashcards-ai: SM-2 spaced-repetition flashcards in your terminal.

Zero dependencies. Cards live in a JSON store; review sessions run
entirely offline.
"""

from .models import Card, Deck, Store
from .sm2 import grade, due_cards

__all__ = ["Card", "Deck", "Store", "grade", "due_cards"]
__version__ = "1.0.0"
