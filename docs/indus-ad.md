# Integrated INDUS-AD workflow

Copy `examples/indus_ad_v21_config.json` and `examples/annotations.jsonl` to your
working directory. Review the recording/split selection, cameras, scene rules,
quotas, and output paths before running `dataset-devkit build --config CONFIG`.

Schema `2.1` selects `source.type: "indus_ad_hf"` and
`contract: "indus_ad_integrated_v1"`. The [example configuration](../examples/indus_ad_v21_config.json)
pins the source revision. Six untilted cameras are selected by default;
`cam_front_tilted` is optional.

The current example pins `ee0e1754964f6af000625fb42d854565b39fec36`, including
the producer's `calibrated_extrinsics` overlay. Its sensor policy is explicit:
`gnss_channel: "gnss"`, `gnss_time_basis: "time_offset_ns"`,
`calibrated_ego_frame: "front_camera_x_forward_y_left_z_up"`, and
`intrinsic_image_transform: "resize"`. The publisher selected the live `gnss`
stream and its embedded recording-relative time on 23 October 2026, confirmed a
pure 1920x1080-to-1280x720 resize without cropping, and confirmed the front-camera
and GNSS pose origin coincide. Pose Euler angles retain the devkit's documented
right-handed active XYZ convention; this is not an independent sensor survey.

The corrected camera matrices map optical coordinates to a left-handed
front-reference frame. The adapter explicitly swaps its X/Y basis into the
right-handed export ego frame (X forward, Y left, Z up), converts millimetre
translations to metres, then forms a proper rotation. It verifies the model ID,
camera identity, units, declared axes, inverse matrices, and static per-camera
calibration before deduplication. It never falls back to the unverified legacy
`fields_json.extrinsic` vectors. Intrinsics are scaled only under the explicit
pure-resize policy; distortion coefficients remain unchanged.

Published GNSS tables require an explicit channel and time basis. Streams are
filtered before interpolation and never merged. Sensor uncertainty/quality fields
are retained. Invalid coordinate-bearing samples remain invalid interpolation
barriers. Unknown source versions, duplicate selected timestamps, missing selected
times, and absolute-time fields are rejected.

The adapter verifies agreement among metadata, video Viewer, video integrity, and
privacy-release controls. Acquired video bytes must match both the pinned tree
identity and the integrity-manifest SHA-256, including when reused from cache.
These status and integrity checks do not independently measure residual privacy
risk. Original MCAP remains `restricted_raw` and has no anonymization claim.

Camera labels join selected sample data by exact recording ID, camera channel, and
recording-relative nanoseconds. Dense references also retain frame index and frame
ID. GNSS windows use recording-relative bounds. Trajectories and motion features
use precise per-recording local ENU.

See [annotation coverage](annotation-coverage.md) for measured per-camera availability,
a real source-label example, and export join auditing. Regular frame sampling does
not guarantee that any sparse source label survives the exact join.

Model outputs are machine-generated weak pseudo-labels. Human scene labels remain
in `mz_extensions/annotations.json`; official `sample_annotation.json` is empty.
The integrated export adds:

```text
mz_extensions/indus_ad/contract.json
mz_extensions/indus_ad/camera_annotations.parquet
mz_extensions/indus_ad/gnss_annotations.parquet
mz_extensions/indus_ad/dense_assets.parquet
```

Parquet has fixed schemas and deterministic row ordering. The contract binds the
source revision, annotation schema digest, selected layers, counts, and join audit.
Final publication includes these files in the content manifest.

The read-only SDK returns immutable annotation records:

```python
from dataset_devkit.dataset import Dataset

dataset = Dataset("DATASET")
rows = dataset.camera_annotations(camera_name="cam_front")
if rows:
    camera = dataset.camera_annotation(rows[0].frame_id)
    semantic = dataset.dense_asset(rows[0].frame_id, "semantic")
contract = dataset.indus_ad_contract()
```

Singular queries raise `DatasetFormatError` for missing or ambiguous identities.
`dense_assets.semantic` and `dense_assets.depth` default to `none`; enabling
`selected_frames` verifies the requested archive members only after final scene
selection and requires `camera_scalar` in `annotation_layers`. Invalid combinations
are rejected during configuration validation. Dense export rows describe source
identities and materialization state. Scalar image-quality measurements, including
dark and overexposed fractions, are retained when semantic fractions are disabled.

Run the control-only compatibility gate with:

```bash
python tools/check_indus_ad_contract.py \
  --repo-id gagandeepreehal/indus-ad \
  --revision ee0e1754964f6af000625fb42d854565b39fec36
```

The gate rejects video, archive, and per-recording sensor-table downloads.

Optional GNSS scenario labels use `annotation_layers: [..., "gnss_scenarios"]`
and `gnss_annotation_source` together. The companion declares its own `repo_id`,
immutable `revision`, `contract: "indus_ad_gnss_annotations_v1"`, and
`expected_source_revision` equal to the integrated dataset revision. Its Parquet
files below `data/` must follow the exact companion schema. The adapter verifies
their source revision, recording ownership, relative bounds, and unique window
identities against the selected sensor recording. A production companion release
is not configured in the example.
