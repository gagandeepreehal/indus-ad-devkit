"""Synthetic rows matching the published sensor layouts; no production sensor rows."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from dataset_devkit.extraction.published_calibration import CALIBRATION_ID


def overlay(camera: str, yaw: float = 0.0, tilt: float = 0.0) -> dict[str, Any]:
    a, b = math.radians(yaw), math.radians(-tilt)
    rz = np.asarray([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]])
    rx = np.asarray([[1, 0, 0], [0, math.cos(b), -math.sin(b)], [0, math.sin(b), math.cos(b)]])
    front = np.eye(4)
    front[:3, :3] = rz @ rx
    front[:3, 3] = [0, 0, -46 if tilt else 0]
    rig = front.copy()
    rig[2, 3] += 1546
    basis = np.eye(4)
    basis[:3, :3] = [[-1, 0, 0], [0, 0, 1], [0, -1, 0]]
    optical = front @ basis
    return {
        "calibration_id": CALIBRATION_ID,
        "camera_name": camera,
        "provenance": "synthetic fixture of the published schema",
        "rig_axes": "x_left,y_forward,z_up; left_handed",
        "optical_axes": "x_right,y_down,z_forward; right_handed",
        "translation_unit": "mm",
        "angle_unit": "degree",
        "yaw_right_deg": yaw,
        "tilt_down_deg": tilt,
        "camera_center_rig_mm": rig[:3, 3].tolist(),
        "camera_center_front_reference_mm": front[:3, 3].tolist(),
        "T_rig_from_camera_mount": rig.reshape(-1).tolist(),
        "T_front_reference_from_camera_mount": front.reshape(-1).tolist(),
        "T_rig_from_camera_optical": (rig @ basis).reshape(-1).tolist(),
        "T_front_reference_from_camera_optical": optical.reshape(-1).tolist(),
        "T_camera_optical_from_front_reference": np.linalg.inv(optical).reshape(-1).tolist(),
    }


def published_gnss_rows(flat: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in flat:
        fields = {k: v for k, v in row.items() if k not in {"recording_id", "recording_offset_ns"}}
        for source, target in (
            ("position_uncertainty", "position_error"),
            ("orientation_uncertainty", "orientation_error"),
            ("quality", "position_type_info"),
        ):
            fields[target] = fields.pop(source)
        fields.update(time_offset_ns=row["recording_offset_ns"], rec_time_offset_ns=None)
        rows.append(
            {
                "schema_version": 1,
                "recording_id": row["recording_id"],
                "log_time_of_day_ns": 10000000000 + row["recording_offset_ns"],
                "log_time_offset_ns": row["recording_offset_ns"] + 100,
                "publish_time_of_day_ns": 10000000000 + row["recording_offset_ns"],
                "publish_time_offset_ns": row["recording_offset_ns"] + 200,
                "channel": "gnss",
                "schema_hash": "a" * 64,
                "sequence": len(rows),
                "fields_json": json.dumps(fields),
            }
        )
    return rows


def rewrite_published_tables(root: Path) -> None:
    calibration_path = next((root / "data/tables/calibrations").rglob("*.parquet"))
    originals = pq.ParquetFile(calibration_path).read().to_pylist()
    rows = []
    for row in originals:
        intrinsic = {
            k: v
            for k, v in row.items()
            if k not in {"recording_id", "camera_name", "rotation_vector", "translation_vector"}
        }
        # A confirmed pure resize by 2:1; decoded fixture images remain 4x4.
        for key in (
            "width",
            "height",
            "focal_length_x",
            "focal_length_y",
            "optical_center_x",
            "optical_center_y",
            "skew",
        ):
            intrinsic[key] *= 2
        fields = {
            "intrinsic": intrinsic,
            "extrinsic": {"rotation_vector": [1, 2, 3], "translation_vector": [4, 5, 6]},
        }
        for index in range(2):
            rows.append(
                {
                    "schema_version": 1,
                    "recording_id": row["recording_id"],
                    "kind": "calibration",
                    "key": f"{row['camera_name']}:0:{index}",
                    "time_of_day_ns": 10000000000 + index,
                    "time_offset_ns": index,
                    "fields_json": json.dumps(fields),
                    "calibrated_extrinsics": overlay(row["camera_name"]),
                }
            )
    pq.write_table(pa.Table.from_pylist(rows), calibration_path)
    gnss_path = next((root / "data/tables/gnss").rglob("*.parquet"))
    flat = pq.ParquetFile(gnss_path).read().to_pylist()
    rows = published_gnss_rows(flat)
    # Overlapping offsets on another stream must not leak into the selected stream.
    rows.extend([{**row, "channel": "rec_gnss"} for row in rows])
    pq.write_table(pa.Table.from_pylist(rows), gnss_path)
