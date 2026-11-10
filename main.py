API_DICTIONARY = """
.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.
                    OSM-SIMPLIFY QUICK API DICTIONARY
.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.

CORE CLASSES & EXCEPTIONS

  . GeoFinder(lat, lon, ...) : Main search engine (remote or local offline).
  . Place                    : Simple data container for a found spot.
  . PlaceList                : Custom list collection of Places supporting batch exports.
  . LocalSpatialIndex        : In-memory O(1) spatial grid hash map for fast offline lookups.
  . Category                 : Pre-built, ready to use, simplified OSM tag presets.
  . OverpassServerError      : Raised when all remote public mirrors are busy or down.

CREATING A SEARCH INSTANCE :|

  . GeoFinder(lat, lon, location_name="...", local_file=None)
      - Direct coordinate initialization.
      - Pass `local_file="sample.osm"` or `"sample.osm.pbf"` for %100 offline local parsing.
      - Automatically builds an in-memory `LocalSpatialIndex` grid ONCE at startup.

  . GeoFinder.from_address(addr, city, country=None, local_file=None)
      - Resolves text to coordinates via Nominatim with Photon fuzzy fallback.

SEARCH METHODS :/

  . location.get_nearby(category, radius_m=1000, tags=None, raise_on_error=False)
      - Returns a 'PlaceList' of 'Place' objects, strictly sorted by distance_m.
      - Uses fast O(1) cell grid hash lookups when running in local offline file mode.
      - Automatically clamps radius_m to MAX_RADIUS_M (1000m max) if user asks for bigger radius'.
      - Pass `tags={"historic": "castle"}` to execute custom dict tag overrides.
      - Builtin memory cache to make repeated/similar searches instantly (_query_cache).
      - Set 'raise_on_error=True' to explicitly catch server congestion.

  . location.get_closest(category, radius_m=1000)
      - Returns strictly the single closest 'Place' object, or 'None' if no match.

PLACE OBJECT & COLLECTION EXPORTS ;)

  . place.name        (str)   : Main location name (or its brand/type).
  . place.category    (str)   : Parent group ("food", "park", "monument").
  . place.subtype     (str)   : Specific OSM tag ("restaurant", "artwork", "memorial").
  . place.lat, .lon   (float) : Extracted coordinates (or area center lat/lon).
  . place.distance_m  (int)   : Real world Haversine distance in meters from origin.
  . place.raw_tags    (dict)  : Full unparsed OSM tag dictionary for custom checks.
  . place.to_dict()   (dict)  : Serializes Place instance to standard dictionary.
  
  . place.to_geojson_feature() : Converts single Place to standard GeoJSON Feature dict.
  . placelist.to_geojson()     : Converts entire PlaceList batch to GeoJSON FeatureCollection!

BUILT-IN PRESETS :)

  . Category.MONUMENT : Monuments, statues, memorials, public artwork, obelisks.
  . Category.PARK     : Parks, gardens, playgrounds, dog parks, green spaces.
  . Category.FOOD     : Restaurants, cafes, bars, pubs, fast food, food court, ice cream.

OFFLINE LOCAL FILE MODE (.osm XML & .osm.pbf BINARY)

  . Pass a local file path (.osm or .osm.pbf) to bypass network endpoints completely:
      geo = GeoFinder(45.0705, 7.6869, local_file="turin_map.osm.pbf")
      places = geo.get_nearby(Category.FOOD, radius_m=500)
      
  . Loads and indexes into `LocalSpatialIndex` hash cells ONCE for instantaneous queries!

.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.
"""

# EXAMPLE USAGE :)

import time
import os
import json
from osm_simplify import GeoFinder, Category

def test_large_pbf():
    LOCAL_PBF = r"Your pbf path"

    if not os.path.exists(LOCAL_PBF):
        print(f"File not found: {LOCAL_PBF}")
        return

    print(f"=== Starting Cold Parse: {LOCAL_PBF} ===")
    t0 = time.perf_counter()
    spot = GeoFinder(45.0705, 7.6868, location_name="Turin Center", local_file=LOCAL_PBF)
    print(f"Successfully indexed PBF into RAM in {time.perf_counter() - t0:.2f}s")

    t1 = time.perf_counter()
    restaurants = spot.get_nearby(Category.FOOD, radius_m=500)
    print(f"\nQuery executed in: {(time.perf_counter() - t1) * 1000:.2f} ms")
    print(f"Found {len(restaurants)} food spots near Turin Center:")
    for place in restaurants[:5]:
        print(f" - {place}")

    print("\n=== Example 1: Direct Tag Filtering & Raw Attributes ===")
    wifi_spots = spot.get_nearby("amenity", radius_m=1000, tags={"internet_access": "wlan"})
    print(f"Wi-Fi spots found: {len(wifi_spots)}")
    if restaurants:
        tags = restaurants[0].raw_tags
        print(f"Sample Spot Tags ({restaurants[0].name}):")
        print(f"  - Cuisine: {tags.get('cuisine', 'N/A')}")
        print(f"  - Website: {tags.get('website', 'N/A')}")

    print("\n=== Example 2: Single Closest Spot & GeoJSON File Export ===")
    closest_park = spot.get_closest(Category.PARK, radius_m=1000)
    if closest_park:
        print(f"Closest park: {closest_park.name} ({closest_park.distance_m}m away)")

    if restaurants:
        geojson_data = restaurants.to_geojson()
        with open("turin_food.geojson", "w", encoding="utf-8") as f:
            json.dump(geojson_data, f, indent=2)
        print(f"Saved {len(geojson_data['features'])} features to 'turin_food.geojson'")

if __name__ == "__main__":
    test_large_pbf()