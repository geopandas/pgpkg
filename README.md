# PGPGK

Faster I/O between [`pygeos`](https://github.com/pygeos/pygeos) and [geopackage](https://www.geopackage.org/) file format for use in GIS.

Geopackages are a modern, sqlite-based file format containing geospatial data. These are intended to overcome shortcomings in the shapefile format that is ubiquitous in the geospatial data world.

`pygeos` is a very fast Python wrapper around the GEOS library. It provides very fast geospatial operations on geometries, including checking for intersections between geometries or calculating the geometric intersection between them.

The goal of this library is to allow serializing `pandas` DataFrames containing `pygeos` geometry objects. (NOTE: this is a shim until `pygeos` is fully integrated into `geopandas`).
