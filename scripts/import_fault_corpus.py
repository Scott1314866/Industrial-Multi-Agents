from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def import_corpus(source: Path) -> dict[str, object]:
    labels = [
        line.strip()
        for line in (source / "class.txt").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    labels_zh = [
        line.strip()
        for line in (source / "class_chinese.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    records: list[dict[str, object]] = []
    counts: Counter[str] = Counter()
    for split in ("train", "dev", "test"):
        for number, line in enumerate(
            (source / f"{split}.txt").read_text(encoding="utf-8").splitlines(), 1
        ):
            if not line.strip():
                continue
            text, raw_label = line.rsplit("\t", 1)
            label_id = int(raw_label)
            records.append(
                {
                    "id": f"{split}-{number:05d}",
                    "split": split,
                    "text": text.strip(),
                    "label": labels[label_id],
                    "label_zh": labels_zh[label_id],
                }
            )
            counts[labels[label_id]] += 1
    return {"version": 1, "labels": labels, "counts": counts, "records": records}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import the injection-molding fault corpus"
    )
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = import_corpus(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Imported {len(payload['records'])} records into {args.output}")


if __name__ == "__main__":
    main()
