# Bounded first build and release provenance

The v0.1.1 example selects only recording
`17-53-27.393-d655e06f8e7ee863e68443502137f2fe` from
`gagandeepreehal/indus-ad` at immutable dataset revision
`ee0e1754964f6af000625fb42d854565b39fec36`.

Selection ranked 1,469 published metadata rows by the sum of the six required
camera video sizes, requiring all six paths to be present. The tilted camera
is excluded from this example. This selects the smallest qualifying recording
by video bytes; it does not claim the best source quality or a successful
production build. Raw recordings, production videos and dense archives were
not downloaded during this selection.

| Artifact class | Unique bytes |
| --- | ---: |
| Six privacy-transformed videos | 163,364,366 |
| Six camera-frame tables, calibration and GNSS | 443,633 |
| 74 shared controls, including annotation/dense indexes | 17,240,772 |
| Total | 181,048,771 |

These counts describe unique selected artifacts from pinned Hub metadata.
Caches may avoid transfers; network overhead, dependency installation, extracted
JPEGs, staging and final outputs are additional. Dense indexes are controls;
dense payload archives remain disabled. An initial 2 GiB working budget is a
planning allowance, not a measured peak or guaranteed bound. Runtime and final
sample/scene counts remain unmeasured for this production recording.

The example uses `gnss` and embedded `time_offset_ns`, explicit calibrated ego
axes and the confirmed pure image resize. See
[published sensor acceptance](published-sensor-acceptance.md) for parser and
synthetic end-to-end evidence. Do not substitute synthetic fixture results for
production-video validation or privacy-detector quality evaluation.

To expand the build deliberately, replace `source.recording_ids` with specific
IDs. An empty list selects every recording matching `source.splits`; the current
train split is a storage label, not an authored evaluation benchmark.

Release [v0.1.1](https://github.com/gagandeepreehal/indus-ad-devkit/releases/tag/v0.1.1)
was published on 24 October 2026 as an alpha prerelease. Software publication
does not constitute final dataset launch approval.

## Python support and mandatory format check

Version 0.1.1 supports Python 3.12 (`>=3.12,<3.13`). The official nuScenes
loader smoke check remains mandatory before an export is published. Internal
validation alone is not substituted for that check.

The current [official SDK dependencies](https://github.com/nutonomy/nuscenes-devkit/blob/master/setup/requirements/requirements_base.txt)
require NumPy <2. Wheel-only dependency checks for Python 3.13 and 3.14 cannot
resolve NumPy 1.x; attempting NumPy 2 also conflicts with the official SDK's
requirements. Newer Python support was investigated but is not claimed for
this alpha release. Dependencies are not bypassed and the SDK check is not disabled.

CI runs the complete tests, strict type/lint checks, schema regeneration,
package builds and an installed-wheel offline export on Linux and macOS with
Python 3.12. Local macOS results and remote CI results must be reported separately.
