# Published sensor schema compatibility, 23 October 2026

This change targets INDUS-AD revision
`ee0e1754964f6af000625fb42d854565b39fec36`. It does not modify source dataset
payloads, privacy transformations, dataset access, or annotations.

## Resolved source differences

- Read repeated `kind/key/fields_json/calibrated_extrinsics` calibration events,
  asserting one static calibration per recording-camera before deduplication.
- Validate the producer's overlay model, units, axes, matrices, origins, and inverses.
  Do not interpret the legacy `[1,2,3]`/`[4,5,6]` source vectors as calibration.
- Convert the left-handed front-reference basis to the right-handed export ego
  basis, then convert only matrix translations from millimetres to metres.
- Scale focal lengths, principal point, and skew under the explicit pure-resize
  policy; retain dimensionless distortion coefficients.
- Read versioned GNSS messages, explicitly select `gnss`, and use embedded
  `time_offset_ns`. Keep streams separate and preserve uncertainty/quality fields.
- Keep coordinate-bearing invalid GNSS samples as invalid interpolation barriers.

The publisher selected this GNSS channel/time basis, confirmed pure image resizing
without cropping, confirmed the front-camera and GNSS pose origins coincide, and
directed use of the existing devkit/datagen rotation convention. The devkit uses
active right-handed fixed-axis XYZ (`Rz @ Ry @ Rx`) and `(w,x,y,z)` quaternions.
These confirmations are not a survey or an independent calibration-accuracy claim.
The example records the sensor choices explicitly; they enter the extraction
configuration fingerprint and do not silently reuse another policy's cache.

## Production table checks

Only one recording's approved decoded calibration and GNSS tables were read:
`12-18-59.400-29e39d129f8745b535957b42fb1cc041`.

| Artifact | Revision | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| Calibration table with corrected overlay | `ee0e1754964f6af000625fb42d854565b39fec36` | 38,786 | `04221b2edbc2a09dc7a65a79232918ccdf7a336b841dfc5d6609fe944a882303` |
| GNSS table | `406674a320879221cfb3050c252dae7110577ee6`; identical object at the newer revision | 262,034 | `ec14bf8078ad7d2bfbbf3b98014d2033af681363db62f2c1f3d93fc9d2be14b5` |

The corrected reader accepted seven distinct camera calibrations from 2,345
repeated events, parsed 1,700 selected live-GNSS samples from the 2,035-row combined
table, and produced an available pose at a selected sample time. The 335 recorded
GNSS rows were excluded. No production video, raw MCAP, or dense archive was
downloaded. A full production-video build remains unverified.

## Regression verification

The complete suite passed with 1,025 tests. Strict mypy and Ruff passed. The added
synthetic published-layout workflow covers acquisition, image extraction,
resizing, scene selection, export, SDK annotation access, and final validation.
Its overlapping GNSS streams detect accidental stream merging. Direction tests
check forward/rear/right/tilted optical rays and proper rotation handedness;
mutation tests reject inconsistent matrices, inverses, units, camera identities,
unknown versions, duplicate times, missing times, and absolute-time fields.

The historical `indus-ad-acceptance.md` records the earlier implementation's
scope. This note records the newer compatibility fix and its verification limits.

## Current integrated timing and trimming policy

Camera timing defaults to `rec_time_offset_ns`; main `gnss` uses `time_offset_ns`. Untimed quality-flagged GNSS messages define excluded portions, with leading portions trimmed from exports rather than rejecting an otherwise usable recording. Original source and annotation identities remain unchanged. See [exact fields, gap handling and verification limits](timing-and-trimming.md). Historical measurements above retain their original configuration and do not establish this newer policy.
