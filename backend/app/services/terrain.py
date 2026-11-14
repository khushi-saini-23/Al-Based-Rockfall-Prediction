"""Analyze an uploaded ESRI ASCII elevation grid without assuming a real mine."""

from __future__ import annotations

import math


class TerrainError(ValueError):
    pass


def analyze_ascii_grid(content: bytes) -> dict:
    try:
        lines = content.decode("utf-8-sig").splitlines()
    except UnicodeDecodeError as exc:
        raise TerrainError("DEM must be a UTF-8 ESRI ASCII grid") from exc
    header = {}
    index = 0
    while index < len(lines) and len(header) < 6:
        parts = lines[index].strip().split()
        if len(parts) != 2:
            raise TerrainError("DEM header must contain six key/value lines")
        header[parts[0].lower()] = parts[1]
        index += 1
    try:
        cols = int(header["ncols"])
        rows = int(header["nrows"])
        cellsize = float(header["cellsize"])
        nodata = float(header.get("nodata_value", "-9999"))
    except (KeyError, ValueError) as exc:
        raise TerrainError("Invalid DEM dimensions, cellsize or NODATA_value") from exc
    if not 3 <= cols <= 2000 or not 3 <= rows <= 2000 or cols * rows > 2_000_000 or not math.isfinite(cellsize) or cellsize <= 0:
        raise TerrainError("DEM must be at least 3×3 and at most 2 million cells, with positive cellsize")
    if not ({"xllcorner", "yllcorner"} <= header.keys() or {"xllcenter", "yllcenter"} <= header.keys()):
        raise TerrainError("DEM header needs xll/yll corner or center")
    grid = []
    for line in lines[index:]:
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != cols:
            raise TerrainError("DEM row has the wrong number of cells")
        try:
            values = [float(part) for part in parts]
        except ValueError as exc:
            raise TerrainError("DEM contains a nonnumeric elevation") from exc
        if any(not math.isfinite(v) for v in values):
            raise TerrainError("DEM contains a non-finite elevation")
        grid.append(values)
    if len(grid) != rows:
        raise TerrainError("DEM row count does not match nrows")
    elevations = [value for row in grid for value in row if value != nodata]
    if not elevations:
        raise TerrainError("DEM contains no valid elevation cells")
    slopes = []
    aspects = []
    roughness = []
    for y in range(1, rows - 1):
        for x in range(1, cols - 1):
            window = [grid[y + dy][x + dx] for dy in (-1, 0, 1) for dx in (-1, 0, 1)]
            if nodata in window:
                continue
            a, b, c, d, e, f, g, h, i = window
            dzdx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8 * cellsize)
            dzdy = ((g + 2 * h + i) - (a + 2 * b + c)) / (8 * cellsize)
            slope = math.degrees(math.atan(math.hypot(dzdx, dzdy)))
            slopes.append(slope)
            if slope > 0:
                aspects.append((math.degrees(math.atan2(-dzdx, dzdy)) + 360) % 360)
            roughness.append(max(window) - min(window))
    if not slopes:
        raise TerrainError("DEM has no complete 3×3 neighborhood for terrain analysis")
    return {"format": "esri_ascii_grid", "ncols": cols, "nrows": rows, "cellsize": cellsize,
            "valid_elevation_cells": len(elevations), "analyzed_cells": len(slopes),
            "elevation_min": min(elevations), "elevation_max": max(elevations),
            "elevation_mean": round(sum(elevations) / len(elevations), 3),
            "slope_mean_deg": round(sum(slopes) / len(slopes), 3),
            "slope_max_deg": round(max(slopes), 3),
            "roughness_mean_elevation_range": round(sum(roughness) / len(roughness), 3),
            "aspect_mean_deg": round((math.degrees(math.atan2(
                sum(math.sin(math.radians(v)) for v in aspects),
                sum(math.cos(math.radians(v)) for v in aspects))) + 360) % 360, 3) if aspects else None,
            "georeferenced_to_mine": False,
            "limitations": "Uploaded grid only; no mine survey, coordinate reference system or field validation."}
