from app.simulation.interfaces import BuildingFootprint

# the 2x2 building "c" has every edge-adjacent perimeter tile covered by another building
BLOCKED = [
    BuildingFootprint("c", 10, 10, 2, 2),
    BuildingFootprint("t", 10, 8, 2, 2),
    BuildingFootprint("r", 12, 10, 2, 2),
    BuildingFootprint("b", 10, 12, 2, 2),
    BuildingFootprint("l", 8, 10, 2, 2),
]
