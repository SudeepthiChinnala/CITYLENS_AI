from typing import Optional
import math

# Approximate centre points of the supported Hyderabad areas (lat, lon).
# Area detection assigns a point to the NEAREST centre (Voronoi-style), which avoids the
# overlapping / mis-placed rectangles used previously. Points farther than MAX_DISTANCE_KM
# from every centre are returned as "Unknown". In a real app use proper ward polygons.
AREA_CENTERS = {
    "Kukatpally":   (17.4849, 78.4138),
    "Madhapur":     (17.4483, 78.3915),
    "Ameerpet":     (17.4375, 78.4482),
    "Gachibowli":   (17.4401, 78.3489),
    "LB Nagar":     (17.3457, 78.5522),
    "Secunderabad": (17.4399, 78.4983),
    "Miyapur":      (17.4968, 78.3614),
    "Hitech City":  (17.4435, 78.3772),
}

MAX_DISTANCE_KM = 5.0


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def get_area(latitude: float, longitude: float) -> Optional[str]:
    """Return the nearest named area, or "Unknown" if outside the covered region."""
    best, best_d = None, float("inf")
    for area, (clat, clon) in AREA_CENTERS.items():
        d = _haversine_km(latitude, longitude, clat, clon)
        if d < best_d:
            best, best_d = area, d
    return best if best_d <= MAX_DISTANCE_KM else "Unknown"
