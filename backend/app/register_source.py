"""Operator-only registry CLI. New sources always start disabled and unreviewed."""

import argparse

from app.db import SessionLocal
from app.source_registry import add_source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--feed-url", required=True)
    parser.add_argument("--terms-url", required=True)
    args = parser.parse_args()
    with SessionLocal() as session:
        source = add_source(session, args.name, args.feed_url, args.terms_url)
        print(f"Registered source id={source.id}; disabled pending rights review.")


if __name__ == "__main__":
    main()
