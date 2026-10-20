"""Shortest mesh routes and a Manhattan minimax rendezvous with explicit ties."""

from itertools import product


def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def nodes(side):
    return list(product(range(side), repeat=2))


def xy_path(source, destination):
    path = [source]
    x, y = source
    while x != destination[0]:
        x += 1 if destination[0] > x else -1
        path.append((x, y))
    while y != destination[1]:
        y += 1 if destination[1] > y else -1
        path.append((x, y))
    return path


def geodesic_meetings(source, destination, side):
    distance = manhattan(source, destination)
    return [m for m in nodes(side) if manhattan(source, m) + manhattan(destination, m) == distance]


def minimax_meeting(source, destination, side):
    return min(geodesic_meetings(source, destination, side),
               key=lambda m: (max(manhattan(source, m), manhattan(destination, m)),
                              abs(manhattan(source, m) - manhattan(destination, m)), m))


def paper_meeting(source, destination):
    return ((source[0] + destination[0]) // 2, (source[1] + destination[1]) // 2)


def edge_key(a, b):
    if manhattan(a, b) != 1:
        raise ValueError("Quantum links connect adjacent cores only")
    return tuple(sorted((a, b)))


def mesh_edges(side):
    return sorted({edge_key(a, b) for a in nodes(side) for b in nodes(side) if manhattan(a, b) == 1})
