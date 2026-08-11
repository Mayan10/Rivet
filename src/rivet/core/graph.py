"""Expands room requirements into individual room nodes and builds the
adjacency graph the layout engine plans against.
"""

from __future__ import annotations

import itertools
from collections import defaultdict
from dataclasses import dataclass

import networkx as nx

from .models import RoomRequirement, RoomType
from .rules import is_avoided_adjacency, is_preferred_adjacency, rule_for

# Room types eligible to receive an auto-generated attached bathroom.
_CAN_HAVE_ENSUITE = frozenset({RoomType.MASTER_BEDROOM, RoomType.BEDROOM})


@dataclass
class RoomNode:
    """A single room instance to be placed, before it has geometry."""

    id: str
    room_type: RoomType
    label: str
    target_area_sqm: float
    min_width_m: float
    max_aspect_ratio: float
    exterior_wall_required: bool
    ensuite_of: str | None = None  # id of the bedroom this bathroom serves


def _default_label(room_type: RoomType) -> str:
    return room_type.value.replace("_", " ").title()


def expand_room_requirements(rooms: list[RoomRequirement]) -> list[RoomNode]:
    """Turn user-facing (type, count) requirements into concrete room nodes,
    auto-creating en-suite bathrooms where requested.
    """
    nodes: list[RoomNode] = []
    type_counters: dict[RoomType, int] = defaultdict(int)

    def _next_id(room_type: RoomType) -> tuple[str, int]:
        type_counters[room_type] += 1
        idx = type_counters[room_type]
        return f"{room_type.value}_{idx}", idx

    for req in rooms:
        rule = rule_for(req.room_type)
        area = req.target_area_sqm if req.target_area_sqm is not None else rule.default_area_sqm
        for _ in range(req.count):
            node_id, idx = _next_id(req.room_type)
            base_label = req.label or _default_label(req.room_type)
            label = f"{base_label} {idx}" if req.count > 1 else base_label
            nodes.append(
                RoomNode(
                    id=node_id,
                    room_type=req.room_type,
                    label=label,
                    target_area_sqm=area,
                    min_width_m=rule.min_width_m,
                    max_aspect_ratio=rule.max_aspect_ratio,
                    exterior_wall_required=rule.exterior_wall_required,
                )
            )

            if req.attached_bathroom and req.room_type in _CAN_HAVE_ENSUITE:
                bath_rule = rule_for(RoomType.BATHROOM)
                bath_id, _ = _next_id(RoomType.BATHROOM)
                nodes.append(
                    RoomNode(
                        id=bath_id,
                        room_type=RoomType.BATHROOM,
                        label=f"{label} Ensuite",
                        target_area_sqm=bath_rule.default_area_sqm,
                        min_width_m=bath_rule.min_width_m,
                        max_aspect_ratio=bath_rule.max_aspect_ratio,
                        exterior_wall_required=False,
                        ensuite_of=node_id,
                    )
                )

    return nodes


def build_adjacency_graph(nodes: list[RoomNode]) -> nx.Graph:
    """Build a weighted graph of desired adjacencies between room nodes.

    Edge weight encodes how strongly two rooms should share a wall:
    2.0 = required (en-suite pairing), 1.0 = preferred (rulebook), and no
    edge at all for unrelated rooms. Pairs the rulebook marks as
    ``ADJACENCY_AVOID`` are never given an edge — the scorer penalizes them
    directly if the layout search accidentally places them together.
    """
    g = nx.Graph()
    for n in nodes:
        g.add_node(n.id, data=n)

    for a, b in itertools.combinations(nodes, 2):
        if is_avoided_adjacency(a.room_type, b.room_type):
            continue
        if a.ensuite_of == b.id or b.ensuite_of == a.id:
            g.add_edge(a.id, b.id, weight=2.0, required=True)
        elif a.ensuite_of is not None or b.ensuite_of is not None:
            # An en-suite bathroom is only reachable through its own bedroom
            # (the required edge above) — it doesn't also open onto the
            # corridor or get a second preferred pairing.
            continue
        elif is_preferred_adjacency(a.room_type, b.room_type):
            g.add_edge(a.id, b.id, weight=1.0, required=False)

    return g
