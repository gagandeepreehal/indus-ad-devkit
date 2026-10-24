# INDUS AD DEVKIT

[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
![Status: Alpha](https://img.shields.io/badge/status-alpha-orange)
![Platform: POSIX](https://img.shields.io/badge/platform-POSIX-lightgrey)
[![License: PolyForm Noncommercial 1.0.0](https://img.shields.io/badge/license-PolyForm%20Noncommercial%201.0.0-blue)](LICENSE.md)

Build reproducible, nuScenes-compatible subsets from INDUS-AD driving datasets.
The devkit selects camera frames and driving scenes, interpolates GNSS poses,
applies scenario quotas, and exports validated train/test splits with provenance.

Integrated INDUS-AD support includes camera, semantic, depth, weather, and optional
GNSS weak pseudo-labels. These model outputs remain separate from human labels.

![Publisher-provided example of six camera perspectives in Bengaluru traffic](docs/assets/indus-ad-surround-view.png)

*Illustrative surround view from the INDUS-AD dataset card; not a calibrated camera-layout diagram
or independent evidence of anonymization performance. [Image source and license](docs/assets/SOURCES.md).*

> Compatibility refers to the nuScenes file structure and supported loader behavior.
> This project is independent of Motional and does not reproduce the nuScenes
> sensor suite, annotations, maps, or benchmarks.

## Source dataset

![Seven-camera and Ouster OS1-128 LiDAR configuration](docs/assets/car_seven_cameras_lidar_corrected.png)

Seven-camera and Ouster OS1-128 LiDAR configuration. Camera positions and orientations are plotted from supplied parameters; vehicle silhouette is illustrative, and LiDAR positioning is estimated and unverified.

[INDUS-AD on Hugging Face](https://huggingface.co/datasets/gagandeepreehal/indus-ad)
contains multi-camera driving recordings from Bengaluru, India, with camera timing,
calibration, transformed GNSS/pose tables, and sampled semantic, depth, weather, and
image-quality pseudo-labels joined by `recording_id`.

| Dataset-card snapshot | Value |
| --- | --- |
| Recordings | 1,469 |
| Camera videos | 9,927 MP4s |
| Recording timeline (longest camera per recording) | 85.31 hours |
| Summed camera-view duration | 588.57 hours across cameras, not distinct driving hours |
| Camera positions | Six surround cameras; tilted-front video in 1,113 recordings |
| Sampled camera annotation rows | 34,306; not labels for every video frame |

Figures come from the [dataset card snapshot](https://huggingface.co/datasets/gagandeepreehal/indus-ad/blob/8983a2b9852d7109b97c5c29dd0482fa9e7e92bb/README.md),
checked 16 October 2026. Its `train` split is a storage/API label, not an authored benchmark split.
The devkit creates its own derived train/test split. Dataset access requires manual approval;
the publisher approved the privacy/access decision on 23 October 2026. Final dataset
launch approval remains pending; see the [current dataset privacy policy](https://huggingface.co/datasets/gagandeepreehal/indus-ad/blob/main/collateral/DATASET_PRIVACY_AND_TAKEDOWN.md).

![INDUS-AD video, GNSS and motion, pseudo-labels, and dense semantic/depth layers joined by recording ID](docs/assets/indus-ad-dataset-layers.png)

*Publisher-provided dataset-layer diagram. [Image source and license](docs/assets/SOURCES.md).*

## Setup

Requires Python 3.12 (`>=3.12,<3.13`) and Linux or macOS.
The mandatory official nuScenes loader check currently depends on NumPy <2;
Python 3.13/3.14 are unsupported until that dependency chain is compatible.

```bash
git clone https://github.com/gagandeepreehal/indus-ad-devkit.git
cd indus-ad-devkit
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

For gated or private datasets, obtain access and authenticate with `hf auth login`.
Keep credentials out of configuration files.

## Choose a source

All sources require an exact repository ID and a full 40-character commit SHA.

| Source | Schema | Example |
| --- | --- | --- |
| Integrated INDUS-AD with annotations | `2.1`, `indus_ad_hf` | [indus_ad_v21_config.json](examples/indus_ad_v21_config.json) |
| Older decoded V2 layout | `2.0`, `decoded_hf` | [decoded_v2_config.json](examples/decoded_v2_config.json) |
| Original MCAP | `1.0`, `mcap_hf` | [dataset_config.json](examples/dataset_config.json) |

INDUS-AD and decoded V2 are classified as `privacy_transformed`; original MCAP is
restricted raw (`restricted_raw`) and carries no anonymization claim. Manifest verification
checks published evidence and integrity; it does not independently rerun the anonymizer.

## Build an INDUS-AD subset

```bash
cp examples/indus_ad_v21_config.json dataset_config.json
cp examples/indus_ad_annotations.jsonl annotations.jsonl
```

The example pins dataset revision `ee0e1754964f6af000625fb42d854565b39fec36`
and selects recording `17-58-38.892-1cafd700d18c4a09a1f9db053c7933c1`.
It selects exactly one eligible scene through an explicit `quickstart` quota of 1;
an empty scenario-rules list selects no scenes. Dense archives are disabled.

- **Download:** 208,664,490 unique artifact bytes (about 209 MB / 199 MiB):
  190,924,636 video bytes, 499,082 recording-table bytes and 17,240,772 shared controls.
  Network overhead and package installation are additional.
- **Disk:** allow a 2 GiB working budget plus the Python environment. The successful
  cached run sampled a 382,150,413-byte peak in working-file lengths; this excludes
  the environment and is not a guaranteed instantaneous peak or allocation bound.
- **Runtime:** the successful cached-artifact build took 59.7 seconds on macOS arm64 /
  Python 3.12.14. Cold downloads and installation are additional; other machines vary.
- **Verified output:** 1 scene, 48 samples and 288 camera images, with 2 joined camera
  labels and 4 dense references. Build, validation, inspection and mandatory official
  nuScenes loading passed using the published v0.1.1 wheel. Dense payloads were disabled.
- **Output directory:** `var/indus-ad-datasets/v1.0-trainval` for a configuration copied
  to the repository root. Paths are relative to the configuration file.

See [quickstart provenance and limits](docs/quickstart-release.md).
Review camera and annotation layers, sampling rate, scene rules, quotas, and paths before running:

```bash
dataset-devkit build --config dataset_config.json
```

The human annotation file is optional input content but must exist at its configured
path. The INDUS-AD template is empty and supplies no invented human labels.
The legacy MCAP and decoded V2 examples use placeholder repository IDs and all-zero
revisions; replace both with a source matching the corresponding contract.

The pipeline verifies selected artifacts, samples frames, builds scenes, applies
filters and seeded scenario quotas, and assigns train/test splits. Strict quota
shortfalls fail the build. For transformed sources, trajectories and motion features
use precise recording-local ENU; rounded global coordinates provide context only.

See [measured annotation coverage and exact-join examples](docs/annotation-coverage.md).
A regular sampling grid can retain no labels from a sparsely annotated recording;
inspect the export contract's `join_audit` before using it for supervision.

Six untilted cameras are selected by default; `cam_front_tilted` is optional. Dense
semantic/depth payloads are metadata-only by default. `selected_frames` modes require
`camera_scalar` and verify dense members after scene selection.

## Output and validation

A successful build publishes `paths.output_dir/v1.0-trainval`:

```text
v1.0-trainval/
├── maps/
├── samples/
├── mz_extensions/
└── v1.0-trainval/       # official JSON tables
```

`mz_extensions/` contains source fingerprints, validity, labels, selection/split
audits, and a content manifest. Integrated weak labels are Parquet tables under
`mz_extensions/indus_ad/`. Official object annotation tables remain empty.
Dense payloads stay in the verified cache; exported rows retain source references
and materialization state. Dense acquisition failures block publication.

```bash
dataset-devkit validate --dataroot DATASET --version v1.0-trainval
dataset-devkit inspect --dataroot DATASET --version v1.0-trainval
```

Use the published dataroot as `DATASET`. Outputs are read-only and existing
destinations are never overwritten. Rebuild into a new destination to change content.
Commands emit JSON; configuration errors exit `2`, and operational/validation errors exit `1`.

## Python SDK

```python
from dataset_devkit import Dataset

dataset = Dataset("DATASET")
scene = dataset.table("scene")[0]
sample = dataset.scene_samples(scene["token"])[0]
front = dataset.camera(sample["token"], "CAM_FRONT")
pose = dataset.ego_pose(front["token"])

# Integrated INDUS-AD output
labels = dataset.camera_annotations(camera_name="cam_front")
if labels:
    weather = labels[0].annotation.weather
```

See the [SDK guide](docs/export.md) for annotation lookups, splits, and audit access.

## Documentation

| Guide | Contents |
| --- | --- |
| [Integrated INDUS-AD](docs/indus-ad.md) | Annotation layers, joins, dense references, and companion GNSS |
| [Published sensor acceptance](docs/published-sensor-acceptance.md) | Corrected calibration/GNSS compatibility and verification limits |
| [Configuration](docs/configuration.md) | Sources, paths, sensors, and policies |
| [Extraction](docs/extraction.md) | Camera decoding, timestamps, GNSS, and staging |
| [Validity](docs/validity.md) | Quality rules, quarantine, and partial publication |
| [Scenes](docs/scenes.md) | Automatic, annotation-driven, and hybrid scenes |
| [Selection](docs/selection.md) | Features, filters, quotas, and splitting |
| [Export and SDK](docs/export.md) | Tables, extensions, validation, and publication |

## Limitations

- Camera, calibration, and GNSS inputs are supported; LiDAR ingestion is not.
- Inputs must follow a supported source contract. Arbitrary repositories and symbolic revisions are rejected.
- `v1.0-trainval` is the only publication version. Windows is unsupported.
- Some source-table variants (missing/signed producer batch offsets or nonzero
  local-ENU origin offsets) are outside the current supported contract and are
  rejected. The bounded quickstart is selected by actual sensor-table preflight.
- The corrected calibration and selected GNSS parsers have been checked against one
  production recording's tables. The bounded quickstart has now passed a real-video
  build on macOS; Linux/macOS CI also covers synthetic/offline exports. Other
  recordings and a production GNSS companion release remain unverified.

## Development

```bash
python -m pip install -e '.[dev]'
pytest -q
ruff check src tests
mypy
python -m dataset_devkit.schema
git diff --exit-code schema/dataset_config.schema.json
python -m build --no-isolation
```

For a tiny offline decoded build:

```bash
python tools/decoded_fixture_smoke.py /tmp/dataset-devkit-fixture
```

The fixture destination must be absent; the script prints the published dataroot.

## Citation and license

Cite the source dataset release using its Hugging Face dataset card, and identify
this devkit by repository URL and the release tag or commit used.

The software uses the [PolyForm Noncommercial License 1.0.0](LICENSE.md).
Commercial use requires a separate license. See [NOTICE](NOTICE) for copyright information.
