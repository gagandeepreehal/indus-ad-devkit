# Production validation

Five real six-camera builds passed using recorded-camera `rec_time_offset_ns` and main `gnss` sensor `time_offset_ns`. Every exported image was decoded and checked, every sample was loaded with the standalone SDK, and every dataset was loaded with the official nuScenes loader. CLI validation and inspection passed.

| Recording | Samples | Images | Build seconds |
| --- | ---: | ---: | ---: | ---: |
| `17-57-22.521-da6bd6dd83015b28732796cedaf0b8b6` | 21 | 126 | 72.3 |
| `12-18-59.400-29e39d129f8745b535957b42fb1cc041` | 67 | 402 | 84.8 |
| `15-34-48.486-1fd4556ed9ca552d2e0e7e49b608c59c` | 51 | 306 | 70.5 |
| `16-44-58.320-3a5975a7c70919f124f797f49ddd53a1` | 41 | 246 | 59.1 |
| `17-58-38.892-1cafd700d18c4a09a1f9db053c7933c1` | 48 | 288 | 65.2 |

Source revision: `a1f1d72b73984ef129ac8b3d882f9074bc587205`. Installed candidate wheel SHA256: `d73b5d43141f01006e4a6d922f01e2dc4a3d084cf958a6aac9bdcdfa4cda6eaf`.

These timings use already cached source artifacts and include any acquisition or control checks still required. They are not cold-download benchmarks. Source downloads stay on the attached disk; temporary image cache and outputs use a native filesystem through the existing runtime cache hook. Access was publisher-authenticated; non-owner gated access was not tested.

Scope: macOS, Python 3.12, six untilted cameras and unchanged quickstart quality thresholds. The builds cover nonzero GNSS origin, signed producer batch offsets, both variants together, the sensor acceptance recording and the documented quickstart. They do not establish full-corpus video acceptance, Linux production decoding, independent physical calibration or privacy accuracy.

The [machine-readable receipt](launch-validation.json) records exact configurations, installed wheel, source revision, loader/CLI checks, image counts and runtime boundary. Earlier receipts under the previous policy are retained in local launch evidence.

The full new-policy metadata audit remains in progress; see [source compatibility](source-compatibility.md). If release history is consolidated, source payload identities must be verified unchanged and current download pins updated to a retained release revision.
