import os
import sys
import sqlite3

import numpy as np
import pygeos as pg
from pyproj import CRS

APPLICATION_ID = 1196444487
USER_VERSION = 10200

### Geopackage header structure

## header magic number, 2 bytes
# magic = b"GP"  # same as b"\x47\x50"
## BLOB version (0), 1 byte
# blob_version = b"\x00"
## Flags:
# 2 bits: 00
# 1 bit: 0 (empty geometry flag)
# 3 bits: 001 (bounds type: XY)
# 1 bit: endian type of platform writing this header (hardcoded to 'little')
# flags = np.packbits([1,1,0,0,0,0,0,0], bitorder='little') => 3 => b'0b11'
# note the inverse order
# flags = b'0b11' => b'\x03'

GP_HEADER_BOUNDS = b"\x47\x50\x00\x03"
GP_HEADER_NOBOUNDS = b"\x47\x50\x00\x01"


class Geopackage(object):
    def __init__(self, filename, mode="r"):
        # 1.1.1.1.2: A GeoPackage SHALL have the file extension name ".gpkg".
        if not filename.endswith(".gpkg"):
            filename = "{}.gpkg".format(filename)

        self.mode = mode
        if mode not in ("r", "w", "r+"):
            raise ValueError("Mode must be r, w, or r+")

        if os.path.exists(filename):
            if mode == "w":
                os.remove(filename)
        elif "r" in mode:
            raise IOError("geopackage not found: {0}".format(filename))

        connect_mode = "ro" if mode == "r" else "rwc"
        self._db = sqlite3.connect(
            "file:{0}?mode={1}".format(filename, connect_mode),
            uri=True,
            isolation_level=None,
        )

        self._cursor = self._db.cursor()

        if mode != "r":
            self._cursor.execute("PRAGMA journal_mode=WAL")
            self._cursor.execute("PRAGMA locking_mode=EXCLUSIVE")
            self._cursor.execute("PRAGMA synchronous=OFF")
            self._cursor.execute("PRAGMA foreign_keys = 1")

            # Set version information
            self._cursor.execute("PRAGMA application_id = {}".format(APPLICATION_ID))
            self._cursor.execute("PRAGMA user_version={}".format(USER_VERSION))

            # initialize tables if needed
            schema = open(os.path.join(os.path.dirname(__file__), "schema.sql")).read()
            self._cursor.executescript(schema)
            self._db.commit()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def add_layer(self, df, name, crs=None, description=""):
        if self.mode == "r":
            raise IOError("geopackage is not open for writing data")

        df = df.copy()

        geom = df.geometry.values

        # Simplification 1: exclude empty geometries from here so we have a constant header
        is_empty = pg.is_empty(geom)
        if is_empty.max():
            raise ValueError(
                "Geometry data contain empty geometries; these are not supported at this time.  Drop empty geometries."
            )

        # Simplification 2: only allow 1 type of geom data for dataset: XY or XYZ
        has_z = pg.has_z(geom)
        if has_z.max() != has_z.min():
            raise ValueError(
                "Geometry data have mixed XY and XYZ data; these are not supported at this time.  Use one representation."
            )
        has_z = has_z.max()

        # Only one geometry type per layer
        geom_types = np.unique(pg.get_type_id(geom))
        if geom_types.size > 1:
            raise ValueError("Only one type of geometry is allowed per layer")
        geom_type = pg.GeometryType(geom_types[0]).name

        is_point = geom_type in ("POINT", "MULTIPOINT")

        # FIXME
        srid = 4326  # does this indicate no srid?

        bounds = pg.bounds(geom).astype("float64")
        pivot = bounds.T
        xmin, ymin = pivot[:2].min(axis=1)
        xmax, ymax = pivot[2:].max(axis=1)

        ### Write to SRID table
        # TODO: if defined and not 4326
        # self._cursor.execute(
        #     """
        #     INSERT OR REPLACE INTO gpkg_spatial_ref_sys
        #     (srs_name, srs_id, organization, organization_coordsys_id, definition)
        #     values
        #     ()
        # """,
        #     (),
        # )

        ### Write to gpkg_contents table
        # NOTE: "features" is hard-coded for feature data
        self._cursor.execute(
            """
        INSERT OR REPLACE INTO gpkg_contents
        (table_name, data_type, identifier, description, min_x, min_y, max_x, max_y, srs_id)
        values
        (?, "features", ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                name,
                name,
                description,
                float(xmin),
                float(ymin),
                float(xmax),
                float(ymax),
                srid,
            ),
        )

        ### Write to gpkg_geometry_columns table
        # NOTE: no support for M geometries
        self._cursor.execute(
            """
        INSERT OR REPLACE INTO gpkg_geometry_columns
        (table_name, column_name, geometry_type_name, srs_id, z, m)
        values
        (?, "geometry", ?, ?, ?, 0)
        """,
            (name, geom_type, srid, int(has_z)),
        )

        self._db.commit()

        header_prefix = GP_HEADER_NOBOUNDS if is_point else GP_HEADER_BOUNDS

        # srid: 4 bytes in system endiness
        # WARNING: numpy lops off zero-padded bytes at the end when
        # appending to wkb
        header_srid = (srid).to_bytes(4, "little", signed=False)

        # NOTE: Bounds are always in 2D coordinates from pygeos

        if is_point:
            header_bounds = b""
        else:
            # Use little byte order to match rest of header
            header_bounds = np.apply_along_axis(
                np.ndarray.tobytes, arr=bounds.newbyteorder("L"), axis=1
            )

        # pack WKB data with required header information for geopackage
        # FIXME: numpy removes zero padded bytes when we join bytestrings - UGH!
        # gpkg_binary = (GP_HEADER + header_srid) + pg.to_wkb(geom)
        header = np.array(bytearray(header_prefix + header_srid + header_bounds))

        # This is a total hack to keep numpy from trimming zero padded bytes from header_srid
        def raw_encode(w):
            return np.concatenate((header, np.fromstring(w, dtype="uint8"))).tostring()

        encode = np.vectorize(raw_encode, otypes=["O"])

        df["geometry"] = encode(pg.to_wkb(geom))
        df.to_sql(name=name, con=self._db)

    def close(self):
        """
        Close the mbtiles file.
        """

        self._cursor.close()
        self._db.close()
