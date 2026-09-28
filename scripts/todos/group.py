#!/usr/bin/env python3
"""Deterministic grouping and wave planning for the todo sweep (spec §7).

Groups: todos whose predicted files overlap (transitively) become one group --
one worker, one PR. Tiny todos in the same top-level module are bundled, at
most MAX_BUNDLE per group. Verify-only todos always stand alone.

Waves: at most `workers` groups each. Two waves overlap in time (wave N is in
review/land while wave N+1 executes), so a lane held in wave N cannot be held
in wave N+1, and a group whose dependency is in wave N cannot start before
wave N+2 (its worktree is cut from origin/main, which has the dependency only
after it merges). An empty wave means "wait for the wave two back to merge".
"""

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
    tick its Finding Status and race its -COMPLETED rename."""
    doc = todo.get("source_review")
    return {f"review:{doc}"} if doc else set()


def lane_doc(lane):
    if lane.startswith("review:"):
        return f"{lane[len('review:'):]} (its Finding Status and -COMPLETED rename)"
    return LANE_DOC[lane]


def _rank(todo):
    p = todo["priority"]
    return (PRIORITIES.index(p) if p in PRIORITIES else len(PRIORITIES), todo["id"])


def _components(todos):
    """Union-find over predicted files: todos that share a file (transitively)."""
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
            if path in owner:
                parent[find(todo["id"])] = find(owner[path])
            else:
                owner[path] = todo["id"]

    components = {}
    for todo in todos:
        components.setdefault(find(todo["id"]), []).append(todo)
    return list(components.values())


def build_groups(todos, solo=frozenset()):
    """Groups of todo ids. A todo in `solo` is never bundled with other tiny todos: one already
    known to be unschedulable (so it cannot take its bundle-mates down with it), or one with an
    in-plan dependency edge (so bundling cannot invent a cycle between bundles, PR #861 B-2)."""
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
    one PR -- until none is left (todo 468). A cycle among the todos themselves is refused earlier."""
    while True:
        gid_of = {i: n for n, ids in enumerate(grouped) for i in ids}
        deps = {n: {gid_of[d] for i in ids for d in by_id[i].get("dependencies", []) if d in gid_of} - {n}
                for n, ids in enumerate(grouped)}
        cycle = _find_cycle(deps)
        if not cycle:
            return grouped
        on = set(cycle)
        merged = sorted((i for n in on for i in grouped[n]), key=lambda i: _rank(by_id[i]))
        grouped = sorted([ids for n, ids in enumerate(grouped) if n not in on] + [merged],
                         key=lambda ids: _rank(by_id[ids[0]]))


def _held(todos, open_ids):
    """Todos that cannot run in this plan, decided per todo BEFORE any bundling (final
    review I4): a dependency on an open todo outside this plan, a file shared with such a
    todo (the same union-find group), or a dependency on another held todo."""
    by_id = {t["id"]: t for t in todos}
    held = {t["id"] for t in todos
            if any(dep not in by_id and dep in open_ids for dep in t.get("dependencies", []))}
    comp_of = {t["id"]: n for n, members in enumerate(_components(todos)) for t in members}
    changed = True
    while changed:
        changed = False
        bad = {comp_of[i] for i in held}
        for t in todos:
            if t["id"] not in held and (comp_of[t["id"]] in bad
                                        or any(dep in held for dep in t.get("dependencies", []))):
                held.add(t["id"])
                changed = True
    return held


def plan(todos, open_ids, workers):
    by_id = {t["id"]: t for t in todos}
    # PR #861 B-2: bundles hold only xs todos with no dependency edge inside this plan, in or out.
    # A bundle then has no group deps at all, so it can never sit on a cycle; a real cycle
    # among the todos themselves is refused below, before any grouping.
    linked = {end for t in todos for dep in t.get("dependencies", []) if dep in by_id and dep != t["id"]
              for end in (t["id"], dep)}
    todo_cycle = _find_cycle({t["id"]: {d for d in t.get("dependencies", []) if d in by_id and d != t["id"]}
                              for t in todos})
    if todo_cycle:
        raise CycleError("dependency cycle: " + " -> ".join(todo_cycle))
    grouped = _merge_cycles(build_groups(todos, solo=_held(todos, open_ids) | linked), by_id)
    gids = [f"g{n}" for n in range(1, len(grouped) + 1)]
    gid_of = {todo_id: gid for gid, ids in zip(gids, grouped) for todo_id in ids}
    lanes = {gid: sorted(set().union(*(lanes_for(by_id[i]["triage"]) | review_lane(by_id[i]) for i in ids)))
             for gid, ids in zip(gids, grouped)}
    deps = {gid: set() for gid in gids}
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
        previous = set().union(*(lanes[g] for g in waves[-1])) if waves else set()
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
        "unschedulable": unschedulable,
    }
