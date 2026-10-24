# Troubleshooting

## Access denied or gated repository

Request access on the dataset's Hugging Face page and wait for manual review.
There is no fixed turnaround. Sign in locally with `hf auth login` using the
approved account. Do not paste access tokens into issues or configuration files.
Repository visibility and approval to download gated files are separate.

## Python or NumPy installation failures

Use Python 3.12 on Linux or macOS in a fresh virtual environment. Python 3.13
and 3.14 are unsupported. The official nuScenes loader requires NumPy below 2;
do not bypass its dependency requirements or disable the format check.

## No scenes selected

Start from the current release's `examples/indus_ad_v21_config.json` and its
annotation companion. Scenario rules need a positive quota; an empty rules
list does not select scenes. Check selection and validity reports before
changing quality thresholds. A `train` storage label is not a benchmark split.

## Source timing or GNSS parsing fails

The adapter uses recorded-camera time for all integrated recordings and
preserves consistent nonzero
local-ENU origin offsets. Batches before recording zero remain in the raw audit
and are excluded from the export grid. Invalid GNSS fixes remain interpolation
barriers even when they have no attitude. Untimed quality-flagged messages
mark excluded portions instead of rejecting the whole recording. Affected
leading portions are trimmed from the export. Missing timestamps on valid
samples, changing origins or malformed valid fixes still fail validation. A parser
failure does not mean the video is corrupt. Use the documented source revision
and explicit GNSS clock selection. Do not substitute camera clocks, rebase origins,
or invent poses to make an export pass. Include the recording ID, dataset
revision and sanitized error in a bug report.

## Few or no labels after frame selection

Pseudo-labels are sparse and vary by camera. Frame downsampling can omit every
labeled frame in a recording. Inspect `join_audit` and the annotation coverage
report. Missing labels are not negative ground truth. Dense archives are not
downloaded unless explicitly requested.

## Disk space or download failures

Begin with the one-recording example. Keep at least the documented working
budget plus space for the Python environment; larger selections need more.
Reuse a verified cache at its recorded source revision. Do not edit cache
receipts to pretend that a file was fetched from another revision. Retry
transient download failures after checking access and connectivity.

## External drives

The image/extraction cache uses filesystem operations that are not available on
every external-drive format. Keep the default working and image cache paths on
a native filesystem such as APFS on macOS. The launch audit stores metadata
files on an attached disk; production validation separates the source-download
cache from the image cache through the existing `BuildRuntime` hook. This does
not claim that the default CLI cache works on every external-drive format.

## Sharing a reproducible report

Include the devkit release, source revision, date-free recording IDs, Python
and operating-system versions, a minimal config and relevant error. Keep
credentials, precise locations and privacy concerns out of public issues.
