"""Shared repository query helpers."""

from collections.abc import Callable, Iterable
from functools import lru_cache
import re
from typing import TypeVar


_T = TypeVar("_T")


@lru_cache(maxsize=128)
def _like_substring_pattern(term: str, escape: str) -> re.Pattern[str]:
    pieces = [".*"]
    index = 0
    while index < len(term):
        char = term[index]
        if escape and char == escape and index + 1 < len(term):
            index += 1
            pieces.append(re.escape(term[index]))
        elif char == "%":
            pieces.append(".*")
        elif char == "_":
            pieces.append(".")
        else:
            pieces.append(re.escape(char))
        index += 1
    pieces.append(".*")
    return re.compile("".join(pieces), flags=re.DOTALL)


def matches_like_substring(value: str | None, term: str, *, escape: str = "\\") -> bool:
    """Match a lowercased value as SQL ``LIKE '%term%'`` would.

    Admin repository searches historically differ in whether they explicitly
    escape wildcard characters. Passing ``escape=''`` treats backslashes
    literally; the default preserves PostgreSQL's backslash escape behavior.
    """
    if value is None:
        return False
    return _like_substring_pattern(term, escape).fullmatch(value.lower()) is not None


def page_filtered_candidates(
    candidates: Iterable[_T],
    predicate: Callable[[_T], bool],
    *,
    page: int,
    page_size: int,
) -> tuple[list[_T], int]:
    """Filter an ordered stream before counting and pagination.

    Encrypted contact substring searches cannot use a database LIKE predicate.
    Callers stream every database-eligible candidate with ``yield_per``; this
    helper retains only the requested page while still returning an exact total.
    The full eligible candidate set must be scanned for each such search.
    """
    first = (page - 1) * page_size
    end = first + page_size
    matches: list[_T] = []
    total = 0
    for candidate in candidates:
        if not predicate(candidate):
            continue
        if first <= total < end:
            matches.append(candidate)
        total += 1
    return matches, total
