#!/usr/bin/env python3
"""Deterministic grouping and wave planning for the todo sweep (spec §7).

Groups: todos whose predicted files overlap (transitively) become one group --
one worker, one PR. A lane file (LANE_FILES) joins no group: two todos that
share only settings.py are two groups, and its lane keeps them two waves apart
(todo 491). Tiny todos in the same top-level module are bundled, at most
MAX_BUNDLE per group. Verify-only todos always stand alone. A todo that waits
on an open todo outside the plan is held before grouping, with every todo that
depends on it; a todo that only shares a file with it is planned without it.

Waves: at most `workers` groups each. Two waves overlap in time (wave N is in
review/land while wave N+1 executes), so a lane held in wave N cannot be held
in wave N+1, and a group whose dependency is in wave N cannot start before
wave N+2 (its worktree is cut from origin/main, which has the dependency only
after it merges). An empty wave means "wait for the wave two back to merge".
"""

import posixpath
import re

PRIORITIES = ["p1", "p2", "p3", "p4"]
LANE_FILES = {
    "backend/plant_community_backend/settings.py": "settings",
    ".secrets.baseline": "secrets-baseline",
}
DEPS_RE = re.compile(r"(?:^|/)(?:requirements[^/]*\.txt|package(?:-lock)?\.json|pubspec\.(?:yaml|lock))$")
LANE_DOC = {
    "settings": "backend/plant_community_backend/settings.py",
    "secrets-baseline": ".secrets.baseline",
    "e2e": "Playwright, or anything served on :5174 / :8000",
    "deps": "dependency manifests (requirements*.txt, package*.json, pubspec.*) and their installed environments",
}
MAX_BUNDLE = 3


class CycleError(Exception):
    pass


def lanes_for(record):
    files = record.get("predicted_files", [])
    lanes = {LANE_FILES[f] for f in files if f in LANE_FILES}
    if record.get("needs_e2e"):
        lanes.add("e2e")
    if any(DEPS_RE.search(f) for f in files):
        lanes.add("deps")
    return lanes


def review_lane(todo):
    """A review doc is a lane (todo 468): two groups converted from one `docs/reviews/*.md` both
    tick its Finding Status and race its -COMPLETED rename. Any other source_review (an archived
    todo, "PR #812") is one Land never touches, so it is no lane (PR #869 round 1)."""
    doc = posixpath.normpath(str(todo["source_review"])) if todo.get("source_review") else ""
    return {f"review:{doc}"} if doc.startswith("docs/reviews/") and doc.endswith(".md") else set()


def lane_doc(lane):
    if lane.startswith("review:"):
        return f"{lane[len('review:'):]} (its Finding Status and -COMPLETED rename)"
    return LANE_DOC[lane]


def _rank(todo):
    p = todo["priority"]
    return (PRIORITIES.index(p) if p in PRIORITIES else len(PRIORITIES), todo["id"])


def _components(todos, lane_files=False):
    """Union-find over predicted files: todos that share a file (transitively).

    A lane file joins nothing (todo 491): its lane already serialises the groups that hold it, and in the
    2026-09-28 run settings.py chained 18 todos into one group. lane_files=True unions on it as well, for
    plan()'s cycle check only: a cycle between todos that share only a lane file is still refused for
    those todos (todo 474), not raised for the whole plan."""
    todos = sorted(todos, key=_rank)
    parent = {t["id"]: t["id"] for t in todos}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    owner = {}
    for todo in todos:
        if todo.get("verify_only"):
            continue
        for path in todo["triage"]["predicted_files"]:
            if path in LANE_FILES and not lane_files:
                continue
            if path in owner:
                parent[find(todo["id"])] = find(owner[path])
            else:
                owner[path] = todo["id"]

    components = {}
    for todo in todos:
        components.setdefault(find(todo["id"]), []).append(todo)
    return list(components.values())


def build_groups(todos, solo=frozenset()):
    """Groups of todo ids. A todo in `solo` is never bundled with other tiny todos: one with an
    in-plan dependency edge (so bundling cannot invent a cycle between bundles, PR #861 B-2). A held
    todo never gets here: plan() refuses it before grouping (todo 491)."""
    groups, tiny = [], {}
    for members in _components(todos):
        only = members[0]
        if (len(members) == 1 and only["triage"]["size"] == "xs" and not only.get("verify_only")
                and only["id"] not in solo):
            files = only["triage"]["predicted_files"]
            tiny.setdefault(files[0].split("/", 1)[0] if files else "misc", []).append(only)
        else:
            groups.append(members)
    for members in tiny.values():
        groups.extend(members[i:i + MAX_BUNDLE] for i in range(0, len(members), MAX_BUNDLE))

    groups = [sorted(g, key=_rank) for g in groups]
    groups.sort(key=lambda g: _rank(g[0]))
    return [[t["id"] for t in g] for g in groups]


def _find_cycle(deps):
    color, stack = {}, []

    def visit(node):
        color[node] = "grey"
        stack.append(node)
        for nxt in sorted(deps[node]):
            if color.get(nxt) == "grey":
                return stack[stack.index(nxt):] + [nxt]
            if nxt not in color:
                found = visit(nxt)
                if found:
                    return found
        stack.pop()
        color[node] = "black"
        return None

    for node in sorted(deps):
        if node not in color:
            found = visit(node)
            if found:
                return found
    return None


def _merge_cycles(grouped, by_id):
    """Todos that share a file are one group, so an acyclic chain through another group (B -> C -> A,
    A and B sharing a file) is still a group cycle. Every group on one becomes one group -- one worker,
    one PR -- until none is left (todo 468). A cycle among the todos themselves is refused earlier.

    Returns (grouped, stuck). A verify-only todo is never merged into a code group, where its brief would
    lose "verify only" (todo 474): a group cycle through one stops merging, and `stuck` names the todos on
    it, for plan() to refuse. Otherwise stuck is empty."""
    while True:
        gid_of = {i: n for n, ids in enumerate(grouped) for i in ids}
        deps = {n: {gid_of[d] for i in ids for d in by_id[i].get("dependencies", []) if d in gid_of} - {n}
                for n, ids in enumerate(grouped)}
        cycle = _find_cycle(deps)
        if not cycle:
            return grouped, []
        on = set(cycle)
        if any(by_id[i].get("verify_only") for n in on for i in grouped[n]):
            return grouped, sorted((i for n in on for i in grouped[n]), key=lambda i: _rank(by_id[i]))
        merged = sorted((i for n in on for i in grouped[n]), key=lambda i: _rank(by_id[i]))
        grouped = sorted([ids for n, ids in enumerate(grouped) if n not in on] + [merged],
                         key=lambda ids: _rank(by_id[ids[0]]))


def _refuse(refused, todos, ids, reason):
    """Refuse ids with reason, and every todo that depends on one of them, directly or not."""
    for todo_id in ids:
        refused.setdefault(todo_id, reason)
    changed = True
    while changed:
        changed = False
        for todo in todos:
            dep = next((d for d in todo.get("dependencies", []) if d in refused), None)
            if todo["id"] not in refused and dep:
                refused[todo["id"]] = f"depends on todo {dep}, which is refused: {refused[dep]}"[:300]
                changed = True


def _held(todos, open_ids):
    """{todo id: reason} for each todo that depends on an open todo outside this plan, decided per todo
    BEFORE any grouping (final review I4). plan() refuses each with _refuse, which also refuses every todo
    that depends on it, directly or not. A hold follows dependency edges only, never a shared file (todo
    491): a held todo never joins a group, so the todos it shares a file with plan without it. Holding its
    whole union-find group made 23 of 52 todos unschedulable in the 2026-09-28 run."""
    ids = {t["id"] for t in todos}
    held = {}
    for t in todos:
        dep = next((d for d in t.get("dependencies", []) if d not in ids and d in open_ids), None)
        if dep:
            held[t["id"]] = f"depends on open todo {dep}, which is not ready in this run"
    return held


def plan(todos, open_ids, workers, busy_lanes=frozenset()):
    """busy_lanes: lanes the wave just before this plan's first wave holds (a retry's groups are
    appended after the run's last wave, which may still be running; PR #869 round 1).

    Todo 474: a cycle that cannot be planned is refused for its own todos (and their dependents) only,
    never for the whole plan: a dependency cycle between todos that share a file (one group), and a group
    cycle through a verify-only todo, which must not be merged. Any other todo cycle raises CycleError.

    Todo 491: a todo that depends on an open todo outside this plan is refused before grouping, with every
    todo that depends on it (_held). One that only shares a file with it is planned without it."""
    refused = {}
    while True:
        live = [t for t in todos if t["id"] not in refused]
        by_id = {t["id"]: t for t in live}
        # PR #861 B-2: bundles hold only xs todos with no dependency edge inside this plan, in or out.
        # A bundle then has no group deps at all, so it can never sit on a cycle; a real cycle
        # among the todos themselves is refused below, before any grouping.
        linked = {end for t in live for dep in t.get("dependencies", []) if dep in by_id and dep != t["id"]
                  for end in (t["id"], dep)}
        todo_cycle = _find_cycle({t["id"]: {d for d in t.get("dependencies", []) if d in by_id and d != t["id"]}
                                  for t in live})
        if todo_cycle:
            comp = {t["id"]: n for n, members in enumerate(_components(live, lane_files=True)) for t in members}
            if len({comp[i] for i in todo_cycle}) > 1:
                raise CycleError("dependency cycle: " + " -> ".join(todo_cycle))
            _refuse(refused, todos, todo_cycle[:-1], "dependency cycle between todos that share a file: "
                    + " -> ".join(todo_cycle))
            continue
        held = _held(live, open_ids)
        if held:
            for todo_id, reason in held.items():
                _refuse(refused, todos, [todo_id], reason)
            continue
        grouped, stuck = _merge_cycles(build_groups(live, solo=linked), by_id)
        if not stuck:
            break
        only = [i for i in stuck if by_id[i].get("verify_only")]
        _refuse(refused, todos, stuck, f"dependency cycle through verify-only todo {', '.join(only)}: planning it "
                f"would merge it into a code group ({', '.join(stuck)})")
    gids = [f"g{n}" for n in range(1, len(grouped) + 1)]
    gid_of = {todo_id: gid for gid, ids in zip(gids, grouped) for todo_id in ids}
    lanes = {gid: sorted(set().union(*(lanes_for(by_id[i]["triage"]) | review_lane(by_id[i]) for i in ids)))
             for gid, ids in zip(gids, grouped)}
    deps = {gid: set() for gid in gids}
    # Todo 491: _held refused every todo that waits outside this plan before grouping, so this guard should
    # never fire. It stays so that a group with such a member is still never placed.
    unschedulable = {}
    for gid, ids in zip(gids, grouped):
        for todo_id in ids:
            for dep in by_id[todo_id].get("dependencies", []):
                if dep in gid_of:
                    if gid_of[dep] != gid:
                        deps[gid].add(gid_of[dep])
                elif dep in open_ids:
                    unschedulable[todo_id] = f"depends on open todo {dep}, which is not ready in this run"

    blocked_groups = {gid_of[i] for i in unschedulable}
    changed = True
    while changed:
        changed = False
        for gid in gids:
            if gid not in blocked_groups and deps[gid] & blocked_groups:
                blocked_groups.add(gid)
                changed = True
    for gid in blocked_groups:
        for todo_id in grouped[gids.index(gid)]:
            unschedulable.setdefault(todo_id, "depends on an unschedulable group")

    placed, waves = {}, []
    pending = [g for g in gids if g not in blocked_groups]
    empty_run = 0
    while pending:
        wave_no = len(waves)
        previous = set().union(*(lanes[g] for g in waves[-1])) if waves else set(busy_lanes)
        chosen, used = [], set()
        for gid in pending:
            if len(chosen) == workers:
                break
            if any(placed.get(dep, wave_no) > wave_no - 2 for dep in deps[gid]):
                continue
            if set(lanes[gid]) & (used | previous):
                continue
            chosen.append(gid)
            used |= set(lanes[gid])
        empty_run = empty_run + 1 if not chosen else 0
        if empty_run > 2:
            raise RuntimeError(f"wave planning made no progress; pending={pending}")
        for gid in chosen:
            placed[gid] = wave_no
            pending.remove(gid)
        waves.append(chosen)

    return {
        "groups": {gid: {"ids": ids, "lanes": lanes[gid], "deps": sorted(deps[gid])}
                   for gid, ids in zip(gids, grouped) if gid not in blocked_groups},
        "waves": waves,
        "unschedulable": {**refused, **unschedulable},
    }
