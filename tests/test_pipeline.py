"""The pipeline must rebuild byte-identical files from the same seed."""
import hashlib
from pathlib import Path

import pipeline

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
FILES = ["equities.csv", "yield_curves.csv", "fx_rates.csv", "trades.csv", "valuations.csv"]


def checksums():
    return {name: hashlib.md5((DATA_DIR / name).read_bytes()).hexdigest() for name in FILES}


def test_pipeline_is_deterministic():
    before = checksums()
    pipeline.run(skip_db=True)
    assert checksums() == before
