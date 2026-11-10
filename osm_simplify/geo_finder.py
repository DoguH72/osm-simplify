import math
import time
import requests
from typing import Optional, Union, Dict

from osm_simplify.models import Place, PlaceList, OverpassServerError
from osm_simplify.index import LocalSpatialIndex
from osm_simplify.pbf import load_local_file_to_index

class GeoFinder:
    USER_AGENT = 'SimpleOSMBot/1.0 (https://github.com/DoguH72/osm-simplify)'
    HTTP_TIMEOUT = (6, 30)
    MAX_RADIUS_M = 1000
    CACHE_MAX_SIZE = 128
    MIN_INTERVAL = 1.5

    OVERPASS_ENDPOINTS = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://overpass.private.coffee/api/interpreter",
    ]

    _query_cache = {}
    _last_overpass = 0.0
    _last_nominatim = 0.0
    _file_index_cache: Dict[str, LocalSpatialIndex] = {}

    def __init__(self, lat: float, lon: float, location_name: str = "Custom Coordinates", local_file: Optional[str] = None):
        self.lat = lat
        self.lon = lon
        self.location_name = location_name
        self.local_file = local_file
        
        # Load and index local file ONCE at initialization
        self.spatial_index: Optional[LocalSpatialIndex] = None
        if self.local_file:
            if self.local_file not in self._file_index_cache:
                self._file_index_cache[self.local_file] = load_local_file_to_index(self.local_file)
            self.spatial_index = self._file_index_cache[self.local_file]

    @classmethod
    def _rate_limit_nominatim(cls):
        wait = cls.MIN_INTERVAL - (time.monotonic() - cls._last_nominatim)
        if wait > 0:
            time.sleep(wait)
        cls._last_nominatim = time.monotonic()

    @classmethod
    def _rate_limit_overpass(cls):
        wait = cls.MIN_INTERVAL - (time.monotonic() - cls._last_overpass)
        if wait > 0:
            time.sleep(wait)
        cls._last_overpass = time.monotonic()

    @classmethod
    def from_address(cls, address: str, city: str, country: Optional[str] = None, local_file: Optional[str] = None):
        query_parts = [address.strip(), city.strip()]
        if country:
            query_parts.append(country.strip())
        query = ", ".join(query_parts)
        headers = {'User-Agent': cls.USER_AGENT, 'Accept': 'application/json'}

        cls._rate_limit_nominatim()
        try:
            resp = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params={'q': query, 'format': 'json', 'limit': 1},
                headers=headers,
                timeout=cls.HTTP_TIMEOUT
            )
            if resp.status_code == 200 and resp.json():
                data = resp.json()[0]
                return cls(float(data['lat']), float(data['lon']), data.get('display_name', query), local_file=local_file)
        except Exception:
            pass

        try:
            resp = requests.get(
                "https://photon.komoot.io/api/",
                params={'q': query, 'limit': 1},
                headers=headers,
                timeout=cls.HTTP_TIMEOUT
            )
            if resp.status_code == 200 and resp.json().get("features"):
                feat = resp.json()["features"][0]
                coords = feat["geometry"]["coordinates"]
                return cls(float(coords[1]), float(coords[0]), feat["properties"].get("name", query), local_file=local_file)
        except Exception:
            pass

        raise ValueError(f"Could not locate address: '{query}'")

    def _haversine(self, lat2: float, lon2: float) -> float:
        R = 6371000
        phi1, phi2 = math.radians(self.lat), math.radians(lat2)
        delta_phi = math.radians(lat2 - self.lat)
        delta_lambda = math.radians(lon2 - self.lon)
        a = math.sin(delta_phi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2)**2
        return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))

    def _extract_subtype(self, tags: dict) -> str:
        for key in ["historic", "tourism", "leisure", "amenity", "man_made", "landuse"]:
            if key in tags:
                return tags[key]
        return "general"

    def get_nearby(
        self, 
        category_config: Union[dict, str], 
        radius_m: int = 1000, 
        tags: Optional[Dict[str, str]] = None,
        raise_on_error: bool = False
    ) -> PlaceList:
        if radius_m > self.MAX_RADIUS_M:
            radius_m = self.MAX_RADIUS_M

        category_name = category_config["name"] if isinstance(category_config, dict) else category_config
        cache_key = (round(self.lat, 4), round(self.lon, 4), category_name, radius_m)

        if cache_key in self._query_cache:
            return self._query_cache[cache_key]

        # fast O(1) offline spatial index lookup
        if self.spatial_index:
            results = self.spatial_index.query_nearby(
                center_lat=self.lat,
                center_lon=self.lon,
                radius_m=radius_m,
                category_name=category_name,
                custom_tags=tags
            )
            self._query_cache[cache_key] = results
            return results

        #online overpass request handling
        category_tags = category_config["overpass"] if isinstance(category_config, dict) else (f'["{category_config}"]',)
        if isinstance(category_tags, str):
            category_tags = (category_tags,)

        lat_clean = round(self.lat, 5)
        lon_clean = round(self.lon, 5)

        union_lines = []
        for tag in category_tags:
            clean_tag = tag.strip().rstrip(';')
            if not clean_tag.startswith('['):
                clean_tag = f'[{clean_tag}]'
            union_lines.append(f"node{clean_tag}(around:{radius_m},{lat_clean},{lon_clean});")
            union_lines.append(f"way{clean_tag}(around:{radius_m},{lat_clean},{lon_clean});")

        union_body = "\n".join(union_lines)
        overpass_query = f"[out:json][timeout:25];\n(\n{union_body}\n);\nout center;"

        post_headers = {
            'User-Agent': self.USER_AGENT,
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
        }

        payload = None
        for url in self.OVERPASS_ENDPOINTS:
            self._rate_limit_overpass()
            try:
                resp = requests.post(url, data={'data': overpass_query}, headers=post_headers, timeout=self.HTTP_TIMEOUT)
                if resp.status_code == 200:
                    data = resp.json()
                    if "elements" in data:
                        payload = data
                        break
            except Exception:
                pass

        if not payload:
            if raise_on_error:
                raise OverpassServerError("All public Overpass servers are currently busy or down.")
            return PlaceList()

        places = PlaceList()
        for elem in payload.get("elements", []):
            elem_tags = elem.get("tags", {})
            subtype = self._extract_subtype(elem_tags)
            raw_name = elem_tags.get("name") or elem_tags.get("brand") or elem_tags.get("operator") or f"Unnamed {subtype.capitalize()}"

            e_lat = elem.get("lat") or (elem.get("center", {}).get("lat") if isinstance(elem.get("center"), dict) else None)
            e_lon = elem.get("lon") or (elem.get("center", {}).get("lon") if isinstance(elem.get("center"), dict) else None)

            if e_lat is not None and e_lon is not None:
                places.append(Place(
                    name=raw_name,
                    category=category_name,
                    subtype=subtype,
                    lat=e_lat,
                    lon=e_lon,
                    distance_m=round(self._haversine(e_lat, e_lon)),
                    raw_tags=elem_tags
                ))

        places.sort(key=lambda p: p.distance_m)
        if places:
            self._query_cache[cache_key] = places
        return places

    def get_closest(self, category_config: dict, radius_m: int = 1000) -> Optional[Place]:
        results = self.get_nearby(category_config, radius_m=radius_m)
        return results[0] if results else None