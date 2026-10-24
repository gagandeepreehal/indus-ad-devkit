# Camera and GNSS timing and trimming

Camera extraction, synchronization, exported camera timestamps and ego-pose queries default to the camera payload `rec_timestamp`, published as `rec_time_offset_ns`. The main GNSS channel is `gnss`, using its payload `timestamp`, published as `time_offset_ns`. The devkit does not replace GNSS sensor time with logger time or combine `gnss` and `rec_gnss` into one trajectory.

```json
{
  "camera_batch_time_basis": "rec_time_offset_ns",
  "gnss_channel": "gnss",
  "gnss_time_basis": "time_offset_ns"
}
```

Both offsets subtract the same recording anchor from their respective source fields. This preserves their original differences; subtraction does not calibrate clocks. Camera payload `timestamp` is a separate producer batch field. It can be zero while `rec_timestamp` is populated. Camera messages must have consistent recorded timestamps within the same source channel and message index. Per-camera source timestamps, raw tables and annotation source identities remain unchanged.

## Missing GNSS messages

Some messages marked `is_valid=false` have no sensor timestamp, attitude or position. The reader does not reject an otherwise usable recording solely for these messages. It counts untimed messages in source order and marks the gap between the surrounding timestamped readings. It does not assign a logger timestamp, interpolate across that gap, invent a pose or assign a confidence value.

Camera batches in an untimed GNSS gap are excluded from the exported target grid. A leading untimed portion before the first timestamped GNSS reading is trimmed from the exported selection; a trailing untimed portion after the last timestamped reading is treated similarly. Internal gaps remain excluded, while usable portions before and after them can be processed. Retained timestamps are not shifted to zero. Original videos and tables are not cut or rewritten. Excluded selected batches remain in the unused-batch audit, and GNSS samples retain untimed-message counts before and after them.

Messages with a sensor timestamp but `is_valid=false` remain timed interpolation barriers under the existing quality policy. Missing diagnostics on these messages remain null. Valid messages still require the declared fields. Malformed identities, contradictory origins, nonmonotonic timed samples and other structural errors remain failures. A recording with no timestamped GNSS samples, or insufficient usable data for the requested scenes, cannot produce a valid export.

## Verified affected recordings

The complete main-GNSS and recorded-GNSS tables were checked for both affected recordings:

| Recording | Main GNSS missing sensor time | Recorded GNSS missing sensor and recorded time |
| --- | ---: | ---: |
| `12-49-25.221-40d21e3d61dd406862e4a42a9f6de418` | 326 | 65 |
| `11-46-51.922-ea6fa65e862f7b73626fb45a6400960f` | 80 | 16 |

The first recording has untimed messages near its beginning. The second has an internal gap near 3,750.50–3,752.08 seconds on the logger-relative timeline, with timed main-GNSS messages afterwards. These bounds locate the source messages; they are not substituted sensor timestamps. Switching to `rec_gnss` does not recover the missing information.

Source checks matched the failing event in each of the 59 investigated recordings against its original immutable MCAP. This was a bounded event check, not a full decode of all source MCAPs. The 471 relevant camera/GNSS tables have identical Git objects across the retained history back to the October snapshot. Metadata acceptance, video-build acceptance and hardware synchronization accuracy are separate claims.

## Original mz datagen convention

The original `mz_datagen/dump_data_with_sync.py` used camera `rec_timestamp` to query and interpolate main `gnss` payload `timestamp`. Its defaults sampled every fifth camera message for 2 FPS from 10 FPS, with a 30 ms bracketing check. This establishes the original software convention; it does not independently measure clock alignment accuracy.
