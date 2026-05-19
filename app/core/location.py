import pygeohash
from sqlalchemy import text

def fuzz_coordinates(lat: float, lng: float) -> tuple[float, float]:
    grid = 160 / 364000
    fuzzed_lat = round(lat / grid) * grid
    fuzzed_lng = round(lng / grid) * grid
    return fuzzed_lat, fuzzed_lng

def compute_geohash(lat: float, lng: float) -> str:
    return pygeohash.encode(lat, lng, precision=6)

def miles_to_meters(miles: float) -> float:
    return miles * 1609.34

def haversine_query(lat: float, lng: float, radius_miles: float):
    return text("""
                SELECT 
                    ul.user_id,
                    u.username,
                    ul.lat,
                    ul.lng,
                    3958.8 * 2 * ASIN(
                        SQRT(
                            POWER(SIN(RADIANS(ul.lat - :lat) / 2), 2) +
                            COS(RADIANS(:lat)) * COS(RADIANS(ul.lat)) *
                            POWER(SIN(RADIANS(ul.lng - :lng) / 2), 2)
                        )
                    ) AS distance_miles
                
                FROM user_locations ul
                JOIN users u ON u.id = ul.user_id
                WHERE ul.is_visible = true
                AND ul.user_id != :user_id
                HAVING distance_miles <= :radius_miles
                ORDER BY distance_miles ASC
                """)