import importlib
from typing import Dict, List

# Lazy load spacy to avoid import-time DLL errors
def _load_spacy():
    try:
        spacy = importlib.import_module('spacy')
        # Load small model, will download if missing
        nlp = spacy.load('en_core_web_sm')
        return spacy, nlp
    except Exception as e:
        print(f'Spacy load failed: {e}')
        return None, None

_spacy, _nlp = _load_spacy()

PROBLEM_KEYWORDS = {
    'pothole': ['pothole', 'hole', 'road hole'],
    'garbage': ['garbage', 'trash', 'waste', 'litter'],
    'streetlight': ['streetlight', 'lamp', 'light', 'dark'],
    'damaged road': ['damaged road', 'crack', 'road damage', 'broken road'],
    'drainage': ['drainage', 'drain', 'flood', 'waterlogging'],
}
SEVERITY_KEYWORDS = {
    'high': ['dangerous', 'severe', 'critical', "can't", 'cannot', 'blocked', 'injury'],
    'medium': ['moderate', 'noticeable', 'slow', 'delay'],
    'low': ['minor', 'small', 'tiny', 'barely'],
}

def _match_keyword(text: str, keywords: List[str]) -> bool:
    import re
    for kw in keywords:
        if re.search(r'\\b' + re.escape(kw) + r'\\b', text, re.IGNORECASE):
            return True
    return False

def analyze_text(text: str) -> Dict:
    """Lightweight NLP analysis.
    Returns possible overrides:
        - problem_type (str) if a keyword matches
        - severity_clues (list) of detected severity levels
    """
    result: Dict = {}
    if not text or not _nlp:
        return result
    # Lowercase processing via spacy for tokenization (optional)
    doc = _nlp(text.lower())
    cleaned = doc.text
    for prob, kws in PROBLEM_KEYWORDS.items():
        if _match_keyword(cleaned, kws):
            result['problem_type'] = prob.title()
            break
    severity_clues = []
    for level, kws in SEVERITY_KEYWORDS.items():
        if _match_keyword(cleaned, kws):
            severity_clues.append(level.upper())
    if severity_clues:
        result['severity_clues'] = severity_clues
    return result
