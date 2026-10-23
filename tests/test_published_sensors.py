from __future__ import annotations

import copy
import json
import math
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from scipy.spatial.transform import Rotation  # type: ignore[import-untyped]

from dataset_devkit.config import CameraName
from dataset_devkit.extraction.decoded import _calibrations
from dataset_devkit.extraction.decoded_gnss import interpolate_privacy_gnss, parse_privacy_gnss
from dataset_devkit.extraction.errors import StructuralExtractionError
from dataset_devkit.extraction.published_calibration import published_camera_extrinsic
from decoded_v2_fixture import write_decoded_fixture
from published_sensor_fixture import overlay, published_gnss_rows


def _messages(tmp_path: Path) -> tuple[Path, str, list[dict[str, Any]]]:
    fixture = write_decoded_fixture(tmp_path / "fixture")
    path = next((fixture.root / "data/tables/gnss").rglob("*.parquet"))
    rows = published_gnss_rows(pq.ParquetFile(path).read().to_pylist())
    return path, fixture.recording_id, rows


def test_published_gnss_uses_selected_channel_and_embedded_time(tmp_path: Path) -> None:
    path, rid, rows = _messages(tmp_path)
    decoy = [{**r, "channel": "rec_gnss"} for r in rows]
    pq.write_table(pa.Table.from_pylist([*rows, *decoy]), path)
    samples = parse_privacy_gnss(
        path, expected_recording_id=rid, channel="gnss", time_basis="time_offset_ns"
    )
    assert [s.recording_offset_ns for s in samples] == [0, 1_000_000_000]
    assert samples[1].local_east_m == 10.0
    assert samples[0].position_uncertainty == {"sigma_m": 0.1}
    assert samples[0].orientation_uncertainty == {"variance": 0.01}


@pytest.mark.parametrize(
    "mutation, message",
    [
        ("version", "schema version"),
        ("missing_time", "recording offset"),
        ("forbidden_time", "forbidden absolute time"),
        ("unknown_channel", "unsupported channel"),
        ("duplicate_time", "unique and strictly increasing"),
    ],
)
def test_published_gnss_rejects_ambiguous_or_unsafe_input(
    tmp_path: Path, mutation: str, message: str
) -> None:
    path, rid, rows = _messages(tmp_path)
    fields = json.loads(rows[0]["fields_json"])
    if mutation == "version":
        rows[0]["schema_version"] = 2
    elif mutation == "missing_time":
        fields["time_offset_ns"] = None
    elif mutation == "forbidden_time":
        fields["utc_timestamp_ns"] = 1
    elif mutation == "unknown_channel":
        rows[0]["channel"] = "unknown"
    elif mutation == "duplicate_time":
        other = json.loads(rows[1]["fields_json"])
        other["time_offset_ns"] = fields["time_offset_ns"]
        rows[1]["fields_json"] = json.dumps(other)
    rows[0]["fields_json"] = json.dumps(fields)
    pq.write_table(pa.Table.from_pylist(rows), path)
    with pytest.raises(StructuralExtractionError, match=message):
        parse_privacy_gnss(
            path, expected_recording_id=rid, channel="gnss", time_basis="time_offset_ns"
        )


def test_published_gnss_requires_policy_and_retains_invalid_coordinate_barrier(
    tmp_path: Path,
) -> None:
    path, rid, rows = _messages(tmp_path)
    fields = json.loads(rows[1]["fields_json"])
    fields["is_valid"] = False
    rows[1]["fields_json"] = json.dumps(fields)
    pq.write_table(pa.Table.from_pylist(rows), path)
    with pytest.raises(StructuralExtractionError, match="explicit"):
        parse_privacy_gnss(path, expected_recording_id=rid)
    samples = parse_privacy_gnss(
        path, expected_recording_id=rid, channel="gnss", time_basis="time_offset_ns"
    )
    assert samples[1].local_east_m == 10.0
    assert not samples[1].is_valid
    assert not interpolate_privacy_gnss(samples, 500_000_000).available


@pytest.mark.parametrize(
    "camera,yaw,tilt,expected",
    [
        ("cam_front", 0, 0, [1, 0, 0]),
        ("cam_rear", 180, 0, [-1, 0, 0]),
        (
            "cam_front_right",
            62.5,
            0,
            [math.cos(math.radians(62.5)), -math.sin(math.radians(62.5)), 0],
        ),
        ("cam_front_tilted", 0, 4, [math.cos(math.radians(4)), 0, -math.sin(math.radians(4))]),
    ],
)
def test_published_optical_forward_rays_have_documented_directions(
    camera: str, yaw: float, tilt: float, expected: list[float]
) -> None:
    result = published_camera_extrinsic(overlay(camera, yaw, tilt), camera=cast(CameraName, camera))
    rotation = Rotation.from_rotvec(result.rotation_vector).as_matrix()
    assert np.linalg.det(rotation) == pytest.approx(1)
    assert rotation @ [0, 0, 1] == pytest.approx(expected, abs=1e-12)
    if tilt:
        assert result.translation_vector == pytest.approx([0, 0, -0.046])


@pytest.mark.parametrize("mutation", ["camera", "units", "inverse", "nan", "reflection"])
def test_published_calibration_rejects_inconsistent_geometry(mutation: str) -> None:
    row = copy.deepcopy(overlay("cam_front"))
    if mutation == "camera":
        row["camera_name"] = "cam_rear"
    elif mutation == "units":
        row["translation_unit"] = "m"
    elif mutation == "inverse":
        row["T_camera_optical_from_front_reference"][3] = 1
    elif mutation == "nan":
        row["T_front_reference_from_camera_optical"][0] = float("nan")
    else:
        row["T_front_reference_from_camera_optical"][0] *= -1
    with pytest.raises(StructuralExtractionError):
        published_camera_extrinsic(row, camera="cam_front")


def test_published_calibration_cannot_fall_back_to_unverified_legacy_vectors(
    tmp_path: Path,
) -> None:
    path = tmp_path / "calibration.parquet"
    row = {
        "schema_version": 1,
        "recording_id": "fixture",
        "kind": "calibration",
        "key": "cam_front:0:0",
        "time_of_day_ns": 0,
        "time_offset_ns": 0,
        "fields_json": "{}",
    }
    pq.write_table(pa.Table.from_pylist([row]), path)
    bundle = SimpleNamespace(
        entry=SimpleNamespace(
            recording_id="fixture", artifacts_of=lambda _: [SimpleNamespace(path="x")]
        ),
        path=lambda _: path,
    )
    with pytest.raises(StructuralExtractionError, match="no verified calibrated_extrinsics"):
        _calibrations(bundle)
