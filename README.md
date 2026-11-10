# 🌍 osm-simplify



`osm-simplify` is a lightweight, dependency-minimal Python library designed to make querying OpenStreetMap (OSM) data effortless. Whether you are building local spatial routing, geographic data parsers, or 100% offline mapping applications, this library bridges the gap between raw map data and clean, ready-to-use Python objects.



---



## 💡 Why Use `osm-simplify`? (The Benefits)



Working directly with OpenStreetMap's Overpass API or raw binary extracts can be tedious, requiring complex query syntax or heavy C++ bindings. `osm-simplify` solves this by giving you:



- **Zero Heavy GIS Bloat:** Avoid installing massive, hard-to-configure geographic libraries like `GDAL`, `GEOS`, or `PyPBF` just to load map extracts or perform local lookups.

- **Pure-Python PBF Binary Parser:** Native streaming `.osm.pbf` reader powered purely by standard library `zlib` and `struct`—no C/C++ build chains required.

- **Sub-Millisecond $O(1)$ Spatial Indexing:** Built-in `LocalSpatialIndex` partitions map primitives into ~$1.1\text{ km}$ spatial grid cells on cold start, delivering instant sub-millisecond offline lookups.

- **Smart Dual-Mode Engine:** Query live public Overpass servers with built-in failover, or seamlessly pass a local `.osm` XML or `.osm.pbf` file for offline parsing.

- **GeoJSON Batch Exports:** `PlaceList` collections export directly to RFC 7946-compliant GeoJSON `FeatureCollection` dictionaries ready for web mapping engines (Leaflet, Mapbox, Deck.gl).

- **Raw Tag Retention:** Full unparsed OpenStreetMap key-value dictionaries are preserved on every `Place` object for custom tag filtering (`tags={"historic": "castle"}`) and metadata inspection.



---



## 🚀 Installation & Local Clone



You can install the package directly from PyPI:



```bash

pip install osm-simplify

```



Or if you want to perform a local clone for development:



```bash

git clone https://github.com/DoguH72/osm-simplify.git

cd osm-simplify

pip install -e .

```



---



## 📖 Quick Start



### 1. Online / Hybrid Search



```python

import os

from osm_simplify import GeoFinder, Category



# Initialize search anchor (via address string or direct coordinates)

spot = GeoFinder.from_address("Piazza Castello", "Turin")



# Attach a local .osm XML or .osm.pbf file for offline fallback

if os.path.exists("nord-ovest-latest.osm.pbf"):

    spot.local_file = "nord-ovest-latest.osm.pbf"



# Find nearby food spots within 500m (automatically sorted by distance)

restaurants = spot.get_nearby(Category.FOOD, radius_m=500)



for place in restaurants[:5]:

    print(f"- {place.name} ({place.subtype}): {place.distance_m}m away")



# Find the single closest monument

closest = spot.get_closest(Category.MONUMENT, radius_m=1000)

if closest:

    print(f"Closest Monument: {closest.name} @ {closest.distance_m}m")

```



---



### 2. Pure Offline Mode (.osm.pbf Binary & .osm XML)



Pass a local PBF binary extract or XML file to bypass network calls completely. The engine builds an in-memory spatial grid hash map on cold start for instant lookups:



```python

from osm_simplify import GeoFinder, Category



# Pass local PBF file directly during initialization

spot = GeoFinder(

    lat=45.0705, 

    lon=7.6868, 

    location_name="Turin Center", 

    local_file="nord-ovest-latest.osm.pbf"

)



# Sub-millisecond indexed search

parks = spot.get_nearby(Category.PARK, radius_m=1000)

print(f"Found {len(parks)} parks offline in sub-milliseconds!")

```



---



### 3. Custom Tag Filtering & Raw Tag Access



Query exact OpenStreetMap key-value tags directly without preset dictionaries, and access original tag metadata:



```python

# Direct OSM tag key-value filter

castles = spot.get_nearby("historic", radius_m=1000, tags={"historic": "castle"})



# Access raw unparsed OSM tags on any returned Place

if castles:

    place = castles[0]

    print(f"Name:    {place.name}")

    print(f"Website: {place.raw_tags.get('website', 'N/A')}")

    print(f"Hours:   {place.raw_tags.get('opening_hours', 'N/A')}")

```



---



### 4. GeoJSON Exports for Web Maps



Export search results directly to GeoJSON format:



```python

import json



places = spot.get_nearby(Category.FOOD, radius_m=500)



# Export batch PlaceList collection to GeoJSON FeatureCollection dictionary

geojson_data = places.to_geojson()



with open("food_spots.geojson", "w", encoding="utf-8") as f:

    json.dump(geojson_data, f, indent=2)

```



---



## 🧩 Core API Reference



- **`GeoFinder(lat, lon, location_name=..., local_file=...)`**: Core spatial engine handling online API requests, mirror failovers, and offline PBF/XML spatial indexing.

- **`LocalSpatialIndex`**: In-memory spatial hash grid storing POI candidates inside ~$1.1\text{ km}$ bounding cells for instant $O(1)$ candidate lookups.

- **`Place`**: Clean dataclass representing a found location (`.name`, `.category`, `.subtype`, `.lat`, `.lon`, `.distance_m`, `.raw_tags`, `.to_dict()`, `.to_geojson_feature()`).

- **`PlaceList`**: Specialized collection list wrapping `Place` objects with batch operations like `.to_geojson()`.

- **`Category`**: Pre-configured presets (`Category.FOOD`, `Category.PARK`, `Category.MONUMENT`).

- **`OverpassServerError`**: Custom exception raised when all public Overpass mirrors are overloaded or unreachable.



---



## 📄 License



Distributed under the **MIT License**. Feel free to use, modify, and adapt it for your own projects!
