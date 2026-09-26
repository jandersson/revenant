"""Refit what a mindstate bucket is worth from ;xp's history:  uv run python tools/experience_fit.py

Cuts history.db's per-minute `mindstate` rows into drain-only runs (per
character and skill: consecutive minutes, mindstate never rising, ended
at the first 0, a reading flat for eight minutes above 0 dropped as
stale, one REXP flag throughout, at least --min-buckets buckets) and
keeps the runs that drained at client/game/drain.py's fitted speed
(within --speed of it: a slower run was being fed). For each run the
bits gained (a rank n costs 200 + n) over the buckets drained, against
the Elanthipedia pool / 34 at the run's rank and mental stats, gives K
= that ratio * rank — the constant drain.BUCKET_K holds (8.35 on
2026-09-26, docs/experience.md "What a mindstate is worth"). Prints K
per tier and rank band and the runs outside the fitted range.

    --min-buckets N   the shortest run counted (5)
    --speed F         the drain-speed tolerance, as a fraction (0.15)
    --character NAME  one character only (all by default)
"""

import argparse
import os
import sqlite3
import statistics as st
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "client"))
from client.game import drain  # noqa: E402

GAP = 150  # seconds between rows still counted consecutive
STALE_MINUTES = 8


def _ts(text):
    return datetime.fromisoformat(text).timestamp()


def total_bits(rank, percent):
    return 200 * rank + rank * (rank - 1) // 2 + percent / 100 * drain.rank_cost(rank)


def load(connection, character=None):
    guild = dict(
        connection.execute(
            "select character_name, guild from character where guild is not null order by seq"
        ).fetchall()
    )
    stats = defaultdict(list)
    for at, name, stat, value in connection.execute(
        "select logged_at, character_name, stat, value from stats "
        "where stat in ('Intelligence', 'Discipline', 'Wisdom') order by seq"
    ):
        stats[name].append((_ts(at), stat, value))
    query = (
        "select logged_at, character_name, skill_name, rank, percent, mindstate, "
        "is_rexp from mindstate"
    )
    args = ()
    if character:
        query, args = query + " where character_name = ?", (character,)
    series = defaultdict(list)
    for at, name, skill, rank, percent, mind, rexp in connection.execute(
        query + " order by seq", args
    ):
        series[(name, skill)].append((_ts(at), rank, percent, mind, rexp or 0))
    return guild, stats, series


def stats_at(stats, name, when):
    """The latest Intelligence, Discipline and Wisdom at or before `when`
    (the earliest known when none precede it)."""
    known = {}
    for at, stat, value in stats.get(name, []):
        if at > when and len(known) == 3:
            break
        if at <= when or stat not in known:
            known[stat] = value
    return known if len(known) == 3 else None


def runs(guild, stats, series, min_buckets):
    found = []
    for (name, skill), points in series.items():
        g = guild.get(name)
        if not g or drain.placement(skill, g) is None:
            continue
        current = []

        def close(run):
            if len(run) < 3:
                return
            flat = run[0]
            for point in run[1:]:
                if point[3] != flat[3]:
                    flat = point
                elif point[3] > 0 and point[0] - flat[0] > STALE_MINUTES * 60:
                    return
            start, end = run[0], run[-1]
            drop = start[3] - end[3]
            if drop < min_buckets or len({p[4] for p in run}) != 1 or start[4]:
                return
            known = stats_at(stats, name, start[0])
            if not known:
                return
            rank = (start[1] + end[1] + (start[2] + end[2]) / 200) / 2
            found.append(
                {
                    "name": name,
                    "skill": skill,
                    "tier": drain.placement(skill, g),
                    "drain_tier": drain.drain_tier(skill, start[1], g),
                    "rank": rank,
                    "intelligence": known["Intelligence"],
                    "discipline": known["Discipline"],
                    "wisdom": known["Wisdom"],
                    "drop": drop,
                    "bits": total_bits(end[1], end[2]) - total_bits(start[1], start[2]),
                    "minutes": (end[0] - start[0]) / 60,
                }
            )

        for point in points:
            if current and (
                point[0] - current[-1][0] > GAP
                or point[3] > current[-1][3]
                or current[-1][3] == 0
            ):
                close(current)
                current = []
            current.append(point)
        close(current)
    return found


def clean(found, tolerance):
    kept = []
    for run in found:
        if run["minutes"] <= 0:
            continue
        pulses = run["minutes"] * 60 / drain.PULSE_SECONDS
        expected = drain.BUCKETS_PER_PULSE[run["drain_tier"]] * drain.wisdom_factor(
            run["wisdom"]
        )
        if abs(run["drop"] / pulses / expected - 1) <= tolerance:
            page = drain.pool_bits(
                run["tier"], run["rank"], run["intelligence"], run["discipline"]
            )
            run["k"] = run["bits"] / run["drop"] / (page / drain.BUCKETS) * run["rank"]
            kept.append(run)
    return kept


def report(kept):
    fitted = [r for r in kept if 10 <= r["rank"] < 100]
    print(f"clean drain runs: {len(kept)}, ranks 10-100: {len(fitted)}")
    if fitted:
        ks = sorted(r["k"] for r in fitted)
        print(
            f"K = {st.median(ks):.2f} (p25 {ks[len(ks) // 4]:.2f}, p75 {ks[3 * len(ks) // 4]:.2f});"
            f" drain.BUCKET_K = {drain.BUCKET_K}"
        )
    for tier in ("primary", "secondary", "tertiary"):
        sub = [r["k"] for r in fitted if r["tier"] == tier]
        if sub:
            print(f"  {tier:9s} n={len(sub):4d}  K {st.median(sub):.2f}")
    for low in range(10, 100, 20):
        sub = [r["k"] for r in fitted if low <= r["rank"] < low + 20]
        if sub:
            print(f"  ranks {low}-{low + 19}  n={len(sub):4d}  K {st.median(sub):.2f}")
    outside = [r for r in kept if not 10 <= r["rank"] < 100]
    if outside:
        print("outside ranks 10-100:")
        for r in sorted(outside, key=lambda r: (r["name"], r["rank"])):
            print(
                f"  {r['name']:10s} {r['skill']:16s} {r['tier']:9s} rank {r['rank']:6.1f}"
                f"  Int {r['intelligence']:3d}  {r['bits'] / r['drop']:5.1f} bits/bucket  K {r['k']:.1f}"
            )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--min-buckets", type=int, default=5)
    parser.add_argument("--speed", type=float, default=0.15)
    parser.add_argument("--character")
    args = parser.parse_args(argv)
    path = Path(
        os.path.expanduser(
            os.environ.get("REVENANT_HISTORY_DB", "~/.revenant/history.db")
        )
    )
    connection = sqlite3.connect(path)
    guild, stats, series = load(connection, args.character)
    report(clean(runs(guild, stats, series, args.min_buckets), args.speed))


if __name__ == "__main__":
    main()
