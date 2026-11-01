# segment

SAM 3.1 segmentation for stills and for frames sampled from short clips. Output per frame: mask, mask area, mask centroid, edge-contact flags. Each sampled frame is segmented and judged on its own. No identity is tracked across frames, and nothing in this module claims otherwise.
