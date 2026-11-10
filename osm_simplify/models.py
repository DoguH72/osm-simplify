
from dataclasses import dataclass, field, asdict
from typing import Dict, Any

class OverpassServerError(Exception):
    """Raised when all Overpass API mirrors fail or are overloaded."""
    pass

@dataclass
class Place:
    name: str
    category: str
    subtype: str
    lat: float
    lon: float
    distance_m: int
    raw_tags: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_geojson_feature(self) -> Dict[str, Any]:
        """Convert a single Place to a GeoJSON Feature dictionary."""
        return {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [self.lon, self.lat]  #GeoJSON is [lon, lat] :)
            },
            "properties": {
                "name": self.name,
                "category": self.category,
                "subtype": self.subtype,
                "distance_m": self.distance_m,
                "tags": self.raw_tags
            }
        }

    def __repr__(self):
        return f"<{self.name} [{self.category}:{self.subtype}] - {self.distance_m}m away>"


class PlaceList(list):
    """Custom list wrapper to support batch .to_geojson() exports on returned places."""
    
    def to_geojson(self) -> Dict[str, Any]:
        """Export the entire result list as a standard GeoJSON FeatureCollection."""
        return {
            "type": "FeatureCollection",
            "features": [place.to_geojson_feature() for place in self]
        }


class Category:
    MONUMENT = {
        "name": "monument",
        "overpass": (
            '["historic"~"monument|memorial|statue"]',
            '["tourism"="artwork"]',
            '["man_made"="obelisk"]',
        ),
    }
    PARK = {
        "name": "park",
        "overpass": (
            '["leisure"~"park|garden|playground|dog_park"]',
            '["landuse"~"recreation_ground|village_green"]',
        ),
    }
    FOOD = {
        "name": "food",
        "overpass": (
            '["amenity"~"restaurant|cafe|bar|pub|fast_food|food_court|ice_cream"]',
        ),
    }