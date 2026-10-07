from typing import Dict, List

SEVERITY_SCORES = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}

def determine_severity(image_confidence: float, nlp_result: Dict) -> str:
    """Determine final severity level.
    - Start from image confidence based heuristic.
    - Boost if NLP severity clues contain HIGH/MEDIUM.
    - Clamp to LOW/MEDIUM/HIGH.
    """
    # Base severity from image confidence
    if image_confidence > 0.85:
        base = "HIGH"
    elif image_confidence > 0.6:
        base = "MEDIUM"
    else:
        base = "LOW"
    # Check NLP clues
    clues: List[str] = nlp_result.get("severity_clues", [])
    if "HIGH" in clues:
        return "HIGH"
    if "MEDIUM" in clues and base == "LOW":
        return "MEDIUM"
    return base
