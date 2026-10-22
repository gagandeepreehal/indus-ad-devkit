"""Read the producer's matrix overlay without interpreting legacy source vectors."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

import numpy as np
from scipy.spatial.transform import Rotation  # type: ignore[import-untyped]

from dataset_devkit.config import CameraName
from dataset_devkit.extraction.errors import StructuralExtractionError
from dataset_devkit.extraction.models import CameraExtrinsic

CALIBRATION_ID = "indus-ad-seven-camera-owner-confirmed-2026-10-23-v1"


def _vector(value: object, size: int) -> list[float]:
    if (
        not isinstance(value, list)
        or len(value) != size
        or any(
            not isinstance(item, (int, float)) or isinstance(item, bool) or not math.isfinite(item)
            for item in value
        )
    ):
        raise StructuralExtractionError("published calibration vector is invalid")
    return [float(item) for item in value]


def published_camera_extrinsic(value: object, *, camera: CameraName) -> CameraExtrinsic:
    """Convert optical -> left-handed front reference -> right-handed ego, in metres.

    Export ego is X forward, Y left, Z up at the front camera centre. Swapping
    source X/Y changes handedness; the optical-to-ego product is a proper rotation.
    GNSS Euler angles retain the devkit's existing right-handed XYZ convention.
    """
    if not isinstance(value, Mapping):
        raise StructuralExtractionError("published calibrated_extrinsics must be an object")
    required = {
        "calibration_id": CALIBRATION_ID,
        "camera_name": camera,
        "rig_axes": "x_left,y_forward,z_up; left_handed",
        "optical_axes": "x_right,y_down,z_forward; right_handed",
        "translation_unit": "mm",
        "angle_unit": "degree",
    }
    if any(value.get(key) != expected for key, expected in required.items()):
        raise StructuralExtractionError("published calibration identity/units/axes are unsupported")
    if not isinstance(value.get("provenance"), str) or not value["provenance"]:
        raise StructuralExtractionError("published calibration provenance is missing")
    matrices: dict[str, Any] = {}
    for key in (
        "T_rig_from_camera_mount",
        "T_front_reference_from_camera_mount",
        "T_rig_from_camera_optical",
        "T_front_reference_from_camera_optical",
        "T_camera_optical_from_front_reference",
    ):
        matrix = np.asarray(_vector(value.get(key), 16)).reshape(4, 4)
        if not np.allclose(matrix[3], [0, 0, 0, 1], rtol=0, atol=1e-10):
            raise StructuralExtractionError("published calibration homogeneous row is invalid")
        matrices[key] = matrix
    rig_center = _vector(value.get("camera_center_rig_mm"), 3)
    front_center = _vector(value.get("camera_center_front_reference_mm"), 3)
    angles = _vector([value.get("yaw_right_deg"), value.get("tilt_down_deg")], 2)
    yaw, tilt = (math.radians(item) for item in angles)
    cy, sy, ct, st = math.cos(yaw), math.sin(yaw), math.cos(tilt), math.sin(tilt)
    mount_rotation = np.asarray([[cy, -sy * ct, -sy * st], [sy, cy * ct, cy * st], [0, -st, ct]])
    basis = np.eye(4)
    basis[:3, :3] = [[-1, 0, 0], [0, 0, 1], [0, -1, 0]]
    for frame, center in (("rig", rig_center), ("front_reference", front_center)):
        expected = np.eye(4)
        expected[:3, :3] = mount_rotation
        expected[:3, 3] = center
        if not np.allclose(
            matrices[f"T_{frame}_from_camera_mount"], expected, rtol=0, atol=1e-8
        ) or not np.allclose(
            matrices[f"T_{frame}_from_camera_optical"], expected @ basis, rtol=0, atol=1e-8
        ):
            raise StructuralExtractionError(
                "published calibration matrices disagree with parameters"
            )
    optical_to_front = matrices["T_front_reference_from_camera_optical"]
    if not np.allclose(
        matrices["T_camera_optical_from_front_reference"] @ optical_to_front,
        np.eye(4),
        rtol=0,
        atol=1e-8,
    ) or not np.allclose(
        np.asarray(rig_center) - front_center,
        [0, 0, 1546],
        rtol=0,
        atol=1e-8,
    ):
        raise StructuralExtractionError("published calibration inverse/origin is inconsistent")
    front_to_ego = np.asarray([[0, 1, 0], [1, 0, 0], [0, 0, 1]])
    rotation = front_to_ego @ optical_to_front[:3, :3]
    if not np.allclose(rotation.T @ rotation, np.eye(3), rtol=0, atol=1e-10) or not math.isclose(
        float(np.linalg.det(rotation)), 1.0, rel_tol=0, abs_tol=1e-10
    ):
        raise StructuralExtractionError("published optical-to-ego rotation is not proper")
    vector = Rotation.from_matrix(rotation).as_rotvec()
    translation = front_to_ego @ optical_to_front[:3, 3] / 1000.0
    return CameraExtrinsic(
        tuple(float(item) for item in vector), tuple(float(item) for item in translation)
    )
