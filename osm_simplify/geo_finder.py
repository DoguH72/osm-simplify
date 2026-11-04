import math
import time
import requests
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict
from typing import Optional

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

    def to_dict(self) -> dict:
        return asdict(self)

    def __repr__(self):
        return f"<{self.name} [{self.category}:{self.subtype}] - {self.distance_m}m away>"

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

    def __init__(self, lat: float, lon: float, location_name: str = "Custom Coordinates", local_file: Optional[str] = None):
        self.lat = lat
        self.lon = lon
        self.location_name = location_name
        self.local_file = local_file  # Path to local .osm XML file if available

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
        # Dynamically build search query whether country is provided or not
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

    def _parse_local_osm(self, category_config: dict, radius_m: int) -> list[Place]:
        """Parses a local .osm XML file offline for both node points and way polygons."""
        if not self.local_file:
            return []

        tree = ET.parse(self.local_file)
        root = tree.getroot()
        places = []

        # Index node coordinates for calculating way centroids
        node_coords = {}
        for node in root.findall("node"):
            node_id = node.attrib['id']
            node_coords[node_id] = (float(node.attrib['lat']), float(node.attrib['lon']))

        category_name = category_config["name"]
        category_tags = category_config["overpass"]
        if isinstance(category_tags, str):
            category_tags = (category_tags,)

        # Build matching rules from Category selectors
        match_rules = []
        for raw_tag in category_tags:
            clean = raw_tag.strip(' []"\'')
            if '~' in clean:
                k, v_str = clean.split('~', 1)
                allowed_vals = set(v_str.strip('[]"\'').split('|'))
                match_rules.append((k.strip('[]"\''), allowed_vals, True))  # Regex match
            elif '=' in clean:
                k, v = clean.split('=', 1)
                match_rules.append((k.strip('[]"\''), {v.strip('[]"\'')}, False))  # Exact match

        def check_tags(tags: dict) -> bool:
            for key, allowed_vals, is_regex in match_rules:
                if key in tags:
                    val = tags[key]
                    if is_regex and any(v in val for v in allowed_vals):
                        return True
                    elif not is_regex and val in allowed_vals:
                        return True
            return False

        # 1. Parse standalone <node> elements
        for node in root.findall("node"):
            tags = {tag.attrib['k']: tag.attrib['v'] for tag in node.findall("tag")}
            if not tags or not check_tags(tags):
                continue

            e_lat, e_lon = float(node.attrib['lat']), float(node.attrib['lon'])
            dist = round(self._haversine(e_lat, e_lon))

            if dist <= radius_m:
                subtype = self._extract_subtype(tags)
                raw_name = tags.get("name") or tags.get("brand") or tags.get("operator") or f"Unnamed {subtype.capitalize()}"
                places.append(Place(
                    name=raw_name,
                    category=category_name,
                    subtype=subtype,
                    lat=e_lat,
                    lon=e_lon,
                    distance_m=dist
                ))

        # 2. Parse building/area <way> elements
        for way in root.findall("way"):
            tags = {tag.attrib['k']: tag.attrib['v'] for tag in way.findall("tag")}
            if not tags or not check_tags(tags):
                continue

            way_lats, way_lons = [], []
            for nd in way.findall("nd"):
                ref = nd.attrib.get("ref")
                if ref in node_coords:
                    lat, lon = node_coords[ref]
                    way_lats.append(lat)
                    way_lons.append(lon)

            if not way_lats:
                continue

            e_lat = sum(way_lats) / len(way_lats)
            e_lon = sum(way_lons) / len(way_lons)
            dist = round(self._haversine(e_lat, e_lon))

            if dist <= radius_m:
                subtype = self._extract_subtype(tags)
                raw_name = tags.get("name") or tags.get("brand") or tags.get("operator") or f"Unnamed {subtype.capitalize()}"
                places.append(Place(
                    name=raw_name,
                    category=category_name,
                    subtype=subtype,
                    lat=e_lat,
                    lon=e_lon,
                    distance_m=dist
                ))

        places.sort(key=lambda p: p.distance_m)
        return places

    def get_nearby(self, category_config: dict, radius_m: int = 1000, raise_on_error: bool = False) -> list[Place]:
        if radius_m > self.MAX_RADIUS_M:
            print(f"[Warning] Requested radius {radius_m}m exceeds {self.MAX_RADIUS_M}m limit. Clamping to {self.MAX_RADIUS_M}m.")
            radius_m = self.MAX_RADIUS_M

        category_name = category_config["name"]
        cache_key = (round(self.lat, 4), round(self.lon, 4), category_name, radius_m)

        # 1. Check LRU Cache FIRST
        if cache_key in self._query_cache:
            return self._query_cache[cache_key]

        # 2. Offline local mode check
        if self.local_file:
            print(f"[Info] Reading from local file: {self.local_file}")
            places = self._parse_local_osm(category_config, radius_m)
            self._query_cache[cache_key] = places
            return places

        category_tags = category_config["overpass"]
        if isinstance(category_tags, str):
            category_tags = (category_tags,)

        lat_clean = round(self.lat, 5)
        lon_clean = round(self.lon, 5)

        # Construct query lines for online Overpass mirrors
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
        server_errors = []

        # 3. Iterate through online endpoints
        for url in self.OVERPASS_ENDPOINTS:
            self._rate_limit_overpass()
            try:
                resp = requests.post(
                    url, 
                    data={'data': overpass_query}, 
                    headers=post_headers, 
                    timeout=self.HTTP_TIMEOUT
                )
                if resp.status_code == 200:
                    try:
                        data = resp.json()
                        if "elements" in data:
                            payload = data
                            break
                    except ValueError:
                        server_errors.append(f"{url}: HTML 200 response (busy/throttled)")
                else:
                    server_errors.append(f"{url}: HTTP {resp.status_code}")
            except Exception as e:
                server_errors.append(f"{url}: {type(e).__name__}")

        if not payload:
            err_msg = f"[API Error] All Overpass servers failed or are busy. Server logs: {server_errors}"
            print(err_msg)
            if raise_on_error:
                raise OverpassServerError("All public Overpass servers are currently busy or down. Please try again in a few moments.")
            return []

        places = []
        for elem in payload.get("elements", []):
            tags = elem.get("tags", {})
            subtype = self._extract_subtype(tags)
            raw_name = tags.get("name") or tags.get("brand") or tags.get("operator") or f"Unnamed {subtype.capitalize()}"

            e_lat = elem.get("lat")
            e_lon = elem.get("lon")
            if e_lat is None or e_lon is None:
                center = elem.get("center")
                if isinstance(center, dict):
                    e_lat = center.get("lat")
                    e_lon = center.get("lon")

            if e_lat is not None and e_lon is not None:
                places.append(Place(
                    name=raw_name,
                    category=category_name,
                    subtype=subtype,
                    lat=e_lat,
                    lon=e_lon,
                    distance_m=round(self._haversine(e_lat, e_lon))
                ))

        places.sort(key=lambda p: p.distance_m)

        if places:
            self._query_cache[cache_key] = places
            if len(self._query_cache) > self.CACHE_MAX_SIZE:
                del self._query_cache[next(iter(self._query_cache))]

        return places

    def get_closest(self, category_config: dict, radius_m: int = 1000):
        results = self.get_nearby(category_config, radius_m=radius_m)
        return results[0] if results else None