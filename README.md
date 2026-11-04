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

## 🚀 Installation

You can install the library directly from PyPI:

```bash
pip install osm-simplify
