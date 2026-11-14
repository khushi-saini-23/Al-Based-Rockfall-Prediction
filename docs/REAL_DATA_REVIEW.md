# Candidate public data sources — suitability review

Reviewed 13 November 2026. These are **candidates**, not data installed in
GeoGuards and not evidence that a mine-site predictor is valid.
The reviewed public sources do not provide an aligned set of open-pit mine
sensor readings, verified rockfall events and verified observation coverage
for non-events. This review is not an exhaustive survey of all repositories.

| Source | What the source describes | Fit for the required target |
| --- | --- | --- |
| [Zenodo: open-pit mine slope failure seismic-noise study](https://zenodo.org/records/15003054) | Velocity-change, seismic-event, weather and surface-deformation data for an open-pit **slope failure** study. | Mine setting and multiple measurements are useful, but a slope-failure event cannot silently be relabeled as rockfall. Inspect raw time/zone references and event definitions before use. |
| [DataverseNO: Stampa rockfall monitoring](https://doi.org/10.18710/GBDO4X) | Monitored rockfall in western Norway; public files include observed activity and tilt measurements. | Genuine rockfall context, but this is **not an open-pit mine**. Observation coverage and sensor/event alignment must be checked. Transfer to mines is unproven. |
| [MRDataset](https://github.com/muranhb/MRDataset) | Annotated mountain rockfall images for object detection, with a non-commercial academic/educational use notice. | Possible vision research input, but mountain scenes differ from open-pit benches; not a time-to-event sensor dataset or mine-site validation. Review license and splits before downloading. |
| [USGS 3DEP](https://www.usgs.gov/3d-elevation-program/about-3dep-products-services) | Public DEM and lidar products for U.S. terrain. | Possible demonstration terrain source. It is not a surveyed DEM of the fictional GeoGuards zones and does not supply rockfall labels. Convert any selected raster to the supported ASCII grid format with provenance and CRS retained. |

## Required acquisition package for prediction research

Place each approved source under `datasets/real/<category>/` without modifying
its original files. Supply a source URL/DOI and license; mine/site identifiers;
sensor and zone coordinates with CRS; timestamps and time zone; units, sampling
frequency and instrumentation; independently verified event timestamps,
locations and definitions; documented monitoring periods in which events would
have been detected; missingness/maintenance logs; and the rights to use the
data. A positive-only event table cannot establish negative examples.

Until these are available, the project cannot make scientific accuracy claims
or train a defensible `VALIDATED_ML` model.
