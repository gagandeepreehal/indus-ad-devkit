"""Audit published annotation keys and per-stream coverage without downloading media."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

import pyarrow.parquet as pq

from dataset_devkit.config import IndusAdHfSourceConfig
from dataset_devkit.indus_ad_acquisition import IndusAdHfAcquirer
from dataset_devkit.indus_ad_contract import CAMERA_ANNOTATION_VIEWER_PATH, METADATA_PATH


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--cache-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    if args.output_dir.exists():
        parser.error("output directory must not exist")
    source = IndusAdHfSourceConfig(
        type="indus_ad_hf",
        contract="indus_ad_integrated_v1",
        repo_id=args.repo_id,
        revision=args.revision,
        splits=["train"],
        annotation_layers=["camera_scalar", "semantic_fractions", "depth_summary", "weather"],
    )
    acquirer = IndusAdHfAcquirer(source=source, cache_dir=args.cache_dir)
    acquirer.load_plan()  # verifies control hashes, schemas and dense-to-label identities
    metadata = [
        json.loads(line)
        for line in acquirer._control_files[METADATA_PATH].read_text().splitlines()
        if line.strip()
    ]
    table = pq.ParquetFile(acquirer._control_files[CAMERA_ANNOTATION_VIEWER_PATH]).read()
    rows = table.to_pylist()
    counts = Counter((r["recording_id"], r["camera_name"]) for r in rows)
    frame_ids = Counter(r["frame_id"] for r in rows)
    keys = Counter((r["recording_id"], r["camera_name"], r["recording_offset_ns"]) for r in rows)
    source_frames = Counter((r["recording_id"], r["camera_name"], r["frame_index"]) for r in rows)
    streams = {
        (r["recording_id"], k.removesuffix("_video_file_name"))
        for r in metadata
        for k, v in r.items()
        if k.endswith("_video_file_name") and v
    }
    orphan_streams = set(counts) - streams
    duplicates = {
        "frame_id": sum(n - 1 for n in frame_ids.values()),
        "camera_offset": sum(n - 1 for n in keys.values()),
        "camera_frame_index": sum(n - 1 for n in source_frames.values()),
    }
    if orphan_streams or any(duplicates.values()):
        raise ValueError(
            f"annotation identities invalid: {duplicates}, orphan streams={len(orphan_streams)}"
        )
    dense = Counter(
        (r.recording_id, r.camera_name, r.kind) for r in acquirer._annotations.dense_refs
    )
    per_stream = [
        {
            "recording_id": rid,
            "camera_name": camera,
            "annotation_rows": counts[(rid, camera)],
            "semantic_refs": dense[(rid, camera, "semantic")],
            "depth_refs": dense[(rid, camera, "depth")],
        }
        for rid, camera in sorted(streams)
    ]
    summary = {
        "schema_version": 1,
        "repository": args.repo_id,
        "source_revision": args.revision,
        "scope": (
            "verified camera-annotation Viewer and dense indexes; "
            "not a full source-table/frame or payload audit"
        ),
        "recordings": len(metadata),
        "video_streams": len(streams),
        "annotation_rows": len(rows),
        "distinct_frame_ids": len(frame_ids),
        "duplicate_counts": duplicates,
        "orphan_annotation_streams": len(orphan_streams),
        "streams_with_annotations": len(set(counts) & streams),
        "streams_without_annotations": len(streams - set(counts)),
        "dense_reference_counts": dict(Counter(r.kind for r in acquirer._annotations.dense_refs)),
        "per_camera": {
            camera: {
                "video_streams": sum(c == camera for _, c in streams),
                "annotated_streams": sum(c == camera for _, c in counts),
                "annotation_rows": sum(n for (_, c), n in counts.items() if c == camera),
            }
            for camera in sorted({c for _, c in streams})
        },
        "inputs": {
            p: {"bytes": f.stat().st_size, "sha256": hashlib.sha256(f.read_bytes()).hexdigest()}
            for p, f in sorted(acquirer._control_files.items())
        },
    }
    args.output_dir.mkdir(parents=True)
    with (args.output_dir / "annotation-coverage.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(per_stream[0]))
        writer.writeheader()
        writer.writerows(per_stream)
    summary["coverage_csv_sha256"] = hashlib.sha256(
        (args.output_dir / "annotation-coverage.csv").read_bytes()
    ).hexdigest()
    (args.output_dir / "annotation-coverage.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "inputs"}, indent=2))


if __name__ == "__main__":
    main()
