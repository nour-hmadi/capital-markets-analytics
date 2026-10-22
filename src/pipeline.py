"""Run the whole project end to end: market data -> trades -> valuation -> database."""
import argparse
import logging
import time

import export_xml
import generate_data
import load_db
import trades
import valuation

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-5s  %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("pipeline")

STEPS = [
    ("Generate market data", generate_data.main),
    ("Book trades", trades.main),
    ("Export XML trade messages", export_xml.main),
    ("Value the book", valuation.main),
    ("Load the database", load_db.main),
]


def run(skip_db=False):
    for name, step in STEPS:
        if skip_db and step is load_db.main:
            log.info("Skipping: %s", name)
            continue
        log.info("Starting: %s", name)
        start = time.perf_counter()
        try:
            step()
        except Exception:
            log.error("Failed: %s. Stopping the pipeline.", name)   # fail fast
            raise
        log.info("Finished: %s (%.1fs)", name, time.perf_counter() - start)
    log.info("Pipeline complete")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-db", action="store_true",
                        help="run everything except the database load")
    run(skip_db=parser.parse_args().skip_db)


if __name__ == "__main__":
    main()
