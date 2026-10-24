# Source metadata compatibility

The current policy uses camera `rec_time_offset_ns` and main `gnss` sensor
`time_offset_ns`. Consistent nonzero GNSS origins are preserved. Untimed
quality-flagged messages mark excluded portions rather than causing whole
recording rejection. See [timing and trimming](timing-and-trimming.md).

A new metadata audit across all 1,469 source recordings is running at immutable
revision `a1f1d72b73984ef129ac8b3d882f9074bc587205`. The earlier 831/638
split describes the older reader and is not the compatibility count for this
policy. Final counts and a per-recording report will be added after completion.
Metadata acceptance is distinct from real video decoding, scene viability,
physical calibration accuracy and privacy performance.

Metadata downloads are retained on the attached disk. Parsing is sequential
under a 6 GB task budget with a 5 GB RSS stop guard. Temporary extracted images
use a native filesystem cache through the existing runtime hook.
