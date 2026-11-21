from __future__ import annotations

Pt = tuple[float, float]


def side(a: Pt, b: Pt, p: Pt) -> float:
    """Signed area: >0 when p is on the 'in' side of a->b, <0 on the other side."""
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])


def _ccw(a: Pt, b: Pt, c: Pt) -> float:
    return (c[1] - a[1]) * (b[0] - a[0]) - (b[1] - a[1]) * (c[0] - a[0])


def segments_intersect(a: Pt, b: Pt, c: Pt, d: Pt) -> bool:
    d1, d2 = _ccw(a, b, c), _ccw(a, b, d)
    d3, d4 = _ccw(c, d, a), _ccw(c, d, b)
    return (d1 > 0) != (d2 > 0) and (d3 > 0) != (d4 > 0)


def crossing_direction(l1: Pt, l2: Pt, prev: Pt, curr: Pt) -> str | None:
    """Return 'in' / 'out' when the movement prev->curr crosses the SEGMENT l1-l2, else None."""
    s_prev, s_curr = side(l1, l2, prev), side(l1, l2, curr)
    if s_prev <= 0 < s_curr:
        direction = "in"
    elif s_prev >= 0 > s_curr:
        direction = "out"
    else:
        return None
    return direction if segments_intersect(l1, l2, prev, curr) else None


def point_in_polygon(pt: Pt, poly: list[Pt]) -> bool:
    x, y = pt
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi:
            inside = not inside
        j = i
    return inside
