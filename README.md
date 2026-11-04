# 🌍 osm-simplify

`osm-simplify` is a lightweight, dependency-minimal Python library designed to make querying OpenStreetMap (OSM) data effortless. Whether you are building local search features, geographic data parsers, or offline mapping applications, this library bridges the gap between raw map data and clean, ready-to-use Python objects.

---

## 💡 Why Use `osm-simplify`? (The Benefits)

Working directly with OpenStreetMap's Overpass API or raw `.osm` XML files can be tedious, requiring complex query syntax and error-prone XML parsing. `osm-simplify` solves this by giving you:

- **Zero Heavy GIS Bloat:** Avoid installing massive, hard-to-configure geographic libraries like `GDAL` or `GeoPandas` just to find nearby places.
- **Smart Dual-Mode Engine:** Query live public Overpass servers with built-in failover, or seamlessly switch to parsing local `.osm` XML files offline when you're without internet or testing locally.
- **Automatic Tag Expansion:** You don't need to write complex Overpass QL syntax. Simple presets (like `Category.FOOD` or `Category.PARK`) automatically expand behind the scenes to capture relevant nodes, ways, and boundaries.
- **Instant Distance Sorting:** Search results are instantly cleaned up, converted into structured `Place` data classes, and sorted by physical distance from your target location.
- **Built-in Memory Caching:** Remembers recent queries to ensure fast repeat lookups without spamming public servers.

---

## 🚀 Installation & Local Clone

You can install the package directly from PyPI:

pip install osm-simplify

Or if you want to perform a local clone for development:

git clone https://github.com/DoguH72/osm-simplify.git
cd osm-simplify
pip install -e .

---

## 📖 Quick Start

Here is how simple it is to find nearby restaurants or historical monuments around a location:

import os
from osm_simplify import GeoFinder, Category

# 1. Initialize your search anchor (via address or direct coordinates)
spot = GeoFinder.from_address("Piazza Castello", "Turin")

# (Optional) Attach a local .osm XML file for offline fallback
if os.path.exists("sample_lib.osm"):
    spot.local_file = "sample_lib.osm"

# 2. Find nearby food spots within 500 meters (automatically sorted by distance!)
restaurants = spot.get_nearby(Category.FOOD, radius_m=500)

for place in restaurants:
    print(f"- {place.name} ({place.subtype}): {place.distance_m}m away")

# 3. Find the single closest monument
closest = spot.get_closest(Category.MONUMENT, radius_m=1000)
if closest:
    print(f"Closest Monument: {closest.name} @ {closest.distance_m}m")

---

## 🛠️ Custom Change (Custom Categories)

Need something specific that isn't in the default presets? You can define custom search filters on the fly:

CUSTOM_CAFE_FILTER = {
    "name": "cafes",
    "overpass": ('["amenity"="cafe"]',)
}

cafes = spot.get_nearby(CUSTOM_CAFE_FILTER, radius_m=600)

---

## 🧩 Core API Reference

- **`GeoFinder`**: The core spatial engine handling online API requests, failovers, and offline XML traversal.
- **`Place`**: A clean dataclass representing a location point (`.name`, `.category`, `.subtype`, `.lat`, `.lon`, `.distance_m`, `.to_dict()`).
- **`Category`**: Pre-configured presets (`Category.FOOD`, `Category.PARK`, `Category.MONUMENT`, etc.).
- **`OverpassServerError`**: Custom exception raised when public mapping mirrors are overloaded.

---

## 📄 License

Distributed under the **MIT License**. Feel free to use, modify, and adapt it for your own projects!
