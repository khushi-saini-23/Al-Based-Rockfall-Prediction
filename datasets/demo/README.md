# Supplied synthetic CSV demonstration data

These five CSV files are byte-for-byte copies of the files supplied in
`GeoGuards_Separate_CSV_Datasets`. They are synthetic software-test data, **not**
real mine measurements or a validated geotechnical simulation. All sensor rows
carry `data_provenance=synthetic_demo_only`. The event file has three positive
rows with `event_label_source=synthetic_rule_based_demo_label`; no verified
negative observation periods are provided. Unlisted keys are **unknown**, not
confirmed non-events. No ML accuracy claim may be made from these labels.

| File | Rows | Numeric columns (CSV values parsed as floats) |
| --- | ---: | --- |
| `01_environmental_data.csv` | 5,000 | `rainfall_mm`, `temperature_c`, `humidity_percent`, `wind_speed_m_s` |
| `02_vibration_sensor_data.csv` | 5,000 | `vibration_mm_s` |
| `03_displacement_strain_data.csv` | 5,000 | `displacement_mm_h`, `strain_microstrain` |
| `04_geotechnical_data.csv` | 5,000 | `slope_angle_deg`, `elevation_m`, `aspect_deg`, `surface_roughness_index`, `terrain_ruggedness_index`, `pore_pressure_kpa`, `soil_moisture_percent`, `factor_of_safety_proxy` |
| `05_rockfall_events.csv` | 3 | `rockfall_event` (all `1`) |

Every file also has `timestamp` (UTC ISO 8601 text), `location_id` (text), and
`data_provenance` (text). The event file also has `event_label_source` (text).
The column suffixes supply the known units. Both terrain indices and the
`factor_of_safety_proxy` are unitless, illustrative values; the latter is **not**
a calibrated engineering factor of safety. The source does not define whether
`rainfall_mm` is a one-hour accumulation, so the importer treats it as one-hour
amount solely for provisional dashboard testing. `displacement_mm_h` is a rate,
while the legacy UI labels displacement as millimetres; imported CSV zones are
shown as mm/h. The provisional rule thresholds were not calibrated to these
CSV units.

All four sensor files contain exactly 500 hourly timestamps for each of
`LOC_01` through `LOC_10`, from `2023-01-01T00:00:00+00:00` through
`2023-01-21T19:00:00+00:00`. Their 5,000 `(timestamp, location_id)` keys match.
The three event keys occur within that grid, at `LOC_03`, `LOC_07`, and
`LOC_09`. Inspection found no blank fields, malformed numeric values, or
duplicate keys. The importer validates these conditions and reports missing
files; it does not replace them. It reads each file separately, aligns a bounded
recent window in memory by both keys, and does not write a combined CSV.
Event rows are never passed to the risk service or stored as sensor readings.

The import endpoint is `POST /api/demo/import?limit_per_location=30`, with a
range of 1–100 per location. It writes the selected historical synthetic
readings and provisional rule assessments into the existing store. Repeating
the same import skips existing readings. If MongoDB is not configured, this
history is held only in process memory. The `GET /api/demo/datasets` endpoint
returns validation and provenance information. The sample is historical; it
does not become a live sensor stream or generate current alerts.
`GET /api/demo/events` returns only the three supplied positive event rows for
display and inspection; it creates no negative labels or risk assessments.

Keep future measured datasets in `datasets/real/`, with their own source,
license, units, instrumentation, event-verification and observation-coverage
documentation. Do not place real data in this demo folder.
