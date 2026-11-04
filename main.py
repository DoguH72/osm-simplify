API_DICTIONARY = """
.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.
                     OSM-SIMPLIFY QUICK API DICTIONARY
.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.

CORE CLASSES & EXCEPTIONS

  . GeoFinder(lat, lon, ...) : Main search engine (remote or local offline).
  . Place                   : Simple data container for a found spot.
  . Category                : Pre-built, ready to use, simplified OSM tag presets.
  . OverpassServerError     : Raised when all remote public mirrors are busy or down.

CREATING A SEARCH INSTANCE :|

  . GeoFinder(lat, lon, location_name="...", local_file=None)
      - Direct coordinate initialization.
      - Pass `local_file="sample.osm"` for %100 offline local XML parsing.

  . GeoFinder.from_address(addr, city, country=None, local_file=None)
      - Resolves text to coordinates via Nominatim with Photon fuzzy fallback.

SEARCH METHODS :/

  . location.get_nearby(category, radius_m=1000, raise_on_error=False)
      - Returns a list of 'Place' objects, strictly sorted by distance_m.
      - Automatically clamps radius_m to MAX_RADIUS_M (1000m max) if the user tries to look for bigger radius'.
      - Expands automatically the necessary key-value selectors across node, way, and relation primitives.
      - Builtin memory cache to make repeated/similiar searches instantly (_query_cache).
      - Set 'raise_on_error=True' to explicitly catch server congestion.

  . location.get_closest(category, radius_m=1000)
      - Returns strictly the single closest 'Place' object, or 'None' if no match.

PLACE OBJECT ATTRIBUTES ;)

  . place.name        (str)   : Main location name (or its brand/type).
  . place.category    (str)   : Parent group ("food", "park", "monument").
  . place.subtype     (str)   : Specific OSM tag ("restaurant", "artwork", "memorial").
  . place.lat, .lon   (float) : Extracted coordinates (or area center lat/lon).
  . place.distance_m  (int)   : Real world Haversine distance in meters from origin with approx calculation.
  . place.to_dict()   (dict)  : Serializes Place instance to standard dictionary.

BUILT-IN PRESETS :)

  . Category.MONUMENT : Monuments, statues, memorials, public artwork, obelisks.
  . Category.PARK     : Parks, gardens, playgrounds, dog parks, green spaces.
  . Category.FOOD     : Restaurants, cafes, bars, pubs, fast food, food court, ice cream.

CUSTOM PRESETS & AUTOMATIC TAG EXPANSION 

  . Define a custom dict without worrying about explicit node/way/nwr syntax:
      MY_PRESET = {
          "name": "fountain",
          "overpass": ('["amenity"="fountain"]',)
      }

  . The engine automatically expands raw selectors into explicit node, way, 
    and relation queries behind the scenes, therefore its easy to use.

OFFLINE LOCAL FILE MODE (.osm XML)

  . Pass a local file path to bypass all HTTP endpoints have a problem free, fast library usage:
      geo = GeoFinder(45.0705, 7.6869, local_file="turin_sample.osm")
      places = geo.get_nearby(Category.FOOD, radius_m=500)

.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.
"""

# EXAMPLE USAGE :)

import os
from osm_simplify import GeoFinder, Category, OverpassServerError

LOCAL_OSM = "sample_lib.osm"

def main():


     
    # creating a referance point via address string (uses Nominatim/Photon under the hood)
    try:
        spot = GeoFinder.from_address("Piazza Castello", "Turin", "Italy")
        #spot = GeoFinder.from_address("Piazza Castello", "Turin", "Italy") also possible to negate the country name
    except ValueError:
        # direct lat/lon initialization fallback just in case
        spot = GeoFinder(45.0705, 7.6869, "Piazza Castello")

    # if public Overpass mirrors are busy or offline, attach a local .osm XML file
    if os.path.exists(LOCAL_OSM):
        spot.local_file = LOCAL_OSM


    
    # nearby search
    # can search up to 1000m (MAX_RADIUS_M) with auto sorted results available

    restaurants = spot.get_nearby(Category.FOOD, radius_m=500)

    print(f"Found {len(restaurants)} food spots within 500m of {spot.location_name}:")
    for place in restaurants[:3]:
        # Place is a dataclass with .name, .category, .subtype, .lat, .lon, .distance_m
        print(f" *** {place.name} ({place.subtype}): {place.distance_m}m away")


   # closest match searching

    closest_monument = spot.get_closest(Category.MONUMENT, radius_m=1000)
    if closest_monument:
        print(f"\nClosest monument: {closest_monument.name} at {closest_monument.distance_m}m")


    # creating custom preset/tag category

    # you can also get away with NOT writing a fix plate like nwr (node, way, relation)
    # those plate blocks are contructed by geo_finder.py

    FOUNTAIN_PRESET = {
        "name": "fountain",
        "overpass": ('["amenity"="fountain"]',)
    }

    fountains = spot.get_nearby(FOUNTAIN_PRESET, radius_m=800)
    print(f"\nFountains found: {len(fountains)}")


    # dict convert and offline-only mode
    
    if restaurants:
        # converting our place object to a python dict
        sample_dict = restaurants[0].to_dict()
        print("\nSerialized Place dict:", sample_dict)

    # pure offline initialization (bypasses network entirely)
    if os.path.exists(LOCAL_OSM):
        offline_spot = GeoFinder(45.0705, 7.6869, location_name="Offline Map", local_file=LOCAL_OSM)
        parks = offline_spot.get_nearby(Category.PARK, radius_m=1000)
        print(f"\n[Offline Engine] Parks found in {LOCAL_OSM}: {len(parks)}")


if __name__ == "__main__":
    main()