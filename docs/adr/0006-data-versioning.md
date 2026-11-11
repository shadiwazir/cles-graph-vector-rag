# 0006. DVC for data versioning; stores are rebuildable [ob.1]

**Status:** accepted (remote: local for now)

**Context.** Code is in Git. Data (raw PDFs, extraction results, datasets, adapters) needs versions tied to code and models.

**Options.** Git LFS (poor for 10k+ files); DVC; lakeFS; MLflow dataset logging (metadata only).

**Decision.** DVC tracks raw PDFs, the extraction export, train/eval JSONL and adapters. Postgres and Neo4j contents are not versioned as data: they are rebuilt from raw data + extraction export + code + pack. `build_manifest` and MLflow runs record git commit and DVC hashes. Remote is a local folder now; DagsHub is evaluated before moving to the cloud (terms, limits, MLflow reachability from the GPU machine).

**Consequences.** The extraction export is the key asset (paid to produce). Needs a Git repository (`dvc init`).
