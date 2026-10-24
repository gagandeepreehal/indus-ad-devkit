# Verified bounded first build

## Current release

Version 0.1.2 includes the revised example, pinned to `592780554157eb2b38eec1bbba9bb498da5878bb`. See [current production validation](launch-validation.md) and [source compatibility](source-compatibility.md). The measurements below preserve the original v0.1.1 run and its historical source identifier; they are not new download pins.

## Historical bounded build measurement

The historical measured example selected recording
`17-58-38.892-1cafd700d18c4a09a1f9db053c7933c1` from
`gagandeepreehal/indus-ad` at immutable dataset revision
`ee0e1754964f6af000625fb42d854565b39fec36`.

It passed a real six-camera build using the published v0.1.1 wheel in a clean
Python 3.12 dependency environment on macOS arm64 on 24 October 2026. The revised
configuration, not the original configuration bundled with the tag's source,
selects this recording and sets one catch-all scenario rule with quota 1.
An empty scenario-rules list intentionally selects no scenes.

## Selection and transfer size

The original byte-size-only choice failed a production build on unavailable GNSS
poses. Candidates were subsequently ranked by six-camera bytes, screened using
the published quality summary and actual pinned camera/GNSS tables, and then
verified by a real build. This is a verified small example, not a claim that every
recording follows the same supported timing/origin layout.

| Artifact class | Unique bytes |
| --- | ---: |
| Six privacy-transformed videos | 190,924,636 |
| Six camera-frame tables, calibration and GNSS | 499,082 |
| 74 shared controls, including annotation/dense indexes | 17,240,772 |
| Total: 88 unique artifacts | 208,664,490 |

This is about 209 MB / 199 MiB before network overhead, dependency installation,
extracted JPEGs, staging and final outputs. Dense indexes are controls; dense TAR
payloads remain disabled.

## Measured result

- 1 scene, 48 samples and 288 camera images.
- 2 joined camera pseudo-label rows and 4 dense references; GNSS scenario labels
  are not configured, and dense payloads were not downloaded.
- Build, CLI validation, inspection and mandatory official nuScenes loading passed.
- Successful build time: 59.7 seconds **with selected source artifacts cached**.
  It excludes installation, cold downloads and the separate validate/inspect calls.
- Sampled working-file peak: 382,150,413 bytes, measured by summing file lengths
  every two seconds. This excludes the Python environment, is not allocated disk
  usage and cannot establish an instantaneous maximum. Keep a 2 GiB working budget
  plus environment space; other machines and larger selections vary.
- Publisher-authenticated access was used. An approved non-owner account and a
  Linux production-video run were not tested in this session.

[Machine-readable acceptance receipt](quickstart-acceptance.json).
See [annotation coverage](annotation-coverage.md) for source availability and exact
join behavior. The 2 FPS example retains two of this recording's three front-camera
labels; missing labels in the other selected cameras are expected.

The example uses `gnss` and embedded `time_offset_ns`, explicit calibrated ego
axes and the confirmed pure image resize. See
[published sensor acceptance](published-sensor-acceptance.md) for the sensor policy.
A successful format/build check does not measure residual privacy risk or physical
calibration accuracy.

To expand deliberately, select explicit recording IDs and set scenario rules and
quotas for the desired output. An empty recording list selects every recording
matching `source.splits`; technical `train` is a storage label, not an evaluation
benchmark. Unsupported source timing/origin layouts fail closed.

Release [v0.1.1](https://github.com/gagandeepreehal/indus-ad-devkit/releases/tag/v0.1.1)
was published on 24 October 2026 as an alpha prerelease. This newer example uses
that wheel but does not alter its immutable release artifacts or tag.

## Python support and mandatory format check

Versions 0.1.1 and 0.1.2 support Python 3.12 (`>=3.12,<3.13`). The official nuScenes
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

## Current integrated timing and trimming policy

Camera timing defaults to `rec_time_offset_ns`; main `gnss` uses `time_offset_ns`. Untimed quality-flagged GNSS messages define excluded portions, with leading portions trimmed from exports rather than rejecting an otherwise usable recording. Original source and annotation identities remain unchanged. See [exact fields, gap handling and verification limits](timing-and-trimming.md). Historical measurements above retain their original configuration and do not establish this newer policy.
