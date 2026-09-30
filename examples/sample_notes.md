# My Python study notes — import me with:
#   flashcards-ai import examples/sample_notes.md --deck python

Q: What does the GIL prevent in CPython?
A: True parallel execution of Python bytecode across threads.
   I/O-bound code still benefits from threading because the GIL
   is released during blocking I/O.

Q: What is the difference between `==` and `is`?
A: `==` compares values (calls `__eq__`), `is` compares identity
   (same object in memory).

Q: How do you make a deep copy of a nested list?
A: `copy.deepcopy(obj)` — a shallow `copy.copy` (or `list(obj)`)
   only copies the outer container.

Q: What does `@functools.lru_cache` do?
A: Memoizes function return values keyed by arguments, so repeated
   calls with the same args return instantly.

Q: When should you use a generator instead of a list?
A: When the sequence is large or infinite — generators yield items
   lazily and use O(1) memory instead of O(n).

Q: What is the MRO and how do you inspect it?
A: Method Resolution Order — the order Python searches base classes.
   Inspect with `ClassName.__mro__` or `ClassName.mro()`.
