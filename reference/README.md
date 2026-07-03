# reference/

Small, **committed** reference tables (unlike `data/`, which is gitignored). Hand-maintained
overrides and lookups the pipeline reads.

| File | Purpose |
|---|---|
| `pfr_id_overrides.csv` | Manual `pfr_id,gsis_id` fixes for PFR players the automatic crosswalk misses (0.3). Unmatched ids are logged to `data/raw/pfr/unmatched_pfr_ids.csv` — copy the genuine ones here with the correct `gsis_id`. |
