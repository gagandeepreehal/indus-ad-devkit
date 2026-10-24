# Source metadata compatibility

The corpus-wide audit checked all 1,469 recordings at source revision
`a1f1d72b73984ef129ac8b3d882f9074bc587205`. The consolidated revision `592780554157eb2b38eec1bbba9bb498da5878bb` preserves those
sensor-table bytes. Every downloaded table was checked against its pinned
Git blob or LFS SHA-256 identity. Camera/calibration validation used the stock
parser invariants with bounded row IO; GNSS used the stock strict reader.

**1469 recordings passed** the explicit six-camera metadata
policy; **0 failed** at least one check. Download
errors: **0**. See the [per-recording CSV](source-compatibility.csv),
[summary](source-compatibility-summary.json), and [dataset report](https://huggingface.co/datasets/gagandeepreehal/indus-ad/blob/592780554157eb2b38eec1bbba9bb498da5878bb/collateral/DEVKIT_COMPATIBILITY.md).

This checks six untilted cameras, the published calibration overlay, pure image
resize, main `gnss` messages and sensor `time_offset_ns`, with camera `rec_time_offset_ns`
used for synchronization, pose queries and export times. Consistent nonzero
local-ENU origins are preserved. Untimed quality-flagged GNSS messages define
excluded portions; edges are trimmed and internal gaps are not interpolated
across. Raw source files and exact annotation identities are unchanged. Tilted-camera
tables were downloaded and byte-verified but their frame parsing is outside
this six-camera count. Missing diagnostics on quality-flagged messages remain null; malformed valid
messages and other structural errors remain failures. See [timing and
trimming](timing-and-trimming.md) for exact fields and verified gap counts.

Metadata acceptance does not guarantee a selected scene will pass validity,
quality thresholds or scenario quotas. It does not decode every video or prove
physical calibration or privacy performance. [Five representative production
builds](launch-validation.md) provide separate bounded acceptance evidence.

## Storage

The launch audit retained new metadata downloads on an attached disk and used
one parser under a 6 GB task budget, with a 5 GB RSS stop threshold. The final
audit retains all verified camera-frame, calibration and GNSS input tables
on the attached disk. This is the audited table subset, not a full dataset
mirror. Full input hashes are preserved in the launch evidence bundle.

The stock image/extraction cache requires native filesystem operations. A tiny
offline check rejected the attached non-native disk with `Operation not supported`;
keeping source downloads there and only the image cache on the native filesystem
passed. Production builds use that existing `BuildRuntime` cache-location hook,
with stock acquisition, decoding, quality rules and official loader checks.
