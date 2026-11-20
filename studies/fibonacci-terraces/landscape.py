"""
Fibonacci Terraces: a landscape study in three ideas.

  1. L-systems           every tree is one Lindenmayer grammar, interpreted by a 3D turtle
  2. the golden section  the plan is a Fibonacci rectangle; a rill follows its spiral;
                         the beds are planted by the golden angle
  3. fractal relief      the surrounding land is recursive midpoint displacement,
                         cut into contour layers like an architect's model

Run with Blender's Python module:

    pip install bpy numpy
    python landscape.py                 # full renders (hero + plan)
    PREVIEW=1 python landscape.py       # small, fast, noisy
    SAVE_BLEND=1 python landscape.py    # also write fibonacci_terraces.blend

Everything is generated from the constants below. There are no external assets.
"""
import math
import os
import sys
import time

import bpy
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
PREVIEW = bool(os.environ.get('PREVIEW'))
VIEWS = os.environ.get('VIEWS', 'hero,plan').split(',')
PHI = (1 + 5 ** 0.5) / 2
GOLDEN_ANGLE = math.pi * (3 - 5 ** 0.5)          # 137.5 degrees

SEED = 21
STEP = 0.95            # metres each terrace rises above the one before it
LAND = 190.0           # side of the square of land the garden sits in, metres
GRID = 513 if PREVIEW else 1025
CONTOUR = 0.6          # height of one contour layer of the surrounding relief, metres
BASE_Z = -9.0          # underside of the model

rng = np.random.default_rng(SEED)


# ------------------------------------------------------------------ helpers

def material(name, rgb, rough=0.8, metallic=0.0):
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    bsdf = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs['Base Color'].default_value = (*[c ** 2.2 for c in rgb], 1)   # sRGB -> linear
    bsdf.inputs['Roughness'].default_value = rough
    bsdf.inputs['Metallic'].default_value = metallic
    return m


def hexrgb(h):
    return tuple(int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))


def mesh_object(name, verts, faces, mat, smooth=False):
    """Build a mesh straight from numpy arrays (faces all have the same vertex count)."""
    verts = np.asarray(verts, np.float32).reshape(-1, 3)
    faces = np.asarray(faces, np.int32)
    k = faces.shape[1]
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(verts))
    me.vertices.foreach_set('co', verts.ravel())
    me.loops.add(faces.size)
    me.loops.foreach_set('vertex_index', faces.ravel())
    me.polygons.add(len(faces))
    me.polygons.foreach_set('loop_start', np.arange(0, faces.size, k, dtype=np.int32))
    me.polygons.foreach_set('loop_total', np.full(len(faces), k, np.int32))
    if smooth:
        try:
            me.polygons.foreach_set('use_smooth', np.ones(len(faces), bool))
        except Exception:
            pass
    me.update(calc_edges=True)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(mat)
    return ob


def smoothstep(t):
    t = np.clip(t, 0, 1)
    return t * t * (3 - 2 * t)


# ------------------------------------------------- 2. the golden section: plan

def fibonacci_squares(count=9):
    """Squares of side 1, 1, 2, 3, 5 ... spiralling outward, each with its quarter-circle arc."""
    fib = [1, 1]
    while len(fib) < count:
        fib.append(fib[-1] + fib[-2])
    order = ['down', 'right', 'up', 'left']
    x0 = y0 = 0
    x1 = y1 = 1
    out = []
    for i, s in enumerate(fib):
        d = order[i % 4]
        if i == 0:
            x, y = 0, 0
        elif d == 'right':
            x, y = x1, y0; x1 += s
        elif d == 'up':
            x, y = x0, y1; y1 += s
        elif d == 'left':
            x, y = x0 - s, y0; x0 -= s
        else:
            x, y = x0, y0 - s; y0 -= s
        # the arc's centre is the corner the spiral turns around; it sweeps 90 degrees from `start`
        centre, start = {'right': ((x, y + s), -90), 'up': ((x, y), 0),
                         'left': ((x + s, y), 90), 'down': ((x + s, y + s), 180)}[d]
        out.append({'i': i, 'x': x, 'y': y, 's': s, 'c': centre, 'a0': math.radians(start),
                    'h': STEP * i})
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    for q in out:                                  # put the middle of the plot at the origin
        q['x'] -= cx; q['y'] -= cy
        q['c'] = (q['c'][0] - cx, q['c'][1] - cy)
    return out, (x0 - cx, y0 - cy, x1 - cx, y1 - cy)


# --------------------------------------------------------- 3. fractal relief

def diamond_square(n, roughness):
    """Recursive midpoint displacement on a (2^n + 1) grid. Each pass halves the step and
    adds noise scaled down by 2^-roughness, so every scale looks like every other."""
    size = 2 ** n + 1
    a = np.zeros((size, size))
    a[0, 0], a[0, -1], a[-1, 0], a[-1, -1] = rng.normal(0, 1, 4)
    step, scale = size - 1, 1.0
    while step > 1:
        half = step // 2
        # diamond: the centre of each square is the mean of its four corners
        corners = (a[0:-1:step, 0:-1:step] + a[step::step, 0:-1:step] +
                   a[0:-1:step, step::step] + a[step::step, step::step]) / 4
        a[half::step, half::step] = corners + rng.normal(0, scale, corners.shape)
        # square: the middle of each edge is the mean of the points around it
        centres = np.pad(a[half::step, half::step], 1)
        pad_count = np.pad(np.ones_like(a[half::step, half::step]), 1)
        # edges lying on the grid's rows
        lr = a[0::step, 0:-1:step] + a[0::step, step::step]
        ud = centres[:-1, 1:-1] + centres[1:, 1:-1]
        cnt = 2 + pad_count[:-1, 1:-1] + pad_count[1:, 1:-1]
        a[0::step, half::step] = (lr + ud) / cnt + rng.normal(0, scale, lr.shape)
        # edges lying on the grid's columns
        ud = a[0:-1:step, 0::step] + a[step::step, 0::step]
        lr = centres[1:-1, :-1] + centres[1:-1, 1:]
        cnt = 2 + pad_count[1:-1, :-1] + pad_count[1:-1, 1:]
        a[half::step, 0::step] = (ud + lr) / cnt + rng.normal(0, scale, ud.shape)
        step, scale = half, scale * 2 ** -roughness
    return a


def build_relief(squares, bounds, mat):
    n = int(math.log2(GRID - 1))
    wild = diamond_square(n, 0.86)
    for _ in range(7 * ((GRID - 1) // 512) ** 2):   # soften it, by the same distance in metres at any resolution
        wild = (wild + np.roll(wild, 1, 0) + np.roll(wild, -1, 0) +
                np.roll(wild, 1, 1) + np.roll(wild, -1, 1)) / 5
    wild = (wild - wild.mean()) / wild.std() * 7.0 + 4.6

    axis = np.linspace(-LAND / 2, LAND / 2, GRID)
    X, Y = np.meshgrid(axis, axis)
    x0, y0, x1, y1 = bounds
    nx, ny = np.clip(X, x0, x1 - 1e-6), np.clip(Y, y0, y1 - 1e-6)   # nearest point of the garden
    dist = np.hypot(X - nx, Y - ny)
    level = np.zeros_like(X)
    near, weight = np.zeros_like(X), np.zeros_like(X)
    for q in squares:
        inside = (nx >= q['x']) & (nx < q['x'] + q['s']) & (ny >= q['y']) & (ny < q['y'] + q['s'])
        level[inside] = q['h']
        # how strongly this terrace pulls on the land around it: everything close by, nothing far off
        d = np.hypot(np.maximum(np.maximum(q['x'] - X, X - q['x'] - q['s']), 0),
                     np.maximum(np.maximum(q['y'] - Y, Y - q['y'] - q['s']), 0))
        pull = 1 / (d * d + 0.3) ** 1.5
        near += pull * q['h']; weight += pull
    near /= weight
    # close to the garden the land meets the terraces; further off it is left to itself
    w = smoothstep(dist / 24)
    z = near * (1 - w) + wild * w
    # cut it into layers: a fast rise, then a flat tread, like stacked card
    t = z / CONTOUR
    z = CONTOUR * (np.floor(t) + smoothstep((t - np.floor(t) - 0.5) / 0.16 + 0.5))
    z = np.where(dist == 0, level - 0.4, z)        # under the terraces, out of sight

    verts = np.stack([X, Y, z], -1).reshape(-1, 3)
    idx = np.arange(GRID * GRID).reshape(GRID, GRID)
    faces = np.stack([idx[:-1, :-1], idx[:-1, 1:], idx[1:, 1:], idx[1:, :-1]], -1).reshape(-1, 4)
    # a skirt down to the base, so the land reads as a solid block
    ring = np.concatenate([idx[0, :], idx[1:, -1], idx[-1, -2::-1], idx[-2:0:-1, 0]])
    low = verts[ring].copy(); low[:, 2] = BASE_Z
    base = len(verts) + np.arange(len(ring))
    nxt = np.roll(np.arange(len(ring)), -1)
    skirt = np.stack([ring, base, base[nxt], ring[nxt]], -1)
    mesh_object('relief', np.concatenate([verts, low]), np.concatenate([faces, skirt]), mat, smooth=True)

    def height_at(px, py):
        i = int(round((py + LAND / 2) / LAND * (GRID - 1)))
        j = int(round((px + LAND / 2) / LAND * (GRID - 1)))
        return float(z[np.clip(i, 0, GRID - 1), np.clip(j, 0, GRID - 1)])
    return height_at


# ------------------------------------------------------------- 1. L-systems

TREE = {
    # Prusinkiewicz & Lindenmayer's branching bush. Note the second and third rules:
    # F -> S F and S -> F are Lindenmayer's original 1968 system, whose lengths are
    # the Fibonacci numbers. The trunk of every tree here grows by that sequence.
    'axiom': 'A',
    'rules': {'A': "[&FL!A]/////[&FL!A]///////[&FL!A]", 'F': 'S/////F', 'S': 'FL'},
    'angle': math.radians(22.5),
    'generations': 6 if PREVIEW else 7,
}


def rewrite(axiom, rules, generations):
    s = axiom
    for _ in range(generations):
        s = ''.join(rules.get(c, c) for c in s)
    return s


def turtle(program, angle, thin=0.72):
    """Walk a 3D turtle through the string. Returns branch segments and leaf placements."""
    c, s = math.cos(angle), math.sin(angle)
    yaw = {+1: np.array([[c, s, 0], [-s, c, 0], [0, 0, 1]]), -1: np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])}
    pitch = {+1: np.array([[c, 0, -s], [0, 1, 0], [s, 0, c]]), -1: np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])}
    roll = {+1: np.array([[1, 0, 0], [0, c, -s], [0, s, c]]), -1: np.array([[1, 0, 0], [0, c, s], [0, -s, c]])}
    pos = np.zeros(3)
    M = np.array([[0., 1, 0], [0, 0, 1], [1, 0, 0]])      # columns: heading, left, up
    width, stack, segs, leaves = 1.0, [], [], []
    for ch in program:
        if ch == 'F':
            nxt = pos + M[:, 0]
            segs.append((pos, nxt, M[:, 1], M[:, 2], width))
            pos = nxt
        elif ch == '+': M = M @ yaw[+1]
        elif ch == '-': M = M @ yaw[-1]
        elif ch == '&': M = M @ pitch[+1]
        elif ch == '^': M = M @ pitch[-1]
        elif ch == '/': M = M @ roll[+1]
        elif ch == '\\': M = M @ roll[-1]
        elif ch == '!': width *= thin
        elif ch == '[': stack.append((pos, M, width))
        elif ch == ']': pos, M, width = stack.pop()
        elif ch == 'L': leaves.append((pos, M))
    return segs, leaves


def build_tree(mat_wood, mat_leaf):
    """One tree, grown once, normalised to stand 1 unit tall. Every tree in the garden is this
    same individual at a different size, which is the point: the family is self-similar."""
    segs, leaves = turtle(rewrite(TREE['axiom'], TREE['rules'], TREE['generations']), TREE['angle'])
    p0 = np.array([s[0] for s in segs]); p1 = np.array([s[1] for s in segs])
    L = np.array([s[2] for s in segs]); U = np.array([s[3] for s in segs])
    w = np.array([s[4] for s in segs])
    top = max(p1[:, 2].max(), max(p[2] for p, _ in leaves))
    k, sides = 1 / top, 5
    radius = (0.016 * top * w)[:, None, None]                 # trunk about 1/30 of the height
    ang = np.arange(sides) * 2 * math.pi / sides
    ring = np.cos(ang)[None, :, None] * L[:, None, :] + np.sin(ang)[None, :, None] * U[:, None, :]
    verts = np.concatenate([p0[:, None, :] + ring * radius, p1[:, None, :] + ring * radius * 0.9], 1) * k
    n = len(segs)
    base = (np.arange(n) * sides * 2)[:, None]
    j = np.arange(sides)[None, :]; jn = (j + 1) % sides
    faces = np.stack([base + j, base + jn, base + sides + jn, base + sides + j], -1).reshape(-1, 4)
    wood = mesh_object('tree_wood', verts.reshape(-1, 3), faces, mat_wood, smooth=True)

    lp = np.array([p for p, _ in leaves]); lm = np.array([m for _, m in leaves])
    H, Lf, Up = lm[:, :, 0], lm[:, :, 1], lm[:, :, 2]
    a = 1.35                                                   # leaf length, in branch segments
    tilt = H * 0.8 + Up * 0.6
    quad = np.stack([lp, lp + a * (0.5 * tilt + 0.3 * Lf), lp + a * tilt, lp + a * (0.5 * tilt - 0.3 * Lf)], 1) * k
    leaf = mesh_object('tree_leaf', quad.reshape(-1, 3), np.arange(len(lp) * 4).reshape(-1, 4), mat_leaf)
    return wood, leaf, len(segs), len(leaves)


def place_copy(ob, location, scale, turn):
    c = bpy.data.objects.new(ob.name, ob.data)               # shares the mesh: one tree, many sizes
    bpy.context.scene.collection.objects.link(c)
    c.location = location; c.scale = (scale,) * 3; c.rotation_euler = (0, 0, turn)
    return c


# ------------------------------------------------------- the garden itself

def build_terraces(squares, mat_stone, mat_edge):
    verts, faces = [], []
    for q in squares:
        x, y, s, h = q['x'], q['y'], q['s'], q['h']
        b = len(verts)
        for z in (BASE_Z + 0.5, h):
            verts += [(x, y, z), (x + s, y, z), (x + s, y + s, z), (x, y + s, z)]
        faces += [(b + 4, b + 5, b + 6, b + 7)] + [(b + i, b + (i + 1) % 4, b + 4 + (i + 1) % 4, b + 4 + i) for i in range(4)]
    mesh_object('terraces', verts, faces, mat_stone)
    # a thin coping along the edge of every terrace, so each square reads as a square
    verts, faces = [], []
    for q in squares:
        x, y, s, h = q['x'], q['y'], q['s'], q['h']
        t, up = max(0.03, 0.012 * s), max(0.02, 0.006 * s)
        for (ax, ay, bx, by) in [(x, y, x + s, y + t), (x, y + s - t, x + s, y + s), (x, y, x + t, y + s), (x + s - t, y, x + s, y + s)]:
            b = len(verts)
            verts += [(ax, ay, h + up), (bx, ay, h + up), (bx, by, h + up), (ax, by, h + up)]
            faces.append((b, b + 1, b + 2, b + 3))
    mesh_object('coping', verts, faces, mat_edge)


def build_rill(squares, mat_water, mat_brass):
    """Water follows the Fibonacci spiral across the terraces and falls from each to the next."""
    water, wf, brass, bf = [], [], [], []

    def ribbon(store, faces, pts_in, pts_out, z):
        b = len(store)
        for (ix, iy), (ox, oy) in zip(pts_in, pts_out):
            store += [(ix, iy, z), (ox, oy, z)]
        for k in range(len(pts_in) - 1):
            faces.append((b + 2 * k, b + 2 * k + 1, b + 2 * k + 3, b + 2 * k + 2))

    for q in squares:
        s, h, (cx, cy) = q['s'], q['h'], q['c']
        if s < 2:
            continue                                         # the two unit squares are the pool
        half, lip = 0.017 * s, 0.007 * s
        ang = q['a0'] + np.linspace(0, math.pi / 2, max(12, int(10 * math.sqrt(s))))
        ring = lambda r: [(cx + r * math.cos(a), cy + r * math.sin(a)) for a in ang]
        ribbon(water, wf, ring(s - half), ring(s + half), h + 0.012 * s * 0.5)
        ribbon(brass, bf, ring(s - half - lip), ring(s - half), h + 0.012 * s)
        ribbon(brass, bf, ring(s + half), ring(s + half + lip), h + 0.012 * s)
        # the fall: where this arc begins, the water drops to the terrace below
        a = q['a0']
        px, py = cx + s * math.cos(a), cy + s * math.sin(a)
        rx, ry = math.cos(a) * half, math.sin(a) * half
        b = len(water)
        water += [(px - rx, py - ry, h), (px + rx, py + ry, h), (px + rx, py + ry, h - STEP), (px - rx, py - ry, h - STEP)]
        wf.append((b, b + 1, b + 2, b + 3))
    # the pool in the eye of the spiral
    for q in squares[:2]:
        x, y, s, h = q['x'], q['y'], q['s'], squares[1]['h']
        b = len(water); m = 0.06
        water += [(x + m, y + m, h + 0.02), (x + s - m, y + m, h + 0.02), (x + s - m, y + s - m, h + 0.02), (x + m, y + s - m, h + 0.02)]
        wf.append((b, b + 1, b + 2, b + 3))
    mesh_object('rill', water, wf, mat_water)
    mesh_object('rill_edge', brass, bf, mat_brass)


def icosphere():
    t = PHI
    v = np.array([(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t),
                  (0, -1, -t), (0, 1, -t), (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)], float)
    f = np.array([(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4),
                  (11, 10, 2), (10, 7, 6), (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8),
                  (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)])
    v /= np.linalg.norm(v[0])
    # one subdivision: 80 faces, round enough at this size
    mid, verts, faces = {}, list(v), []
    def m(a, b):
        key = (min(a, b), max(a, b))
        if key not in mid:
            p = (verts[a] + verts[b]) / 2
            verts.append(p / np.linalg.norm(p)); mid[key] = len(verts) - 1
        return mid[key]
    for a, b, c in f:
        ab, bc, ca = m(a, b), m(b, c), m(c, a)
        faces += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
    return np.array(verts), np.array(faces)


def anchor(q, reach):
    """A point on the square's diagonal, measured out from the corner the spiral turns around."""
    cx, cy = q['c']
    mx, my = q['x'] + q['s'] / 2, q['y'] + q['s'] / 2
    return cx + math.copysign(reach * q['s'], mx - cx), cy + math.copysign(reach * q['s'], my - cy)


def build_beds(squares, mat_shrub, count=233):
    """Each terrace has a round bed planted like a sunflower head: plant n sits at the golden
    angle times n, at a radius growing with the square root of n. 233 is a Fibonacci number,
    so the spirals you can count in the bed are 13 one way and 21 the other."""
    sv, sf = icosphere()
    verts, faces = [], []
    for q in squares:
        if q['s'] < 3:
            continue
        px, py = anchor(q, 0.31)
        R = 0.27 * q['s']
        spacing = R * math.sqrt(math.pi / count)
        for n in range(6, count + 1):                          # the first few make room for the trunk
            r, a = R * math.sqrt(n / count), n * GOLDEN_ANGLE
            size = 0.47 * spacing * (0.55 + 0.45 * math.sqrt(n / count))
            centre = np.array([px + r * math.cos(a), py + r * math.sin(a), q['h'] + size * 0.62])
            faces.append(sf + len(verts) * 0 + sum(len(v) for v in verts))
            verts.append(sv * size * np.array([1, 1, 0.8]) + centre)
    mesh_object('beds', np.concatenate(verts), np.concatenate(faces), mat_shrub, smooth=True)


def build_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    paper = material('paper', hexrgb('#f0ebe1'), 0.92)
    stone = material('stone', hexrgb('#d2c6ae'), 0.8)
    edge = material('edge', hexrgb('#a89c85'), 0.7)
    water = material('water', hexrgb('#0c4750'), 0.06)
    brass = material('brass', hexrgb('#c69a45'), 0.32, 1.0)
    wood = material('wood', hexrgb('#3b2a20'), 0.7)
    leaf = material('leaf', hexrgb('#9aa74c'), 0.6)
    shrub = material('shrub', hexrgb('#5f8560'), 0.75)
    table = material('table', hexrgb('#cfc9bf'), 0.9)

    squares, bounds = fibonacci_squares()
    height_at = build_relief(squares, bounds, paper)
    build_terraces(squares, stone, edge)
    build_rill(squares, water, brass)
    build_beds(squares, shrub)

    tree_wood, tree_leaf, n_seg, n_leaf = build_tree(wood, leaf)
    for q in squares:
        if q['s'] < 2:
            continue
        px, py = anchor(q, 0.31)
        for part in (tree_wood, tree_leaf):
            place_copy(part, (px, py, q['h']), 0.33 * q['s'], q['i'] * GOLDEN_ANGLE)
    # the same tree goes on shrinking outside the wall, scattered over the wild land by the golden angle
    x0, y0, x1, y1 = bounds
    for n in range(1, 145):
        r, a = 24 + 5.9 * math.sqrt(n), n * GOLDEN_ANGLE
        px, py = r * math.cos(a), r * math.sin(a) * 1.12
        if x0 - 6 < px < x1 + 6 and y0 - 6 < py < y1 + 6 or max(abs(px), abs(py)) > LAND / 2 - 8:
            continue
        size = 2.6 * PHI ** ((n * 7) % 4 - 1.5)
        for part in (tree_wood, tree_leaf):
            place_copy(part, (px, py, height_at(px, py) - 0.05), size, n * 2.4)
    for part in (tree_wood, tree_leaf):
        bpy.data.objects.remove(part)                           # the originals stood at the origin

    half = LAND * 4
    mesh_object('table', [(-half, -half, BASE_Z), (half, -half, BASE_Z), (half, half, BASE_Z), (-half, half, BASE_Z)],
                [(0, 1, 2, 3)], table)
    return squares, bounds, n_seg, n_leaf


# ------------------------------------------------------- light, lens, film

def aim(ob, target):
    ob.rotation_euler = (Vector(target) - ob.location).to_track_quat('-Z', 'Y').to_euler()


def setup_render(scene):
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 40 if PREVIEW else 320
    try:
        scene.cycles.use_denoising = True
        scene.cycles.denoiser = 'OPENIMAGEDENOISE'
    except Exception as e:
        print('denoiser unavailable:', e)
    try:
        scene.view_settings.view_transform = 'AgX'
        scene.view_settings.look = 'AgX - Medium High Contrast'
    except Exception as e:
        print('view transform:', e)
    scene.render.image_settings.file_format = 'PNG'

    world = bpy.data.worlds.new('studio')
    try:
        world.use_nodes = True
    except Exception:
        pass
    bg = next(n for n in world.node_tree.nodes if n.type == 'BACKGROUND')
    bg.inputs['Color'].default_value = (0.62, 0.70, 0.84, 1)    # cool fill against a warm sun
    bg.inputs['Strength'].default_value = 0.55
    scene.world = world

    sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
    scene.collection.objects.link(sun)
    sun.data.energy = 4.6
    sun.data.color = (1.0, 0.86, 0.68)
    sun.data.angle = math.radians(2.2)
    sun.location = (-80, -30, 46)                               # low, from the west: long shadows off every layer
    aim(sun, (0, 0, 0))


def camera(scene, name, location, target, lens=None, ortho=None, fstop=None):
    cam = bpy.data.objects.new(name, bpy.data.cameras.new(name))
    scene.collection.objects.link(cam)
    cam.location = location
    aim(cam, target)
    cam.data.clip_end = 2000
    if ortho:
        cam.data.type = 'ORTHO'; cam.data.ortho_scale = ortho
    else:
        cam.data.lens = lens
    if fstop:
        cam.data.dof.use_dof = True
        cam.data.dof.focus_distance = (Vector(target) - Vector(location)).length
        cam.data.dof.aperture_fstop = fstop
    return cam


def render(scene, cam, path, width, height):
    scene.camera = cam
    scale = 0.42 if PREVIEW else 1
    scene.render.resolution_x, scene.render.resolution_y = int(width * scale), int(height * scale)
    scene.render.filepath = path
    t = time.time()
    bpy.ops.render.render(write_still=True)
    print(f'rendered {os.path.basename(path)} in {time.time() - t:.0f}s')


def main():
    t = time.time()
    squares, bounds, n_seg, n_leaf = build_scene()
    scene = bpy.context.scene
    setup_render(scene)
    print(f'built in {time.time() - t:.0f}s: plot {bounds[2] - bounds[0]:.0f} x {bounds[3] - bounds[1]:.0f} m, '
          f'tree with {n_seg} branch segments and {n_leaf} leaves')
    eye = squares[0]
    focus = (eye['x'] + 2, eye['y'] + 2, 2.0)
    suffix = '_preview' if PREVIEW else ''
    if 'hero' in VIEWS:
        cam = camera(scene, 'hero', (70, 96, 66), (-2, -6, 3.0), lens=62, fstop=0.5)
        render(scene, cam, os.path.join(HERE, f'fibonacci_terraces{suffix}.png'), 2400, 1500)
    if 'plan' in VIEWS:
        cam = camera(scene, 'plan', (0, 0, 300), (0, 0, 0), ortho=86)
        cam.rotation_euler = (0, 0, 0)
        render(scene, cam, os.path.join(HERE, f'fibonacci_terraces_plan{suffix}.png'), 1800, 1800)
    if os.environ.get('SAVE_BLEND'):
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, 'fibonacci_terraces.blend'))


if __name__ == '__main__':
    main()
