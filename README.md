# PGPGK

Faster I/O between [`pygeos`](https://github.com/pygeos/pygeos) and [geopackage](https://www.geopackage.org/) file format for use in GIS.

Geopackages are a modern, sqlite-based file format containing geospatial data. These are intended to overcome shortcomings in the shapefile format that is ubiquitous in the geospatial data world.

`pygeos` is a very fast Python wrapper around the GEOS library. It provides very fast geospatial operations on geometries, including checking for intersections between geometries or calculating the geometric intersection between them.

The goal of this library is to allow serializing `pandas` DataFrames containing `pygeos` geometry objects as fast as possible.
This is a shim until `pygeos` is fully integrated into `geopandas`.

## WARNING:

This package may change radically once `pygeos` is used internally within `geopandas`.

We are not focusing on full coverage of all of the different ways of writing data to a geopackage. If that is what you need, use `ogr2ogr` or one of the other Python packages available for geopackages.

## Early results:

According to the benchmarks in our test suite, we are seeing 2-3x speedups compared to writing shapefiles or geopackages in `geopandas`.
