# Annotation coverage and exact joins

The control-file audit at dataset revision
`ed3f724e75527b5c888c1ad52787d5e82949328e` found 34,306 distinct annotated
frames across 3,169 of 9,927 video streams. The other 6,758 streams have no
sampled camera annotations. Video availability and label availability are separate.

| Camera | Video streams | Streams with labels | Label rows |
| --- | ---: | ---: | ---: |
| Front | 1,469 | 1,469 | 31,434 |
| Front left | 1,469 | 295 | 497 |
| Front right | 1,469 | 295 | 497 |
| Front tilted | 1,113 | 225 | 387 |
| Rear | 1,469 | 295 | 497 |
| Rear left | 1,469 | 295 | 497 |
| Rear right | 1,469 | 295 | 497 |

The audit found no duplicate frame IDs, camera/offset keys or camera/frame-index
keys, and no annotations belonging to absent video streams. Dense indexes contain
34,306 semantic and 34,306 depth references whose frame identities are checked
against the annotations. This verifies references, not archive payload bytes or
all source camera-frame tables. These are sparse machine-generated labels, not
human ground truth or labels for every video frame.

## Reproduce the source coverage audit

After installing the devkit and authenticating with an approved Hugging Face account:

```bash
python tools/audit_indus_ad_coverage.py \
  --repo-id gagandeepreehal/indus-ad \
  --revision 592780554157eb2b38eec1bbba9bb498da5878bb \
  --cache-dir var/coverage-cache \
  --output-dir var/coverage-report
```

The output directory must be absent. The command verifies controls and writes
`annotation-coverage.csv` (one row per available recording-camera stream) and
`annotation-coverage.json` (summary, checks and input hashes). It does not acquire
videos, recording-level sensor tables, or dense archives.

## Read a real source label

This example reads the sampled-label table directly, independently of export
sampling. It requires accepted gated access and uses one immutable revision:

```python
import pyarrow.parquet as pq
from huggingface_hub import hf_hub_download

path = hf_hub_download(
    repo_id="gagandeepreehal/indus-ad",
    repo_type="dataset",
    revision="592780554157eb2b38eec1bbba9bb498da5878bb",
    filename="data/viewer/camera-annotations/part-00000.parquet",
)
rows = pq.ParquetFile(path).read().to_pylist()
row = next(item for item in rows if item["camera_name"] == "cam_front")
print({key: row[key] for key in (
    "recording_id", "camera_name", "frame_id", "frame_index",
    "recording_offset_ns", "weather_label", "depth_p50",
)})
```

## Coverage after building a subset

The devkit joins labels to **actual selected camera frames** using exact recording,
camera and recording-relative timestamp identity. A 2 FPS grid does not guarantee
retention of the source's sparse labeled frames. Labels are not assigned to a
nearby frame or interpolated. Empty label results can therefore be correct even
when the source recording has annotations.

```python
from dataset_devkit import Dataset

dataset = Dataset("DATASET")
contract = dataset.indus_ad_contract()
print(contract["join_audit"])
labels = dataset.camera_annotations(camera_name="cam_front")
print("Joined front-camera labels:", len(labels))
if labels:
    label = labels[0]
    print(label.frame_id, label.annotation.weather)
    print(dataset.dense_asset(label.frame_id, "semantic"))
else:
    print("No front-camera labels matched the selected frames; inspect join_audit.")
```

The contract records available/joined camera labels and dense references for each
selected recording. Inspect those counts before using an export as supervision.
Dense assets default to `none`; their export rows retain references, while
`selected_frames` acquires and validates the relevant archives before export.
Selecting one member can require downloading its entire archive. Keep that opt-in
separate from the bounded camera-video quickstart.

## Current integrated timing and trimming policy

Camera timing defaults to `rec_time_offset_ns`; main `gnss` uses `time_offset_ns`. Untimed quality-flagged GNSS messages define excluded portions, with leading portions trimmed from exports rather than rejecting an otherwise usable recording. Original source and annotation identities remain unchanged. See [exact fields, gap handling and verification limits](timing-and-trimming.md). Historical measurements above retain their original configuration and do not establish this newer policy.

Current examples use consolidated revision `592780554157eb2b38eec1bbba9bb498da5878bb`. The earlier audit revision remains a historical provenance identifier; the source data is preserved in the consolidated tree.
