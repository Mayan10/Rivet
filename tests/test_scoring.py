import networkx as nx

from rivet.core.graph import RoomNode
from rivet.core.models import Orientation, PlotSpec, Rect
from rivet.core.scoring import evaluate

PLOT = PlotSpec(width_m=10.0, length_m=10.0, entrance=Orientation.NORTH)
BUILDABLE = Rect(x=1.0, y=1.0, w=8.0, h=8.0)


def _node(id_, room_type, area, min_width, aspect=2.2, exterior=False, ensuite_of=None):
    return RoomNode(
        id=id_,
        room_type=room_type,
        label=id_,
        target_area_sqm=area,
        min_width_m=min_width,
        max_aspect_ratio=aspect,
        exterior_wall_required=exterior,
        ensuite_of=ensuite_of,
    )


def test_min_width_violation_is_penalized():
    from rivet.core.models import RoomType

    node = _node("bedroom_1", RoomType.BEDROOM, area=10.0, min_width=2.4)
    wide_enough = {"bedroom_1": Rect(1, 1, 4.0, 2.5)}
    too_narrow = {"bedroom_1": Rect(1, 1, 1.0, 10.0)}
    graph = nx.Graph()
    graph.add_node("bedroom_1", data=node)

    good = evaluate([node], wide_enough, BUILDABLE, PLOT, graph)
    bad = evaluate([node], too_narrow, BUILDABLE, PLOT, graph)

    assert good.breakdown["min_width"] == 0.0
    assert bad.breakdown["min_width"] > 0.0
    assert bad.score < good.score


def test_avoided_adjacency_is_penalized_even_without_a_graph_edge():
    from rivet.core.models import RoomType

    kitchen = _node("kitchen_1", RoomType.KITCHEN, area=6.0, min_width=1.8)
    bathroom = _node("bathroom_1", RoomType.BATHROOM, area=3.0, min_width=1.2)
    graph = nx.Graph()
    graph.add_node("kitchen_1", data=kitchen)
    graph.add_node("bathroom_1", data=bathroom)  # deliberately no edge

    adjacent = {"kitchen_1": Rect(1, 1, 3.0, 3.0), "bathroom_1": Rect(4, 1, 2.0, 3.0)}
    separated = {"kitchen_1": Rect(1, 1, 3.0, 3.0), "bathroom_1": Rect(1, 5, 2.0, 3.0)}

    touching = evaluate([kitchen, bathroom], adjacent, BUILDABLE, PLOT, graph)
    apart = evaluate([kitchen, bathroom], separated, BUILDABLE, PLOT, graph)

    assert touching.breakdown["adjacency_avoided"] > 0.0
    assert apart.breakdown["adjacency_avoided"] == 0.0
    assert apart.score > touching.score


def test_required_edge_penalized_more_than_preferred_when_both_missed():
    from rivet.core.models import RoomType

    bedroom = _node("bedroom_1", RoomType.BEDROOM, area=10.0, min_width=2.4)
    ensuite = _node("bath_1", RoomType.BATHROOM, area=3.0, min_width=1.2, ensuite_of="bedroom_1")
    kitchen = _node("kitchen_1", RoomType.KITCHEN, area=6.0, min_width=1.8)
    dining = _node("dining_1", RoomType.DINING_ROOM, area=7.0, min_width=2.0)

    required_graph = nx.Graph()
    required_graph.add_edge("bedroom_1", "bath_1", weight=2.0, required=True)

    preferred_graph = nx.Graph()
    preferred_graph.add_edge("kitchen_1", "dining_1", weight=1.0, required=False)

    # Rects placed so neither pair actually touches.
    rects_required = {"bedroom_1": Rect(0, 0, 4, 4), "bath_1": Rect(4, 6, 2, 2)}
    rects_preferred = {"kitchen_1": Rect(0, 0, 3, 3), "dining_1": Rect(4, 6, 3, 3)}

    missed_required = evaluate([bedroom, ensuite], rects_required, BUILDABLE, PLOT, required_graph)
    missed_preferred = evaluate([kitchen, dining], rects_preferred, BUILDABLE, PLOT, preferred_graph)

    assert missed_required.breakdown["adjacency_missed"] > missed_preferred.breakdown["adjacency_missed"]


def test_scoring_ranks_a_good_layout_above_a_bad_one():
    """A layout that respects the rulebook (en-suite touches its bedroom,
    kitchen and bathroom stay apart) must outscore one that violates both,
    with every other dimension (areas, widths) held identical.
    """
    from rivet.core.models import RoomType

    bedroom = _node("bedroom_1", RoomType.BEDROOM, area=10.0, min_width=2.4)
    ensuite = _node("bath_1", RoomType.BATHROOM, area=3.0, min_width=1.2, ensuite_of="bedroom_1")
    kitchen = _node("kitchen_1", RoomType.KITCHEN, area=6.0, min_width=1.8)
    bathroom = _node("bathroom_2", RoomType.BATHROOM, area=3.0, min_width=1.2)
    nodes = [bedroom, ensuite, kitchen, bathroom]

    graph = nx.Graph()
    for n in nodes:
        graph.add_node(n.id, data=n)
    graph.add_edge("bedroom_1", "bath_1", weight=2.0, required=True)

    good_rects = {
        "bedroom_1": Rect(1, 1, 4.0, 2.5),
        "bath_1": Rect(5, 1, 2.0, 1.5),  # touches bedroom_1's east wall
        "kitchen_1": Rect(1, 4, 3.0, 2.0),
        "bathroom_2": Rect(1, 7, 2.0, 1.5),  # far from kitchen_1
    }
    bad_rects = {
        "bedroom_1": Rect(1, 1, 4.0, 2.5),
        "bath_1": Rect(1, 7, 2.0, 1.5),  # nowhere near bedroom_1
        "kitchen_1": Rect(1, 4, 3.0, 2.0),
        "bathroom_2": Rect(4, 4, 2.0, 2.0),  # touches kitchen_1 -- avoided pair
    }

    good = evaluate(nodes, good_rects, BUILDABLE, PLOT, graph)
    bad = evaluate(nodes, bad_rects, BUILDABLE, PLOT, graph)

    assert good.score > bad.score
