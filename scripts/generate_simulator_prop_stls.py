#!/usr/bin/env python3
"""Generate small, reproducible STL props for the LuxoPi simulator scene."""

from pathlib import Path
import math


OUT = Path(__file__).parents[1] / "src/luxo_behaviors/luxo_behaviors/assets/simulator_props"


def facets(vertices, faces):
    for face in faces:
        a, b, c = (vertices[index] for index in face)
        ab = tuple(b[i] - a[i] for i in range(3))
        ac = tuple(c[i] - a[i] for i in range(3))
        normal = (
            ab[1] * ac[2] - ab[2] * ac[1],
            ab[2] * ac[0] - ab[0] * ac[2],
            ab[0] * ac[1] - ab[1] * ac[0],
        )
        norm = math.sqrt(sum(value * value for value in normal)) or 1.0
        normal = tuple(value / norm for value in normal)
        yield normal, (a, b, c)


def write_stl(name, vertices, faces):
    lines = [f"solid {name}"]
    for normal, triangle in facets(vertices, faces):
        lines.append("  facet normal " + " ".join(f"{value:.7g}" for value in normal))
        lines.append("    outer loop")
        lines.extend("      vertex " + " ".join(f"{value:.7g}" for value in point) for point in triangle)
        lines.extend(("    endloop", "  endfacet"))
    lines.append(f"endsolid {name}")
    (OUT / f"{name}.stl").write_text("\n".join(lines) + "\n", encoding="ascii")


def box(name, sx, sy, sz):
    vertices = [(x * sx / 2, y * sy / 2, z * sz / 2) for x, y, z in (
        (-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),
        (-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1),
    )]
    faces = [(0,2,1),(0,3,2),(4,5,6),(4,6,7),(0,1,5),(0,5,4),
             (1,2,6),(1,6,5),(2,3,7),(2,7,6),(3,0,4),(3,4,7)]
    write_stl(name, vertices, faces)


def cylinder(name, radius, height, sides=12, cone=False, noisy=False):
    vertices = []
    for ring, z in enumerate((-height / 2, height / 2)):
        scale = (1.0 if ring == 0 else (0.05 if cone else 1.0))
        for index in range(sides):
            angle = 2 * math.pi * index / sides
            radial = radius * scale * (1 + 0.16 * math.sin(index * 2.7) if noisy else 1)
            vertices.append((radial * math.cos(angle), radial * math.sin(angle), z))
    faces = []
    for index in range(sides):
        following = (index + 1) % sides
        faces.extend(((index, following, sides + following), (index, sides + following, sides + index)))
        faces.extend(((0, following, index), (sides, sides + index, sides + following)))
    write_stl(name, vertices, faces)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    box("crate", 0.12, 0.10, 0.10)
    box("wedge", 0.15, 0.12, 0.09)
    cylinder("can", 0.045, 0.14)
    cylinder("cone", 0.065, 0.15, cone=True)
    cylinder("rock", 0.085, 0.11, sides=9, noisy=True)


if __name__ == "__main__":
    main()
