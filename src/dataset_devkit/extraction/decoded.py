"""Decoded V2 MP4/Parquet adapter for the existing extraction pipeline."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from fractions import Fraction
from pathlib import Path
from typing import Any, Protocol, cast

import av
import pyarrow.parquet as pq

from dataset_devkit.config import CameraName, GnssChannel, GnssTimeBasis
from dataset_devkit.extraction.decoded_gnss import (
    interpolate_privacy_gnss,
    parse_privacy_gnss,
)
from dataset_devkit.extraction.errors import StructuralExtractionError
from dataset_devkit.extraction.grid import GridSelection, select_camera_grid
from dataset_devkit.extraction.models import (
    CameraCalibration,
    CameraExtrinsic,
    CameraIntrinsic,
    EgoPose,
    ExtractedCameraSample,
    PrivacyGnssSample,
    RawCameraBatch,
    RawCameraFrame,
    RecordingExtractionResult,
    TimestampObservation,
)
from dataset_devkit.extraction.published_calibration import published_camera_extrinsic
from dataset_devkit.extraction.service import OwnedRecordingExtraction
from dataset_devkit.extraction.staging import (
    create_staging_invocation,
    rollback_staging_invocation,
    stage_jpeg,
)
from dataset_devkit.publication import OwnedDirectoryCleanupError

_SIMPLE_FRAME_COLUMNS = {
    "recording_id",
    "camera_name",
    "frame_index",
    "recording_offset_ns",
    "width",
    "height",
}
_PRODUCTION_FRAME_REQUIRED = {
    "recording_id",
    "camera_index",
    "camera_time_offset_ns",
    "batch_time_offset_ns",
    "frame_id",
    "rec_frame_id",
    "packet_index",
    "source_camera_name",
    "width",
    "height",
}
_SIMPLE_CALIBRATION_COLUMNS = {
    "recording_id",
    "camera_name",
    "width",
    "height",
    "focal_length_x",
    "focal_length_y",
    "optical_center_x",
    "optical_center_y",
    "skew",
    "rmse",
    "distortion_coeffs",
    "rotation_vector",
    "translation_vector",
}
_PRODUCTION_CALIBRATION_REQUIRED = {
    "recording_id",
    "camera",
    "camera_index",
    "intrinsic_json",
    "extrinsic_json",
}
_PUBLISHED_CALIBRATION_COLUMNS = {
    "schema_version",
    "recording_id",
    "kind",
    "key",
    "time_of_day_ns",
    "time_offset_ns",
    "fields_json",
}


@dataclass(frozen=True, slots=True)
class _CameraRow:
    camera: CameraName
    frame_index: int
    frame_id: int
    rec_frame_id: int
    batch_offset_ns: int
    recording_offset_ns: int
    width: int
    height: int


class _ArtifactLike(Protocol):
    @property
    def path(self) -> str: ...


class _VideoLike(_ArtifactLike, Protocol):
    @property
    def camera(self) -> CameraName: ...

    @property
    def frame_count(self) -> int | None: ...


class _EntryLike(Protocol):
    @property
    def recording_id(self) -> str: ...

    @property
    def videos(self) -> Sequence[_VideoLike]: ...

    def artifacts_of(self, kind: str) -> Sequence[_ArtifactLike]: ...

    def artifact(self, kind: str) -> _ArtifactLike: ...


class _DecodedBundle(Protocol):
    @property
    def entry(self) -> _EntryLike: ...

    def path(self, repo_path: str) -> Path: ...


def _read_rows(path: Path, label: str) -> tuple[set[str], list[dict[str, object]]]:
    try:
        parquet = pq.ParquetFile(path)
        return set(parquet.schema_arrow.names), cast(
            list[dict[str, object]], parquet.read().to_pylist()
        )
    except Exception as error:
        raise StructuralExtractionError(f"decoded {label} Parquet is invalid") from error


def _integer(value: object, label: str, *, nonnegative: bool = True) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or (nonnegative and value < 0):
        raise StructuralExtractionError(f"decoded {label} must be an integer")
    return value


def _number(value: object, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise StructuralExtractionError(f"decoded {label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise StructuralExtractionError(f"decoded {label} must be finite")
    return result


def _camera(value: object) -> CameraName:
    if value not in {
        "cam_front",
        "cam_front_left",
        "cam_front_right",
        "cam_front_tilted",
        "cam_rear",
        "cam_rear_left",
        "cam_rear_right",
    }:
        raise StructuralExtractionError("decoded camera frame contains an unknown camera")
    return cast(CameraName, value)


def _camera_rows(
    bundle: _DecodedBundle, *, batch_time_basis: str = "batch_time_offset_ns"
) -> tuple[_CameraRow, ...]:
    if batch_time_basis not in {"batch_time_offset_ns", "rec_time_offset_ns"}:
        raise ValueError("unsupported camera batch time basis")
    shared_recorded_offsets: dict[tuple[str, int], int] = {}
    result: list[_CameraRow] = []
    next_index: dict[CameraName, int] = defaultdict(int)
    previous_offset: dict[CameraName, int] = {}
    source_indexes: dict[CameraName, int] = {}
    for artifact in bundle.entry.artifacts_of("camera_frames"):
        columns, rows = _read_rows(bundle.path(artifact.path), "camera frame")
        simple = columns == _SIMPLE_FRAME_COLUMNS
        production = columns >= _PRODUCTION_FRAME_REQUIRED
        if not simple and not production:
            raise StructuralExtractionError("decoded camera frame schema is unsupported")
        if simple and batch_time_basis != "batch_time_offset_ns":
            raise StructuralExtractionError(
                "recorded-camera clock requires production frame schema"
            )
        for row in rows:
            if row.get("recording_id") != bundle.entry.recording_id:
                raise StructuralExtractionError("decoded camera frame recording identity differs")
            camera = _camera(row.get("camera_name" if simple else "source_camera_name"))
            frame_index = _integer(
                row.get("frame_index" if simple else "packet_index"), "frame index"
            )
            if frame_index != next_index[camera]:
                raise StructuralExtractionError("decoded camera frame indices are not contiguous")
            if production:
                source_index = _integer(row.get("camera_index"), "camera index")
                previous_source_index = source_indexes.setdefault(camera, source_index)
                if source_index != previous_source_index:
                    raise StructuralExtractionError("decoded camera index changes within a camera")
            offset = _integer(
                row.get("recording_offset_ns" if simple else "camera_time_offset_ns"),
                "camera recording offset",
            )
            batch_offset = _integer(
                row.get("recording_offset_ns" if simple else batch_time_basis),
                "batch recording offset",
                nonnegative=False,
            )
            if batch_time_basis == "rec_time_offset_ns":
                message_index = _integer(row.get("message_index"), "message index")
                channel = row.get("channel")
                if not isinstance(channel, str) or not channel:
                    raise StructuralExtractionError("recorded-camera clock requires source channel")
                key = (channel, message_index)
                previous = shared_recorded_offsets.setdefault(key, batch_offset)
                if previous != batch_offset:
                    raise StructuralExtractionError(
                        "recorded-camera timestamps differ within batch"
                    )
            frame_id = _integer(
                row.get("frame_index" if simple else "frame_id"),
                "frame ID",
                nonnegative=False,
            )
            rec_frame_id = _integer(
                row.get("frame_index" if simple else "rec_frame_id"),
                "recording frame ID",
                nonnegative=False,
            )
            if camera in previous_offset and offset <= previous_offset[camera]:
                raise StructuralExtractionError("decoded camera frame rows are out of order")
            width = _integer(row.get("width"), "camera width")
            height = _integer(row.get("height"), "camera height")
            if width <= 0 or height <= 0:
                raise StructuralExtractionError("decoded camera frame dimensions are invalid")
            result.append(
                _CameraRow(
                    camera,
                    frame_index,
                    frame_id,
                    rec_frame_id,
                    batch_offset,
                    offset,
                    width,
                    height,
                )
            )
            next_index[camera] += 1
            previous_offset[camera] = offset
    if not result:
        raise StructuralExtractionError("decoded camera frame table is empty")
    return tuple(result)


def _json_mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, str):
        raise StructuralExtractionError(f"decoded {label} JSON is invalid")
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError as error:
        raise StructuralExtractionError(f"decoded {label} JSON is invalid") from error
    if not isinstance(decoded, dict):
        raise StructuralExtractionError(f"decoded {label} JSON is invalid")
    return cast(Mapping[str, Any], decoded)


def _calibration_from_values(
    intrinsic: Mapping[str, Any], extrinsic: Mapping[str, Any]
) -> CameraCalibration:
    distortion = intrinsic.get("distortion_coeffs", intrinsic.get("distortion", []))
    rotation = extrinsic.get("rotation_vector", extrinsic.get("rotation", []))
    translation = extrinsic.get("translation_vector", extrinsic.get("translation", []))
    if not all(isinstance(value, list) for value in (distortion, rotation, translation)):
        raise StructuralExtractionError("decoded calibration vectors are invalid")
    return CameraCalibration(
        CameraIntrinsic(
            _number(intrinsic.get("focal_length_x"), "focal length x"),
            _number(intrinsic.get("focal_length_y"), "focal length y"),
            _number(intrinsic.get("optical_center_x"), "optical center x"),
            _number(intrinsic.get("optical_center_y"), "optical center y"),
            _number(intrinsic.get("rmse", 0.0), "calibration RMSE"),
            _number(intrinsic.get("skew", 0.0), "calibration skew"),
            tuple(_number(item, "distortion coefficient") for item in distortion),
            _number(intrinsic.get("width"), "calibration width"),
            _number(intrinsic.get("height"), "calibration height"),
        ),
        CameraExtrinsic(
            tuple(_number(item, "rotation vector") for item in rotation),
            tuple(_number(item, "translation vector") for item in translation),
        ),
    )


def _calibrations(
    bundle: _DecodedBundle,
    *,
    use_published_calibration: bool = False,
) -> dict[CameraName, CameraCalibration]:
    result: dict[CameraName, CameraCalibration] = {}
    overlays: dict[CameraName, object] = {}
    for artifact in bundle.entry.artifacts_of("calibration"):
        columns, rows = _read_rows(bundle.path(artifact.path), "calibration")
        simple = columns == _SIMPLE_CALIBRATION_COLUMNS
        production = columns >= _PRODUCTION_CALIBRATION_REQUIRED
        if columns == _PUBLISHED_CALIBRATION_COLUMNS:
            raise StructuralExtractionError(
                "legacy calibration has no verified calibrated_extrinsics; pin the newer overlay"
            )
        published = columns == _PUBLISHED_CALIBRATION_COLUMNS | {"calibrated_extrinsics"}
        if not simple and not production and not published:
            raise StructuralExtractionError("decoded calibration schema is unsupported")
        for row in rows:
            if row.get("recording_id") != bundle.entry.recording_id:
                raise StructuralExtractionError("decoded calibration recording identity differs")
            if published:
                if not use_published_calibration:
                    raise StructuralExtractionError(
                        "published calibration requires explicit calibrated_ego_frame"
                    )
                if (
                    row.get("schema_version") != 1
                    or isinstance(row.get("schema_version"), bool)
                    or row.get("kind") != "calibration"
                ):
                    raise StructuralExtractionError(
                        "decoded calibration row version/kind is unsupported"
                    )
                key = row.get("key")
                parts = key.split(":") if isinstance(key, str) else []
                if len(parts) != 3 or any(not part.isdecimal() for part in parts[1:]):
                    raise StructuralExtractionError("decoded calibration key is invalid")
                camera = _camera(parts[0])
                payload = _json_mapping(row.get("fields_json"), "calibration")
                native_intrinsic = payload.get("intrinsic")
                if not isinstance(native_intrinsic, Mapping):
                    raise StructuralExtractionError(
                        "decoded calibration requires an intrinsic object"
                    )
                overlay = row["calibrated_extrinsics"]
                if camera in overlays and overlays[camera] != overlay:
                    raise StructuralExtractionError("published calibration changes within a camera")
                if camera not in overlays:
                    native_extrinsic = published_camera_extrinsic(overlay, camera=camera)
                    overlays[camera] = overlay
                else:
                    native_extrinsic = result[camera].extrinsic
                calibration = _calibration_from_values(
                    native_intrinsic,
                    {
                        "rotation_vector": list(native_extrinsic.rotation_vector),
                        "translation_vector": list(native_extrinsic.translation_vector),
                    },
                )
                if camera in result and result[camera] != calibration:
                    raise StructuralExtractionError("decoded calibration changes within a camera")
                result[camera] = calibration
                continue
            camera = _camera(row.get("camera_name" if simple else "camera"))
            if camera in result:
                raise StructuralExtractionError("decoded calibration contains a duplicate camera")
            if simple:
                intrinsic: Mapping[str, Any] = row
                extrinsic: Mapping[str, Any] = row
            else:
                intrinsic = _json_mapping(row.get("intrinsic_json"), "intrinsic")
                extrinsic = _json_mapping(row.get("extrinsic_json"), "extrinsic")
            result[camera] = _calibration_from_values(intrinsic, extrinsic)
    return result


def _observations(
    rows: tuple[_CameraRow, ...], gnss: tuple[PrivacyGnssSample, ...]
) -> tuple[TimestampObservation, ...]:
    output: list[TimestampObservation] = []
    by_camera: dict[CameraName, list[int]] = defaultdict(list)
    for row in rows:
        by_camera[row.camera].append(row.recording_offset_ns)
    for camera in sorted(by_camera):
        values = by_camera[camera]
        output.extend(
            TimestampObservation(f"camera:{camera}", left, right, right - left)
            for left, right in zip(values, values[1:], strict=False)
        )
    output.extend(
        TimestampObservation(
            "gnss",
            left.recording_offset_ns,
            right.recording_offset_ns,
            right.recording_offset_ns - left.recording_offset_ns,
        )
        for left, right in zip(gnss, gnss[1:], strict=False)
    )
    return tuple(output)


class DecodedRecordingExtractor:
    """Decode selected MP4 frames and adapt them into native extraction records."""

    def __init__(
        self,
        *,
        target_fps: Fraction | float | str,
        tolerance_ns: int,
        staging_root: Path,
        gnss_channel: GnssChannel | None = None,
        gnss_time_basis: GnssTimeBasis | None = None,
        use_published_calibration: bool = False,
        resize_intrinsics: bool = False,
        camera_batch_time_basis: str = "batch_time_offset_ns",
    ) -> None:
        self.target_fps = (
            target_fps if isinstance(target_fps, Fraction) else Fraction(str(target_fps))
        )
        if self.target_fps <= 0:
            raise ValueError("target_fps must be positive")
        if tolerance_ns < 0:
            raise ValueError("tolerance_ns must be nonnegative")
        self.tolerance_ns = tolerance_ns
        self.staging_root = staging_root
        self.gnss_channel = gnss_channel
        self.gnss_time_basis = gnss_time_basis
        self.use_published_calibration = use_published_calibration
        self.resize_intrinsics = resize_intrinsics
        self.camera_batch_time_basis = camera_batch_time_basis

    def extract_owned(self, bundle: _DecodedBundle) -> OwnedRecordingExtraction:
        rows = _camera_rows(bundle, batch_time_basis=self.camera_batch_time_basis)
        selected_cameras = tuple(video.camera for video in bundle.entry.videos)
        if len(selected_cameras) != len(set(selected_cameras)):
            raise StructuralExtractionError("decoded videos contain duplicate cameras")
        rows = tuple(row for row in rows if row.camera in selected_cameras)
        by_camera: dict[CameraName, list[_CameraRow]] = defaultdict(list)
        for row in rows:
            by_camera[row.camera].append(row)
        for video in bundle.entry.videos:
            if video.frame_count is None or len(by_camera[video.camera]) != video.frame_count:
                raise StructuralExtractionError(f"decoded frame count differs for {video.camera}")
        calibrations = _calibrations(
            bundle, use_published_calibration=self.use_published_calibration
        )
        if set(selected_cameras) - set(calibrations):
            raise StructuralExtractionError("decoded calibration is missing a selected camera")
        if self.resize_intrinsics:
            for camera in selected_cameras:
                dimensions = {(row.width, row.height) for row in by_camera[camera]}
                if len(dimensions) != 1:
                    raise StructuralExtractionError(
                        "camera image dimensions change within recording"
                    )
                width, height = next(iter(dimensions))
                calibration = calibrations[camera]
                intrinsic = calibration.intrinsic
                if (
                    intrinsic.width <= 0
                    or intrinsic.height <= 0
                    or not math.isclose(
                        width * intrinsic.height, height * intrinsic.width, rel_tol=1e-9
                    )
                ):
                    raise StructuralExtractionError("pure-resize intrinsic aspect ratio differs")
                sx, sy = width / intrinsic.width, height / intrinsic.height
                calibrations[camera] = replace(
                    calibration,
                    intrinsic=replace(
                        intrinsic,
                        width=float(width),
                        height=float(height),
                        focal_length_x=intrinsic.focal_length_x * sx,
                        focal_length_y=intrinsic.focal_length_y * sy,
                        optical_center_x=intrinsic.optical_center_x * sx,
                        optical_center_y=intrinsic.optical_center_y * sy,
                        skew=intrinsic.skew * sx,
                    ),
                )
        for camera, calibration in calibrations.items():
            camera_rows = by_camera.get(camera, [])
            if camera in selected_cameras and any(
                (row.width, row.height)
                != (int(calibration.intrinsic.width), int(calibration.intrinsic.height))
                for row in camera_rows
            ):
                raise StructuralExtractionError(
                    "decoded calibration dimensions differ from camera frames"
                )
        gnss = parse_privacy_gnss(
            bundle.path(bundle.entry.artifact("gnss").path),
            expected_recording_id=bundle.entry.recording_id,
            channel=self.gnss_channel,
            time_basis=self.gnss_time_basis,
        )
        offsets = sorted({row.batch_offset_ns for row in rows})
        # Producer batch clocks may precede the first video frame. Retain those
        # signed source offsets, but export only the recording interval >= 0.
        selection = select_camera_grid(
            [offset for offset in offsets if offset >= 0], self.target_fps, self.tolerance_ns
        )
        selection = GridSelection(
            selection.entries,
            selection.misses,
            tuple(offset for offset in offsets if offset < 0)
            + selection.unused_batch_timestamps_ns,
        )
        return self._decode(bundle, by_camera, calibrations, gnss, selection)

    def _decode(
        self,
        bundle: _DecodedBundle,
        by_camera: Mapping[CameraName, list[_CameraRow]],
        calibrations: Mapping[CameraName, CameraCalibration],
        gnss: tuple[PrivacyGnssSample, ...],
        selection: GridSelection,
    ) -> OwnedRecordingExtraction:
        selected_target = {
            item.batch_timestamp_ns: item.target_timestamp_ns for item in selection.entries
        }
        ordered_offsets = sorted(
            {row.batch_offset_ns for camera_rows in by_camera.values() for row in camera_rows}
        )
        offset_ordinal = {offset: index for index, offset in enumerate(ordered_offsets)}
        poses: dict[int, EgoPose] = {}
        samples: list[ExtractedCameraSample] = []
        invocation = create_staging_invocation(self.staging_root, bundle.entry.recording_id)
        authority = invocation.authority
        if authority is None:
            rollback_staging_invocation(invocation)
            raise StructuralExtractionError("decoded staging authority was not established")

        def pose_for(offset: int) -> EgoPose:
            existing = poses.get(offset)
            if existing is not None:
                return existing
            interpolation = interpolate_privacy_gnss(gnss, offset)
            if interpolation.available:
                if interpolation.translation_xyz_m is None or interpolation.quaternion_wxyz is None:
                    raise StructuralExtractionError("available decoded GNSS pose lacks geometry")
                pose = EgoPose(
                    offset,
                    True,
                    interpolation.translation_xyz_m,
                    interpolation.quaternion_wxyz,
                    interpolation,
                )
            else:
                # As in the MCAP extractor, preserve unavailable poses for validity
                # evaluation instead of treating ordinary GNSS gaps as corruption.
                pose = EgoPose(offset, False, None, None, interpolation)
            poses[offset] = pose
            return pose

        try:
            for camera_index, video in enumerate(bundle.entry.videos):
                expected_rows = by_camera[video.camera]
                decoded_count = 0
                try:
                    with av.open(str(bundle.path(video.path))) as container:
                        for frame_index, frame in enumerate(container.decode(video=0)):
                            decoded_count += 1
                            if frame_index >= len(expected_rows):
                                raise StructuralExtractionError(
                                    f"decoded video frame count differs for {video.camera}"
                                )
                            row = expected_rows[frame_index]
                            image = frame.to_image()  # type: ignore[no-untyped-call]
                            if image.size != (row.width, row.height):
                                raise StructuralExtractionError(
                                    f"decoded video dimensions differ for {video.camera}"
                                )
                            target = selected_target.get(row.batch_offset_ns)
                            if target is None:
                                continue
                            staged = stage_jpeg(
                                self.staging_root,
                                invocation.directory_name,
                                camera_index,
                                video.camera,
                                row.recording_offset_ns,
                                image,
                                (row.width, row.height),
                                batch_ordinal=offset_ordinal[row.batch_offset_ns],
                                invocation=invocation,
                            )
                            samples.append(
                                ExtractedCameraSample(
                                    target,
                                    row.batch_offset_ns,
                                    row.recording_offset_ns,
                                    camera_index,
                                    video.camera,
                                    staged,
                                    pose_for(row.recording_offset_ns),
                                    calibrations[video.camera],
                                )
                            )
                except StructuralExtractionError:
                    raise
                except Exception as error:
                    raise StructuralExtractionError(
                        f"decoded video could not be read for {video.camera}"
                    ) from error
                if decoded_count != video.frame_count:
                    raise StructuralExtractionError(
                        f"decoded video frame count differs for {video.camera}"
                    )

            samples.sort(
                key=lambda item: (
                    item.grid_target_timestamp_ns,
                    item.camera_index,
                    item.camera_timestamp_ns,
                )
            )
            raw_batches = tuple(
                RawCameraBatch(
                    offset,
                    offset,
                    ordinal,
                    ordinal,
                    "decoded_mp4",
                    next(
                        row.width
                        for rows in by_camera.values()
                        for row in rows
                        if row.batch_offset_ns == offset
                    ),
                    next(
                        row.height
                        for rows in by_camera.values()
                        for row in rows
                        if row.batch_offset_ns == offset
                    ),
                    tuple(
                        RawCameraFrame(
                            camera_index,
                            video.camera,
                            row.recording_offset_ns,
                            calibrations[video.camera],
                        )
                        for camera_index, video in enumerate(bundle.entry.videos)
                        for row in by_camera[video.camera]
                        if row.batch_offset_ns == offset
                    ),
                )
                for ordinal, offset in enumerate(ordered_offsets)
            )
            source_path = bundle.path(bundle.entry.videos[0].path)
            return OwnedRecordingExtraction(
                RecordingExtractionResult(
                    source_path,
                    invocation.path,
                    raw_batches,
                    gnss,
                    selection,
                    tuple(samples),
                    poses,
                    _observations(tuple(row for rows in by_camera.values() for row in rows), gnss),
                ),
                authority,
            )
        except Exception as extraction_error:
            try:
                rollback_staging_invocation(invocation)
            except Exception as rollback_error:
                cleanup_error = OwnedDirectoryCleanupError((authority.cleanup_failure(),))
                cleanup_error.add_note(f"rollback failed with {type(rollback_error).__name__}")
                raise cleanup_error from extraction_error
            raise
