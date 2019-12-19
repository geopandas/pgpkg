import os
import sqlite3
import pygeos as pg


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

        # TODO: insert into srid table and reference here, last value

        g = df.geometry
        bounds = pg.bounds(df.geometry)
        pivot = bounds.T
        xmin, ymin = pivot[:2].min(axis=1)
        xmax, ymax = pivot[2:].max(axis=1)

        self._cursor.execute(
            """
        INSERT OR REPLACE INTO gpkg_contents
        (table_name, data_type, identifier, description, min_x, min_y, max_x, max_y)
        values
        (?, "features", ?, ?, ?, ?, ?, ?)
        """,
            (name, name, description, xmin, ymin, xmax, ymax),
        )
        self._db.commit()

        # 1. convert data to WKB
        # 2. generate bounds
        # 3. generate the binary hearder
        # 4. splice header onto WKB
        # 5. use pandas to write the dataframe to the database

    def close(self):
        """
        Close the mbtiles file.
        """

        self._cursor.close()
        self._db.close()
