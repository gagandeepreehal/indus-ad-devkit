# Production validation

Five selected real six-camera recordings passed acquisition, extraction,
scene export, standalone SDK loading, official nuScenes loading and image
readback before the new default camera clock was selected. These are historical
results for the previous candidate, not new-policy acceptance evidence.

The same five recordings are being rerun using the recorded-camera default
and main GNSS sensor time. They cover a nonzero GNSS origin, signed producer
batch offsets, both variants together, a separate sensor acceptance recording
and the documented quickstart. Final receipts will report the exact installed
wheel SHA256, configuration, immutable source revision and per-build results.

The new reader has 1,039 passing local tests, including trimming an untimed
GNSS start, blocking interpolation over internal untimed gaps and preserving
exact annotation identity across camera clock selection. See
[timing and trimming](timing-and-trimming.md).

Production checks are macOS and Python 3.12 with publisher-authenticated
access. They are not a whole-corpus video decode, a Linux production build,
a non-owner access test or independent physical calibration/privacy validation.
