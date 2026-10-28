"""Small-input oracle for neighborhood cores of strongly induced hypergraphs.

An edge survives in H[S] only when *all* of its vertices remain in S.
Neighbors are distinct co-members, not incident-edge counts. This deliberately
simple fixed-point implementation is for correctness checks, not benchmarking.
"""

from pathlib import Path


def read_hyp(path):
    """Read comma-separated integer vertex IDs, one hyperedge per line."""
    edges = []
    with Path(path).open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            line = line.strip()
            if not line:
                continue
            try:
                edge = frozenset(int(value.strip()) for value in line.split(","))
            except ValueError as error:
                raise ValueError("Invalid vertex ID on line " + str(line_number)) from error
            edges.append(edge)
    return edges


def neighborhood_sizes(edges, active):
    neighbors = {vertex: set() for vertex in active}
    for edge in edges:
        if edge <= active:
            for vertex in edge:
                neighbors[vertex].update(edge - {vertex})
    return {vertex: len(adjacent) for vertex, adjacent in neighbors.items()}


def core_numbers(edges, vertices=None, max_vertices=128):
    edges = tuple(frozenset(edge) for edge in edges)
    edge_vertices = set().union(*edges) if edges else set()
    all_vertices = edge_vertices if vertices is None else set(vertices)
    if not edge_vertices <= all_vertices:
        raise ValueError("An edge references a vertex absent from the vertex set")
    if len(all_vertices) > max_vertices:
        raise ValueError("Oracle input exceeds the small-graph size limit")
    cores = {vertex: 0 for vertex in all_vertices}
    active = set(all_vertices)
    for threshold in range(1, len(all_vertices)):
        while active:
            sizes = neighborhood_sizes(edges, active)
            removed = {vertex for vertex, size in sizes.items() if size < threshold}
            if not removed:
                break
            active.difference_update(removed)
        if not active:
            break
        for vertex in active:
            cores[vertex] = threshold
    return cores
