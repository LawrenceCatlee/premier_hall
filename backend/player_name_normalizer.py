"""
Player Name Normalization Module

This module provides standardized player name normalization functions
for matching player names across different data sources (Transfermarkt, 
Pulselive, Wikipedia, etc.).

Used by:
- premier_league_awards.py
- player_premier_team_200.py
"""

import re
import unicodedata
from typing import Dict


# Nickname map (extend as you find more cases)
NICKNAME_MAP = {
    "andy": "andrew",
    "alex": "alexander",
    "mike": "michael",
    "tony": "anthony",
    "dave": "david",
    "rob": "robert",
    "bob": "robert",
    "jim": "james",
    "bill": "william",
    "ben": "benjamin",
    "sam": "samuel",
    "matt": "matthew",
}

# Special name mapping for Transfermarkt to Pulselive matching
SPECIAL_NAME_MAP = {
    "alisson": "alisson becker",  # Alisson -> Alisson Becker
    "heung-min son": "son heung-min",  # Heung-min Son -> Son Heung-min
    "yakubu aiyegbeni": "yakubu",  # Yakubu Aiyegbeni -> Yakubu
    "Gabriel": "Gabriel Magalhães"
}

# Extra transliteration for common football-name characters
# (unicodedata strip doesn't convert ligatures like æ -> ae)
TRANSLIT_MULTI = {
    "æ": "ae",
    "Æ": "Ae",
    "œ": "oe",
    "Œ": "Oe",
    "ø": "o",
    "Ø": "O",
    "å": "a",
    "Å": "A",
    "ß": "ss",
}


def clean_text(x) -> str:
    """Remove footnotes and special characters from text"""
    s = "" if pd.isna(x) else str(x)
    s = re.sub(r"\[[^\]]+\]", "", s)  # remove [a], [1]...
    s = s.replace("†", "").replace("‡", "").replace("§", "").replace("#", "")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def clean_player_name(name: str) -> str:
    """Clean player name by removing counters and footnotes"""
    s = clean_text(name)
    # remove trailing "(2)" style counters
    s = re.sub(r"\s*\(\d+\)\s*$", "", s).strip()
    return s


def _strip_accents(s: str) -> str:
    """Remove diacritics and special characters"""
    # Apply custom transliteration first
    for old, new in TRANSLIT_MULTI.items():
        s = s.replace(old, new)
    
    # Then apply Unicode normalization
    return "".join(ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch))


def normalize_player_name(s: str) -> str:
    """
    Normalize player name for matching:
    - lowercase
    - transliterate + strip accents (Solskjær -> solskjaer)
    - remove punctuation
    - collapse spaces
    - unify ij -> y (Nistelrooij <-> Nistelrooy)
    - apply special name mappings
    """
    s = clean_player_name(s).lower().strip()
    
    # Apply special name mapping first
    if s in SPECIAL_NAME_MAP:
        s = SPECIAL_NAME_MAP[s]
    
    s = _strip_accents(s)

    # unify ij -> y (helps Dutch spelling variants)
    s = s.replace("ij", "y")

    # keep letters/numbers/spaces only
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def apply_nickname(norm: str) -> str:
    """Apply nickname mapping to first name"""
    parts = norm.split()
    if not parts:
        return norm
    if parts[0] in NICKNAME_MAP:
        parts[0] = NICKNAME_MAP[parts[0]]
    return " ".join(parts)


def first_last_only(norm: str) -> str:
    """Keep only first and last name for matching"""
    parts = norm.split()
    if len(parts) <= 2:
        return norm
    return f"{parts[0]} {parts[-1]}"


def last_token(norm: str) -> str:
    """Get last token (usually last name) for matching"""
    parts = norm.split()
    return parts[-1] if parts else ""


def standardize_player_name_for_matching(name: str) -> str:
    """
    Standardize player name for matching across different data sources.
    This is the main function to use for name normalization.
    """
    # Apply basic normalization
    normalized = normalize_player_name(name)
    
    # Apply nickname mapping
    normalized = apply_nickname(normalized)
    
    return normalized


# Import pandas for clean_text function
try:
    import pandas as pd
except ImportError:
    # Fallback if pandas not available
    class pd:
        @staticmethod
        def isna(x):
            return x is None or (isinstance(x, str) and x.strip() == "")


def similarity_score(a: str, b: str) -> float:
    """Calculate similarity score between two strings"""
    from difflib import SequenceMatcher
    return SequenceMatcher(None, a, b).ratio()
