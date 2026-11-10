import math
from dataclasses import replace
from typing import List, Tuple, Dict, Optional
from osm_simplify.models import Place, PlaceList

GRID_SIZE_DEG = 0.01  # ~1.1km grid cell size

def _to_grid_key(lat: float, lon: float) -> Tuple[int, int]:
    return (math.floor(lat / GRID_SIZE_DEG), math.floor(lon / GRID_SIZE_DEG))

class LocalSpatialIndex:
    """In-memory spatial hash grid for instantaneous O(1) POI candidate lookups."""
    
    def __init__(self):
        self._grid: Dict[Tuple[int, int], List[Place]] = {}

    def add(self, place: Place) -> None:
        key = _to_grid_key(place.lat, place.lon)
        if key not in self._grid:
            self._grid[key] = []
        self._grid[key].append(place)

    def query_nearby(
        self, 
        center_lat: float, 
        center_lon: float, 
        radius_m: float, 
        category_name: Optional[str] = None,
        custom_tags: Optional[Dict[str, str]] = None
    ) -> PlaceList:
        
        lat_delta = radius_m / 111_000.0
        lon_delta = radius_m / (111_000.0 * math.cos(math.radians(center_lat)))
        
        min_key = _to_grid_key(center_lat - lat_delta, center_lon - lon_delta)
        max_key = _to_grid_key(center_lat + lat_delta, center_lon + lon_delta)
        
        candidates: List[Place] = []
        for c_lat in range(min_key[0], max_key[0] + 1):
            for c_lon in range(min_key[1], max_key[1] + 1):
                cell_key = (c_lat, c_lon)
                if cell_key in self._grid:
                    candidates.extend(self._grid[cell_key])

        results = PlaceList()
        for place in candidates:
            
            if category_name:
                matches_cat = (place.category == category_name or place.subtype == category_name)
                if not matches_cat and hasattr(place, "raw_tags") and place.raw_tags:
                    matches_cat = any(k == category_name or v == category_name for k, v in place.raw_tags.items())
                if not matches_cat:
                    continue

            
            if custom_tags:
                if not (hasattr(place, "raw_tags") and place.raw_tags):
                    continue
                if not all(place.raw_tags.get(k) == v for k, v in custom_tags.items()):
                    continue

            
            dist = self._haversine(center_lat, center_lon, place.lat, place.lon)
            if dist <= radius_m:
                
                result_place = replace(place, distance_m=round(dist))
                results.append(result_place)

        results.sort(key=lambda p: p.distance_m)
        return results

    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        R = 6371000.0
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        a = math.sin(delta_phi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0)**2
        return R * (2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a)))