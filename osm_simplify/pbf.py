import zlib
import struct
import xml.etree.ElementTree as ET
from typing import Dict, List, Tuple, Optional
from osm_simplify.models import Place
from osm_simplify.index import LocalSpatialIndex

# xoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxo

#global tag helpers

# xoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxo

def _extract_subtype(tags: dict) -> str:
    for key in ["historic", "tourism", "leisure", "amenity", "man_made", "landuse"]:
        if key in tags:
            return tags[key]
    return "general"

def _map_category(tags: dict) -> str:
    amenity = tags.get("amenity", "")
    tourism = tags.get("tourism", "")
    historic = tags.get("historic", "")
    leisure = tags.get("leisure", "")
    landuse = tags.get("landuse", "")

    if amenity in {"restaurant", "cafe", "bar", "pub", "fast_food", "food_court", "ice_cream"}:
        return "food"
    if historic in {"monument", "memorial", "statue"} or tourism == "artwork" or tags.get("man_made") == "obelisk":
        return "monument"
    if leisure in {"park", "garden", "playground", "dog_park"} or landuse in {"recreation_ground", "village_green"}:
        return "park"

    return amenity or tourism or historic or leisure or "general"


# xoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxo

#lightweight non-dependent PBF binary decoder

# xoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxo


class _VarintDecoder:
    @staticmethod
    def read_varint(data: bytes, pos: int) -> Tuple[int, int]:
        res = 0
        shift = 0
        while True:
            b = data[pos]
            pos += 1
            res |= (b & 0x7F) << shift
            if not (b & 0x80):
                break
            shift += 7
        return res, pos

    @staticmethod
    def read_svarint(data: bytes, pos: int) -> Tuple[int, int]:
        val, pos = _VarintDecoder.read_varint(data, pos)
        return (val >> 1) ^ (-(val & 1)), pos


class PBFReader:
    """Python streaming parser for OpenStreetMap .osm.pbf files."""

    def __init__(self, filepath: str):
        self.filepath = filepath

    def populate_index(self, index: LocalSpatialIndex) -> None:
        block_count = 0
        with open(self.filepath, "rb") as f:
            while True:
                header_size_bytes = f.read(4)
                if not header_size_bytes or len(header_size_bytes) < 4:
                    break
                header_size = struct.unpack(">I", header_size_bytes)[0]
                header_data = f.read(header_size)

                blob_size = self._parse_blob_header(header_data)
                blob_data = f.read(blob_size)

                decompressed_block = self._parse_blob(blob_data)
                if decompressed_block:
                    self._parse_primitive_block(decompressed_block, index)

                block_count += 1
                if block_count % 500 == 0:
                    print(f"   [PBF Progress] Processed {block_count} binary blocks...")

    def _parse_blob_header(self, data: bytes) -> int:
        pos = 0
        datasize = 0
        while pos < len(data):
            key, pos = _VarintDecoder.read_varint(data, pos)
            field_num = key >> 3
            wire_type = key & 0x7
            if field_num == 3 and wire_type == 0:  
                datasize, pos = _VarintDecoder.read_varint(data, pos)
            else:
                pos = self._skip_field(data, pos, wire_type)
        return datasize

    def _parse_blob(self, data: bytes) -> Optional[bytes]:
        pos = 0
        zlib_data = None
        raw_data = None

        while pos < len(data):
            key, pos = _VarintDecoder.read_varint(data, pos)
            field_num = key >> 3
            wire_type = key & 0x7
            if field_num == 1 and wire_type == 2:  
                length, pos = _VarintDecoder.read_varint(data, pos)
                raw_data = data[pos : pos + length]
                pos += length
            elif field_num == 3 and wire_type == 2:  
                length, pos = _VarintDecoder.read_varint(data, pos)
                zlib_data = data[pos : pos + length]
                pos += length
            else:
                pos = self._skip_field(data, pos, wire_type)

        if zlib_data:
            return zlib.decompress(zlib_data)
        return raw_data

    def _skip_field(self, data: bytes, pos: int, wire_type: int) -> int:
        if wire_type == 0:
            _, pos = _VarintDecoder.read_varint(data, pos)
        elif wire_type == 1:
            pos += 8
        elif wire_type == 2:
            length, pos = _VarintDecoder.read_varint(data, pos)
            pos += length
        elif wire_type == 5:
            pos += 4
        return pos

    def _parse_primitive_block(self, data: bytes, index: LocalSpatialIndex) -> None:
        pos = 0
        string_table: List[str] = []
        lat_offset, lon_offset = 0, 0
        granularity = 100

        
        while pos < len(data):
            key, pos = _VarintDecoder.read_varint(data, pos)
            field_num = key >> 3
            wire_type = key & 0x7

            if field_num == 1 and wire_type == 2:  
                length, pos = _VarintDecoder.read_varint(data, pos)
                st_end = pos + length
                while pos < st_end:
                    _, pos = _VarintDecoder.read_varint(data, pos)
                    st_len, pos = _VarintDecoder.read_varint(data, pos)
                    string_table.append(data[pos : pos + st_len].decode("utf-8", errors="ignore"))
                    pos += st_len
            elif field_num == 17 and wire_type == 0: 
                granularity, pos = _VarintDecoder.read_varint(data, pos)
            elif field_num == 19 and wire_type == 0:  
                lat_offset, pos = _VarintDecoder.read_varint(data, pos)
            elif field_num == 20 and wire_type == 0:  
                lon_offset, pos = _VarintDecoder.read_varint(data, pos)
            elif field_num == 2 and wire_type == 2:  
                length, pos = _VarintDecoder.read_varint(data, pos)
                group_data = data[pos : pos + length]
                pos += length
                self._parse_primitive_group(
                    group_data, string_table, granularity, lat_offset, lon_offset, index
                )
            else:
                pos = self._skip_field(data, pos, wire_type)

    def _parse_primitive_group(
        self,
        data: bytes,
        string_table: List[str],
        granularity: int,
        lat_offset: int,
        lon_offset: int,
        index: LocalSpatialIndex
    ) -> None:
        pos = 0
        while pos < len(data):
            key, pos = _VarintDecoder.read_varint(data, pos)
            field_num = key >> 3
            wire_type = key & 0x7

            if field_num == 2 and wire_type == 2:  
                length, pos = _VarintDecoder.read_varint(data, pos)
                dense_end = pos + length
                self._parse_dense_nodes(
                    data[pos:dense_end], string_table, granularity, lat_offset, lon_offset, index
                )
                pos = dense_end
            else:
                pos = self._skip_field(data, pos, wire_type)

    def _parse_dense_nodes(
        self,
        data: bytes,
        string_table: List[str],
        granularity: int,
        lat_offset: int,
        lon_offset: int,
        index: LocalSpatialIndex
    ) -> None:
        pos = 0
        last_lat, last_lon = 0, 0
        id_data, lat_data, lon_data, keys_vals_data = [], [], [], []

        
        while pos < len(data):
            key, pos = _VarintDecoder.read_varint(data, pos)
            field_num = key >> 3
            wire_type = key & 0x7

            if field_num == 1 and wire_type == 2:  
                length, pos = _VarintDecoder.read_varint(data, pos)
                end = pos + length
                while pos < end:
                    val, pos = _VarintDecoder.read_svarint(data, pos)
                    id_data.append(val)
            elif field_num == 8 and wire_type == 2:  
                length, pos = _VarintDecoder.read_varint(data, pos)
                end = pos + length
                while pos < end:
                    val, pos = _VarintDecoder.read_svarint(data, pos)
                    lat_data.append(val)
            elif field_num == 9 and wire_type == 2:  
                length, pos = _VarintDecoder.read_varint(data, pos)
                end = pos + length
                while pos < end:
                    val, pos = _VarintDecoder.read_svarint(data, pos)
                    lon_data.append(val)
            elif field_num == 10 and wire_type == 2:  
                length, pos = _VarintDecoder.read_varint(data, pos)
                end = pos + length
                while pos < end:
                    val, pos = _VarintDecoder.read_varint(data, pos)
                    keys_vals_data.append(val)
            else:
                pos = self._skip_field(data, pos, wire_type)

        
        kv_idx = 0
        for i in range(len(id_data)):
            last_lat += lat_data[i]
            last_lon += lon_data[i]

            lat = (lat_offset + (last_lat * granularity)) / 1e9
            lon = (lon_offset + (last_lon * granularity)) / 1e9

            tags = {}
            if keys_vals_data:
                while kv_idx < len(keys_vals_data):
                    k_idx = keys_vals_data[kv_idx]
                    kv_idx += 1
                    if k_idx == 0:  
                        break
                    v_idx = keys_vals_data[kv_idx]
                    kv_idx += 1
                    if k_idx < len(string_table) and v_idx < len(string_table):
                        tags[string_table[k_idx]] = string_table[v_idx]

           
            if tags:
                subtype = _extract_subtype(tags)
                name = tags.get("name") or tags.get("brand") or tags.get("operator") or f"Unnamed {subtype.capitalize()}"
                category = _map_category(tags)

                index.add(Place(
                    name=name,
                    category=category,
                    subtype=subtype,
                    lat=lat,
                    lon=lon,
                    distance_m=0,
                    raw_tags=tags
                ))

#xoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxo

#file to index loader (.osm & .osm.pbf)

#xoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxoxo

def load_local_file_to_index(filepath: str) -> LocalSpatialIndex:
    """Unified file loader. Automatically routes XML (.osm) or binary (.osm.pbf) to index."""
    index = LocalSpatialIndex()

    if filepath.endswith(".pbf"):
        pbf_reader = PBFReader(filepath)
        pbf_reader.populate_index(index)

    elif filepath.endswith(".osm"):
        tree = ET.parse(filepath)
        root = tree.getroot()
        node_coords = {}

        for node in root.findall("node"):
            node_coords[node.attrib['id']] = (float(node.attrib['lat']), float(node.attrib['lon']))

        for node in root.findall("node"):
            tags = {tag.attrib['k']: tag.attrib['v'] for tag in node.findall("tag")}
            if not tags:
                continue
            subtype = _extract_subtype(tags)
            name = tags.get("name") or tags.get("brand") or tags.get("operator") or f"Unnamed {subtype.capitalize()}"
            category = _map_category(tags)
            
            index.add(Place(
                name=name,
                category=category,
                subtype=subtype,
                lat=float(node.attrib['lat']),
                lon=float(node.attrib['lon']),
                distance_m=0,
                raw_tags=tags
            ))

        for way in root.findall("way"):
            tags = {tag.attrib['k']: tag.attrib['v'] for tag in way.findall("tag")}
            if not tags:
                continue
            lats, lons = [], []
            for nd in way.findall("nd"):
                ref = nd.attrib.get("ref")
                if ref in node_coords:
                    lats.append(node_coords[ref][0])
                    lons.append(node_coords[ref][1])
            if lats:
                subtype = _extract_subtype(tags)
                name = tags.get("name") or tags.get("brand") or f"Unnamed {subtype.capitalize()}"
                category = _map_category(tags)
                
                index.add(Place(
                    name=name,
                    category=category,
                    subtype=subtype,
                    lat=sum(lats) / len(lats),
                    lon=sum(lons) / len(lons),
                    distance_m=0,
                    raw_tags=tags
                ))

    return index