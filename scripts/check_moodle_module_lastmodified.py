"""Diagnostic script: check Moodle module timestamp availability.

This script uses the same timestamp extraction logic as
`src/loaders/moodle.py::compute_module_fingerprint()` and reports how often the
effective `lastmodified` timestamp resolves to 0.

Why:
  - In `compute_module_fingerprint()`, `lastmodified` falls back to 0 if:
      * contentsinfo.lastmodified is missing/None
      * and module contents have no valid timemodified values
      * or an exception occurs while reading these fields

Usage (PowerShell):
  poetry run python scripts/check_moodle_module_lastmodified.py --max-courses 5
  poetry run python scripts/check_moodle_module_lastmodified.py --course-id 123 --course-id 456

Requires the same env vars as the ingestion pipeline:
  - DATA_SOURCE_MOODLE_URL
  - DATA_SOURCE_MOODLE_TOKEN
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import Any, Iterable

from src.loaders.moodle import Moodle, compute_module_fingerprint


@dataclass(frozen=True)
class ModuleTimestampCheck:
    course_id: int
    topic_id: int | None
    module_id: int
    modname: str
    lastmodified: int
    reason: str
    fingerprint: str


def _safe_int(v: Any) -> int | None:
    try:
        if isinstance(v, bool):
            return None
        if isinstance(v, int):
            return v
        if isinstance(v, str) and v.isdigit():
            return int(v)
    except Exception:
        return None
    return None


def extract_lastmodified_like_fingerprint(module: Any) -> tuple[int, str]:
    """Re-implement the timestamp extraction part of compute_module_fingerprint().

    Returns (lastmodified, reason).
    """

    # 1) Prefer module.contentsinfo.lastmodified
    try:
        ci = getattr(module, "contentsinfo", None) or {}
        if isinstance(ci, dict):
            lm = _safe_int(ci.get("lastmodified"))
            if lm is not None:
                return lm, "contentsinfo.lastmodified"
    except Exception:
        # Mirrors compute_module_fingerprint: swallow exceptions and continue.
        pass

    # 2) Fallback: max(module.contents[].timemodified)
    try:
        contents = getattr(module, "contents", None) or []
        ts: list[int] = []
        for c in contents:
            v = getattr(c, "timemodified", None)
            if v is None and isinstance(c, dict):
                v = c.get("timemodified")
            vv = _safe_int(v)
            if vv is not None:
                ts.append(vv)
        if ts:
            return max(ts), "contents[].timemodified"
        return 0, "no_timestamp_fields"
    except Exception:
        return 0, "exception_in_contents_fallback"


def iter_course_ids(moodle: Moodle, *, explicit: list[int] | None, max_courses: int | None) -> Iterable[int]:
    if explicit:
        for cid in explicit:
            yield int(cid)
        return

    courses = moodle.get_courses()
    if max_courses is not None:
        courses = courses[: max(0, int(max_courses))]
    for c in courses:
        yield int(getattr(c, "id", 0) or 0)


def main() -> int:
    ap = argparse.ArgumentParser(description="Check Moodle module timestamp availability.")
    ap.add_argument("--course-id", action="append", type=int, help="Restrict to one or more course IDs")
    ap.add_argument("--max-courses", type=int, default=None, help="Limit number of courses (if --course-id not given)")
    ap.add_argument("--max-modules", type=int, default=None, help="Stop after N modules total")
    ap.add_argument(
        "--json",
        action="store_true",
        help="Output full results as JSON (otherwise prints a summary + a short table)",
    )
    args = ap.parse_args()

    moodle = Moodle()

    results: list[ModuleTimestampCheck] = []
    total_modules = 0

    for course_id in iter_course_ids(moodle, explicit=args.course_id, max_courses=args.max_courses):
        if course_id <= 0:
            continue

        topics = moodle.get_course_contents(course_id)
        for topic in topics or []:
            topic_id = getattr(topic, "id", None)
            for m in getattr(topic, "modules", None) or []:
                if m is None:
                    continue

                mid = int(getattr(m, "id", 0) or 0)
                if mid <= 0:
                    continue

                lastmodified, reason = extract_lastmodified_like_fingerprint(m)
                fp = compute_module_fingerprint(m)

                results.append(
                    ModuleTimestampCheck(
                        course_id=course_id,
                        topic_id=_safe_int(topic_id),
                        module_id=mid,
                        modname=str(getattr(m, "modname", "") or ""),
                        lastmodified=int(lastmodified),
                        reason=reason,
                        fingerprint=fp,
                    )
                )
                print(f"Checked course {course_id} module {mid}: lastmodified={lastmodified} reason={reason}")
                total_modules += 1
                if args.max_modules is not None and total_modules >= int(args.max_modules):
                    break
            if args.max_modules is not None and total_modules >= int(args.max_modules):
                break
        if args.max_modules is not None and total_modules >= int(args.max_modules):
            break

    if args.json:
        print(json.dumps([r.__dict__ for r in results], indent=2, ensure_ascii=False))
        return 0

    zeros = [r for r in results if r.lastmodified == 0]
    by_reason: dict[str, int] = {}
    for r in zeros:
        by_reason[r.reason] = by_reason.get(r.reason, 0) + 1

    print("== Moodle module lastmodified diagnostic ==")
    print(f"modules_total: {len(results)}")
    print(f"lastmodified_zero: {len(zeros)}")
    if results:
        print(f"lastmodified_zero_pct: {round(len(zeros) / len(results) * 100, 2)}")
    if by_reason:
        print("zero_reasons:")
        for k in sorted(by_reason.keys()):
            print(f"  - {k}: {by_reason[k]}")

    # Print a small sample of zeros so you can inspect course/module IDs.
    if zeros:
        print("\nSample lastmodified=0 modules (first 25):")
        print("course_id\ttopic_id\tmodule_id\tmodname\treason")
        for r in zeros[:25]:
            print(f"{r.course_id}\t{r.topic_id}\t{r.module_id}\t{r.modname}\t{r.reason}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

