"""
Pure Anatomical Carved-Stone Dragon Mesh Generator (`piece_meshes.py`).

Sculpts 6 unmistakable, anatomically authentic Dark-Fantasy Carved-Stone Dragon
Breeds (`ドラゴンの石造`) perched atop natural jagged ruined-stone crags (`PART_PEDESTAL`):

  - pawn   (1.08m): 幼竜ドレイク — Quadruped Stone Hatchling Prowler on jagged slate crag
  - rook   (1.38m): 重装鎧地竜 — Quadruped Armored Behemoth Earth-Drake with spiked club-tail
  - knight (1.62m): 双翼ワイバーン — Rearing Bipedal Winged Wyvern with raptorial strike talons
  - bishop (1.72m): 双頭の秘術竜 — Twin-Headed Oracle Hydra-Wyrm with two intertwining dragon necks/skulls
  - queen  (1.94m): 四翼の飛翔女帝竜 — Four-Winged Celestial Elder Dragon with 4-horned crown skull
  - king   (2.18m): 大聖堂の覇王古竜 — Colossal Rearing Quadruped Sovereign Arch-Dragon

Every mesh is 100% watertight 2-manifold (`nonMan == 0`), faces `+Y`, grounds its
ruined stone crag flush at `Z = 0.0` (`Z in [0.0, 0.22]`, `r_xy <= 0.47m`), fits within
`MAX_WING_RADIUS <= 0.56m`, populates all 7 semantic `PartID` vertex layers (`0..6`),
and maps cleanly to isotropic carved-stone UV zones from `dragon_spec.py`.
"""

import math
import os
import sys
import bpy
import bmesh
from mathutils import Vector, Matrix, Euler

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from dragon_spec import (
    PIECE_HEIGHTS,
    MAX_CRAG_RADIUS,
    MAX_WING_RADIUS,
    PART_PEDESTAL,
    PART_LOWER_BODY,
    PART_UPPER_BODY,
    PART_HEAD_JAW,
    PART_WEAPON_R,
    PART_SHIELD_L,
    PART_WINGS_TAIL,
    UV_ZONE_SCALES,
    UV_ZONE_STONE,
    UV_ZONE_RUNES,
    UV_ZONE_BRONZE,
)


def _safe_norm(v: Vector, fallback: Vector = Vector((0.0, 0.0, 1.0))) -> Vector:
    if v.length_squared < 1e-12:
        return fallback.copy()
    return v.normalized()


def _zone_v_bounds(uv_zone: tuple[float, float]) -> tuple[float, float]:
    """
    Map each dragon_spec UV zone to its crisp interior V sub-band so mipmaps
    never bleed across zone borders and dragon osteoderm scales orient monotonically.
    """
    if uv_zone == UV_ZONE_SCALES:
        return (0.360, 0.492)
    if uv_zone == UV_ZONE_STONE:
        return (0.688, 0.792)
    if uv_zone == UV_ZONE_RUNES:
        return (0.826, 0.884)
    if uv_zone == UV_ZONE_BRONZE:
        return (0.926, 0.974)
    lo, hi = uv_zone
    pad = (hi - lo) * 0.08
    return (lo + pad, hi - pad)


def _pingpong_v(t: float, v_lo: float, v_hi: float, repeats: int = 1) -> float:
    t_c = max(0.0, min(1.0, t))
    if repeats <= 1:
        f = t_c
    else:
        f = 0.5 - 0.5 * math.cos(math.pi * t_c * repeats)
    return v_lo + f * (v_hi - v_lo)


def _cubic_bezier(p0: Vector, p1: Vector, p2: Vector, p3: Vector, t: float) -> Vector:
    u = 1.0 - t
    return (
        (u * u * u) * p0
        + (3.0 * u * u * t) * p1
        + (3.0 * u * t * t) * p2
        + (t * t * t) * p3
    )


def _frame_from_forward_up(forward: Vector, up_hint: Vector = Vector((0.0, 0.0, 1.0))) -> Matrix:
    """
    Build a right-handed 3x3 rotation matrix where:
      +Y_local = forward (snout / limb / talon point direction)
      +Z_local = dorsal / up (orthogonalized from up_hint)
      +X_local = right (Y_local x Z_local -> X x Y = +Z)
    """
    y_ax = _safe_norm(forward, Vector((0.0, 1.0, 0.0)))
    if abs(y_ax.dot(_safe_norm(up_hint))) > 0.96:
        up_hint = Vector((0.0, 1.0, 0.0)) if abs(y_ax.y) < 0.8 else Vector((1.0, 0.0, 0.0))
    x_ax = _safe_norm(y_ax.cross(up_hint), Vector((1.0, 0.0, 0.0)))
    z_ax = _safe_norm(x_ax.cross(y_ax), Vector((0.0, 0.0, 1.0)))
    return Matrix((
        (x_ax.x, y_ax.x, z_ax.x),
        (x_ax.y, y_ax.y, z_ax.y),
        (x_ax.z, y_ax.z, z_ax.z),
    ))


class DragonSculptor:
    """
    Watertight 2-manifold BMesh sculptor for pure anatomical Carved-Stone Dragons.
    Every primitive constructs closed, manifold shells with isotropic UVs.
    """

    def __init__(self):
        self.bm = bmesh.new()
        self.uv_layer = self.bm.loops.layers.uv.new("UVMap")
        self.part_layer = self.bm.verts.layers.int.new("PartID")

    def _new_vert(self, co: Vector, part_id: int):
        v = self.bm.verts.new(co)
        v[self.part_layer] = int(part_id)
        return v

    def _add_face(self, verts, uvs, smooth: bool = True, flip: bool = False):
        if flip:
            verts = list(reversed(verts))
            uvs = list(reversed(uvs))
        try:
            f = self.bm.faces.new(verts)
            f.smooth = smooth
            for loop, uv in zip(f.loops, uvs):
                loop[self.uv_layer].uv = (
                    max(0.0, min(1.0, float(uv[0]))),
                    max(0.0, min(1.0, float(uv[1]))),
                )
            return f
        except ValueError:
            return None

    # ==========================================================================
    # CORE CLOSED 2-MANIFOLD SCULPTING PRIMITIVES
    # ==========================================================================
    def add_lofted_spine(
        self,
        stations: list[tuple[Vector, float, float]],
        segs: int = 12,
        up_hint: Vector = Vector((0.0, 0.0, 1.0)),
        dorsal_keel: float = 0.0,
        ventral_flat: float = 0.0,
        ring_ridge_amp: float = 0.0,
        sharp_tip: bool = False,
        uv_zone: tuple[float, float] = UV_ZONE_SCALES,
        v_repeats: int = 1,
        part_id: int = PART_UPPER_BODY,
        part_ids: list[int] | None = None,
        smooth: bool = True,
    ) -> list[tuple[Vector, Vector, Vector]]:
        """
        Watertight parallel-transport (Bishop frame) tube along 3D curve stations:
          stations = [(world_pos, radius_x, radius_y_dorsal), ...]
        Returns list of `(pos, tangent, dorsal_normal)` frames for attaching osteoderms/spines.
        """
        n_pts = len(stations)
        if n_pts < 2:
            return []

        v_lo, v_hi = _zone_v_bounds(uv_zone)

        tangents: list[Vector] = []
        for i in range(n_pts):
            if i == 0:
                d = stations[1][0] - stations[0][0]
            elif i == n_pts - 1:
                d = stations[-1][0] - stations[-2][0]
            else:
                d = stations[i + 1][0] - stations[i - 1][0]
            tangents.append(_safe_norm(d, Vector((0.0, 0.0, 1.0))))

        t0 = tangents[0]
        uh = _safe_norm(up_hint, Vector((0.0, 0.0, 1.0)))
        if abs(t0.dot(uh)) > 0.95:
            uh = Vector((0.0, -1.0, 0.0)) if abs(t0.y) < 0.8 else Vector((1.0, 0.0, 0.0))
        n_cur = _safe_norm(uh - t0 * t0.dot(uh))

        frames: list[tuple[Vector, Vector, Vector]] = []
        rings = []
        end_ring_count = n_pts - 1 if sharp_tip else n_pts

        for i in range(n_pts):
            pt, rx, ry = stations[i]
            ti = tangents[i]
            if i > 0:
                rot_q = tangents[i - 1].rotation_difference(ti)
                n_cur = _safe_norm(rot_q @ n_cur)
                n_cur = _safe_norm(n_cur - ti * ti.dot(n_cur), n_cur)
            x_cur = _safe_norm(n_cur.cross(ti))
            frames.append((pt.copy(), ti.copy(), n_cur.copy()))

            if i >= end_ring_count:
                continue

            pid_i = part_ids[i] if part_ids is not None else part_id
            ring_mod = 1.0 + ring_ridge_amp * (1.0 if (i % 2 == 0) else -1.0)
            rx_e = max(rx * ring_mod, 0.0018)
            ry_e = max(ry * ring_mod, 0.0018)
            vc = _pingpong_v(i / float(max(n_pts - 1, 1)), v_lo, v_hi, v_repeats)

            ring = []
            for s in range(segs):
                ang = (s / float(segs)) * 2.0 * math.pi
                ca = math.cos(ang)
                sa = math.sin(ang)
                lx = ca * rx_e
                ly = sa * ry_e
                if dorsal_keel > 0.0 and sa > 0.22:
                    ly += dorsal_keel * ry_e * ((sa - 0.22) / 0.78) ** 1.55
                if ventral_flat > 0.0 and sa < -0.18:
                    ly *= (1.0 - ventral_flat * min(1.0, abs(sa + 0.18)))
                co = pt + x_cur * lx + n_cur * ly
                ring.append((self._new_vert(co, pid_i), vc))
            rings.append(ring)

        avg_r = sum(0.5 * (st[1] + st[2]) for st in stations) / float(len(stations))
        u_span = max(0.32, min(1.0, avg_r / 0.145)) if uv_zone == UV_ZONE_SCALES else 1.0

        for i in range(len(rings) - 1):
            r0, r1 = rings[i], rings[i + 1]
            for s in range(segs):
                sn = (s + 1) % segs
                u0 = (s / float(segs)) * u_span
                u1 = ((s + 1) / float(segs)) * u_span
                self._add_face(
                    [r0[s][0], r0[sn][0], r1[sn][0], r1[s][0]],
                    [(u0, r0[s][1]), (u1, r0[sn][1]), (u1, r1[sn][1]), (u0, r1[s][1])],
                    smooth=smooth,
                )

        v_mid = 0.5 * (v_lo + v_hi)
        # Start cap (-T outward) — planar 2D UV patch (no concentric bullseye rings)
        c_start = self._new_vert(stations[0][0], part_ids[0] if part_ids is not None else part_id)
        for s in range(segs):
            sn = (s + 1) % segs
            ang0 = (s / float(segs)) * 2.0 * math.pi
            ang1 = (sn / float(segs)) * 2.0 * math.pi
            self._add_face(
                [c_start, rings[0][sn][0], rings[0][s][0]],
                [
                    (0.5, v_mid),
                    (0.5 + 0.045 * math.cos(ang1), v_mid + 0.038 * math.sin(ang1)),
                    (0.5 + 0.045 * math.cos(ang0), v_mid + 0.038 * math.sin(ang0)),
                ],
                smooth=False,
            )

        # End cap or sharp cone apex (+T outward)
        c_end = self._new_vert(stations[-1][0], part_ids[-1] if part_ids is not None else part_id)
        r_last = rings[-1]
        for s in range(segs):
            sn = (s + 1) % segs
            if sharp_tip:
                cap_uvs = [
                    (0.5 * u_span, v_hi),
                    ((s / float(segs)) * u_span, r_last[s][1]),
                    (((s + 1) / float(segs)) * u_span, r_last[sn][1]),
                ]
            else:
                ang0 = (s / float(segs)) * 2.0 * math.pi
                ang1 = (sn / float(segs)) * 2.0 * math.pi
                cap_uvs = [
                    (0.5, v_mid),
                    (0.5 + 0.045 * math.cos(ang0), v_mid + 0.038 * math.sin(ang0)),
                    (0.5 + 0.045 * math.cos(ang1), v_mid + 0.038 * math.sin(ang1)),
                ]
            self._add_face(
                [c_end, r_last[s][0], r_last[sn][0]],
                cap_uvs,
                smooth=sharp_tip and smooth,
            )

        return frames

    def add_lofted_polygon(
        self,
        poly_xy: list[tuple[float, float]],
        slices: list[tuple[float, float, float, float, float]],
        origin: Vector = Vector((0.0, 0.0, 0.0)),
        basis: Matrix = Matrix.Identity(3),
        sharp_end: bool = False,
        uv_zone: tuple[float, float] = UV_ZONE_STONE,
        part_id: int = PART_UPPER_BODY,
        smooth: bool = False,
        runes_along_z: bool = False,
    ):
        """
        Watertight loft of a 2D CCW polygon `poly_xy` through `slices`:
          slices = [(z_local, scale_x, scale_y, offset_x, offset_y), ...]
        Checks `basis.determinant() < 0` so mirrored parts never invert face normals.
        """
        flip = basis.determinant() < 0.0
        v_lo, v_hi = _zone_v_bounds(uv_zone)
        n_sides = len(poly_xy)
        n_sl = len(slices)
        ring_sl_count = n_sl - 1 if sharp_end else n_sl

        z0, z1 = slices[0][0], slices[-1][0]
        z_span = max(abs(z1 - z0), 1e-4)

        rings = []
        for idx in range(ring_sl_count):
            zl, sx, sy, ox, oy = slices[idx]
            zt = abs(zl - z0) / z_span
            vc = v_lo + zt * (v_hi - v_lo)
            ring = []
            for k, (px, py) in enumerate(poly_xy):
                lp = Vector((px * sx + ox, py * sy + oy, zl))
                ring.append((self._new_vert(origin + basis @ lp, part_id), vc, zt))
            rings.append(ring)

        for i in range(len(rings) - 1):
            r0, r1 = rings[i], rings[i + 1]
            for k in range(n_sides):
                kn = (k + 1) % n_sides
                if runes_along_z:
                    u0 = min(0.94, 0.06 + r0[k][2] * min(0.84, z_span * 1.35))
                    u1 = min(0.94, 0.06 + r1[k][2] * min(0.84, z_span * 1.35))
                    vk0 = v_lo + (abs((k / float(n_sides)) - 0.5) * 2.0) * (v_hi - v_lo)
                    vk1 = v_lo + (abs(((k + 1) / float(n_sides)) - 0.5) * 2.0) * (v_hi - v_lo)
                    quad_uvs = [(u0, vk0), (u0, vk1), (u1, vk1), (u1, vk0)]
                else:
                    u0 = (k / float(n_sides)) * 0.45
                    u1 = ((k + 1) / float(n_sides)) * 0.45
                    quad_uvs = [(u0, r0[k][1]), (u1, r0[kn][1]), (u1, r1[kn][1]), (u0, r1[k][1])]
                self._add_face(
                    [r0[k][0], r0[kn][0], r1[kn][0], r1[k][0]],
                    quad_uvs,
                    smooth=smooth,
                    flip=flip,
                )

        v_mid = 0.5 * (v_lo + v_hi)
        # Bottom cap — planar 2D UV projection
        zl0, _, _, ox0, oy0 = slices[0]
        c_bot = self._new_vert(origin + basis @ Vector((ox0, oy0, zl0)), part_id)
        for k in range(n_sides):
            kn = (k + 1) % n_sides
            ang0 = (k / float(n_sides)) * 2.0 * math.pi
            ang1 = (kn / float(n_sides)) * 2.0 * math.pi
            self._add_face(
                [c_bot, rings[0][kn][0], rings[0][k][0]],
                [
                    (0.5, v_mid),
                    (0.5 + 0.055 * math.cos(ang1), v_mid + 0.042 * math.sin(ang1)),
                    (0.5 + 0.055 * math.cos(ang0), v_mid + 0.042 * math.sin(ang0)),
                ],
                smooth=False,
                flip=flip,
            )

        # Top cap / apex
        zlt, _, _, oxt, oyt = slices[-1]
        c_top = self._new_vert(origin + basis @ Vector((oxt, oyt, zlt)), part_id)
        r_last = rings[-1]
        for k in range(n_sides):
            kn = (k + 1) % n_sides
            if sharp_end:
                top_uvs = [
                    (0.25, v_hi),
                    ((k / float(n_sides)) * 0.45, r_last[k][1]),
                    (((k + 1) / float(n_sides)) * 0.45, r_last[kn][1]),
                ]
            else:
                ang0 = (k / float(n_sides)) * 2.0 * math.pi
                ang1 = (kn / float(n_sides)) * 2.0 * math.pi
                top_uvs = [
                    (0.5, v_mid),
                    (0.5 + 0.055 * math.cos(ang0), v_mid + 0.042 * math.sin(ang0)),
                    (0.5 + 0.055 * math.cos(ang1), v_mid + 0.042 * math.sin(ang1)),
                ]
            self._add_face(
                [c_top, r_last[k][0], r_last[kn][0]],
                top_uvs,
                smooth=sharp_end and smooth,
                flip=flip,
            )

    def add_box_bevel(
        self,
        size: Vector,
        center: Vector,
        rot_euler: tuple[float, float, float] = (0.0, 0.0, 0.0),
        taper_top: tuple[float, float] = (1.0, 1.0),
        uv_zone: tuple[float, float] = UV_ZONE_STONE,
        part_id: int = PART_UPPER_BODY,
    ):
        hx, hy, hz = size.x * 0.5, size.y * 0.5, size.z * 0.5
        cham = min(hx, hy) * 0.16
        poly = [
            (-hx + cham, -hy),
            (hx - cham, -hy),
            (hx, -hy + cham),
            (hx, hy - cham),
            (hx - cham, hy),
            (-hx + cham, hy),
            (-hx, hy - cham),
            (-hx, -hy + cham),
        ]
        slices = [
            (-hz, 0.92, 0.92, 0.0, 0.0),
            (-hz * 0.82, 1.0, 1.0, 0.0, 0.0),
            (hz * 0.82, taper_top[0], taper_top[1], 0.0, 0.0),
            (hz, taper_top[0] * 0.88, taper_top[1] * 0.88, 0.0, 0.0),
        ]
        self.add_lofted_polygon(
            poly,
            slices,
            origin=center,
            basis=Euler(rot_euler, "XYZ").to_matrix(),
            uv_zone=uv_zone,
            part_id=part_id,
            smooth=False,
            runes_along_z=(uv_zone == UV_ZONE_RUNES and size.z > size.x * 1.4),
        )

    # ==========================================================================
    # NATURAL JAGGED RUINED-STONE CRAG BASE (`PART_PEDESTAL = 0`)
    # ==========================================================================
    def add_jagged_stone_crag(
        self,
        seed: int = 1,
        max_r: float = 0.44,
        crag_h: float = 0.205,
        spire_bias_y: float = -0.02,
        slab_tilt: tuple[float, float, float] = (0.14, -0.09, 0.22),
    ):
        """
        Sculpts a jagged volcanic/limestone rock outcrop (`PART_PEDESTAL = 0`):
          - Irregular 14-sided faceted cliff massif grounded flush at `Z = 0.0`
          - 5 asymmetric flanking basalt/limestone rock buttresses & claw-perches (`Z = 0.0` bottom)
          - Shattered tilted Gothic sanctuary slab + subtle obsidian-bronze crag clamp
          - Glowing recessed draconic ley-line rune fissures (`UV_ZONE_RUNES`)
        NO circular lathe drums or octagonal chess pedestals!
        """
        s_f = float(seed) * 1.731

        # 1. Primary irregular 14-facet rock massif grounded strictly at Z = 0.000
        n_crag = 14
        crag_poly = []
        for k in range(n_crag):
            ang = (k / float(n_crag)) * 2.0 * math.pi
            jag = (
                0.86
                + 0.08 * math.sin(3.0 * ang + s_f)
                + 0.06 * math.cos(5.0 * ang - s_f * 1.4)
                + 0.04 * math.sin(7.0 * ang + s_f * 2.1)
            )
            r_k = min(max_r, max_r * jag)
            crag_poly.append((math.cos(ang) * r_k, math.sin(ang) * r_k))

        dx1 = 0.018 * math.cos(s_f)
        dy1 = spire_bias_y
        crag_slices = [
            (0.000, 1.00, 1.00, 0.0, 0.0),
            (crag_h * 0.30, 0.96, 0.95, dx1 * 0.4, dy1 * 0.3),
            (crag_h * 0.62, 0.86, 0.85, dx1 * 0.8, dy1 * 0.7),
            (crag_h * 0.88, 0.74, 0.72, dx1, dy1),
            (crag_h * 0.97, 0.58, 0.56, dx1 * 1.1, dy1 * 1.1),
        ]
        self.add_lofted_polygon(
            crag_poly,
            crag_slices,
            origin=Vector((0.0, 0.0, 0.0)),
            uv_zone=UV_ZONE_STONE,
            part_id=PART_PEDESTAL,
            smooth=False,
        )

        # 2. Five asymmetric fractured rock outcrops / claw-grip ledges (all grounded at Z = 0.000)
        boulder_angles = [0.35, 1.48, 2.55, 3.82, 5.18]
        for b_idx, b_ang_base in enumerate(boulder_angles):
            b_ang = b_ang_base + 0.16 * math.sin(s_f + b_idx * 2.1)
            dist = max_r * (0.58 + 0.08 * ((b_idx * 3 + seed) % 3))
            bx = math.cos(b_ang) * dist
            by = math.sin(b_ang) * dist
            b_rad = 0.115 + 0.018 * ((b_idx + seed) % 3)
            # Keep outer boulder vertices strictly inside r <= max_r + 0.022 <= 0.468
            if math.hypot(bx, by) + b_rad > 0.466:
                dist = max(0.20, 0.466 - b_rad)
                bx = math.cos(b_ang) * dist
                by = math.sin(b_ang) * dist

            b_poly = []
            for k in range(7):
                a_k = (k / 7.0) * 2.0 * math.pi + b_ang
                rk = b_rad * (0.82 + 0.18 * math.cos(3.0 * a_k + b_idx))
                b_poly.append((math.cos(a_k) * rk, math.sin(a_k) * rk))

            bh = crag_h * (0.68 + 0.11 * ((b_idx + seed) % 4))
            b_slices = [
                (0.000, 1.00, 1.00, 0.0, 0.0),
                (bh * 0.48, 0.90, 0.88, -bx * 0.08, -by * 0.08),
                (bh * 0.88, 0.68, 0.65, -bx * 0.16, -by * 0.16),
                (bh, 0.44, 0.42, -bx * 0.20, -by * 0.20),
            ]
            self.add_lofted_polygon(
                b_poly,
                b_slices,
                origin=Vector((bx, by, 0.0)),
                uv_zone=UV_ZONE_STONE,
                part_id=PART_PEDESTAL,
                smooth=False,
            )

        # 3. Tilted shattered Gothic sanctuary stone slab wedged atop the crag
        slab_poly = [
            (-0.22, -0.17),
            (0.19, -0.19),
            (0.24, -0.04),
            (0.20, 0.18),
            (-0.08, 0.22),
            (-0.24, 0.11),
        ]
        slab_slices = [
            (-0.032, 0.96, 0.96, 0.0, 0.0),
            (0.018, 1.00, 1.00, 0.0, 0.0),
            (0.032, 0.92, 0.92, 0.0, 0.0),
        ]
        self.add_lofted_polygon(
            slab_poly,
            slab_slices,
            origin=Vector((0.0, spire_bias_y * 0.6, crag_h * 0.80)),
            basis=Euler(slab_tilt, "XYZ").to_matrix(),
            uv_zone=UV_ZONE_STONE,
            part_id=PART_PEDESTAL,
            smooth=False,
        )

        # Subtle ancient weathered bronze crag-clamp embedded in shattered slab edge
        self.add_box_bevel(
            size=Vector((0.085, 0.036, 0.028)),
            center=Vector((0.18, 0.16, crag_h * 0.72)),
            rot_euler=(slab_tilt[0], slab_tilt[1], slab_tilt[2] + 0.55),
            uv_zone=UV_ZONE_BRONZE,
            part_id=PART_PEDESTAL,
        )

        # 4. Glowing Recessed Draconic Ley-Line Rune Veins splitting the rock crag!
        for v_idx, v_ang in enumerate((0.42 + 0.2 * seed, 2.35 + 0.15 * seed, 4.45 - 0.18 * seed)):
            p_in = Vector((math.cos(v_ang) * 0.08, math.sin(v_ang) * 0.08, crag_h * 0.93))
            p_mid = Vector((math.cos(v_ang + 0.18) * (max_r * 0.54), math.sin(v_ang + 0.18) * (max_r * 0.54), crag_h * 0.72))
            p_out = Vector((math.cos(v_ang + 0.08) * (max_r * 0.86), math.sin(v_ang + 0.08) * (max_r * 0.86), crag_h * 0.24))
            self.add_lofted_spine(
                [
                    (p_in, 0.016, 0.014),
                    (p_mid, 0.022, 0.018),
                    (p_out, 0.015, 0.014),
                ],
                segs=6,
                up_hint=Vector((0.0, 0.0, 1.0)),
                dorsal_keel=0.25,
                uv_zone=UV_ZONE_RUNES,
                part_id=PART_PEDESTAL,
                smooth=False,
            )

    # ==========================================================================
    # ANATOMICAL REPTILIAN / DRACONIC SCULPTURAL HELPERS
    # ==========================================================================
    def add_3d_scale_plate(
        self,
        pos: Vector,
        outward_dir: Vector,
        down_dir: Vector,
        width: float,
        length: float,
        thickness: float,
        part_id: int,
        uv_zone: tuple[float, float] = UV_ZONE_STONE,
    ):
        """
        Single 3D chiselled pointed dragon osteoderm plate with raised central keel!
        """
        z_out = _safe_norm(outward_dir, Vector((0.0, 1.0, 0.0)))
        y_up = _safe_norm(-down_dir, Vector((0.0, 0.0, 1.0)))
        if abs(z_out.dot(y_up)) > 0.95:
            y_up = Vector((0.0, 0.0, 1.0)) if abs(z_out.z) < 0.8 else Vector((1.0, 0.0, 0.0))
        x_rt = _safe_norm(y_up.cross(z_out))
        y_up = _safe_norm(z_out.cross(x_rt))
        basis = Matrix((
            (x_rt.x, y_up.x, z_out.x),
            (x_rt.y, y_up.y, z_out.y),
            (x_rt.z, y_up.z, z_out.z),
        ))
        hw = width * 0.5
        hl = length * 0.5
        poly = [
            (0.0, -hl * 1.15),
            (hw * 0.96, -hl * 0.12),
            (hw * 0.78, hl * 0.84),
            (0.0, hl * 0.96),
            (-hw * 0.78, hl * 0.84),
            (-hw * 0.96, -hl * 0.12),
        ]
        slices = [
            (-thickness * 0.35, 0.96, 0.96, 0.0, 0.0),
            (thickness * 0.55, 0.88, 0.88, 0.0, -hl * 0.06),
            (thickness * 1.08, 0.22, 0.76, 0.0, -hl * 0.10),
        ]
        self.add_lofted_polygon(
            poly,
            slices,
            origin=pos,
            basis=basis,
            uv_zone=uv_zone,
            part_id=part_id,
            smooth=False,
        )

    def add_spine_osteoderms(
        self,
        frames: list[tuple[Vector, Vector, Vector]],
        radii_xy: list[tuple[float, float]],
        count: int,
        width: float,
        length: float,
        thickness: float = 0.022,
        lateral_angle_deg: float = 0.0,
        part_id: int = PART_UPPER_BODY,
    ):
        """
        Places overlapping 3D carved dragon osteoderm armor bosses along a curved spine!
        """
        n_f = min(len(frames), len(radii_xy))
        if n_f < 2 or count < 1:
            return
        ang_rad = math.radians(lateral_angle_deg)
        for k in range(count):
            t = (k + 0.5) / float(count)
            idx = min(n_f - 1, max(0, int(round(t * (n_f - 1)))))
            pos, tan_v, norm_v = frames[idx]
            rx, ry = radii_xy[idx]
            x_v = _safe_norm(norm_v.cross(tan_v))
            surf_dir = _safe_norm(norm_v * math.cos(ang_rad) + x_v * math.sin(ang_rad))
            r_eff = math.hypot(rx * math.sin(ang_rad), ry * math.cos(ang_rad))
            plate_pos = pos + surf_dir * (r_eff * 0.94)
            self.add_3d_scale_plate(
                pos=plate_pos,
                outward_dir=surf_dir,
                down_dir=-tan_v,
                width=width * (1.05 - 0.22 * t),
                length=length * (1.05 - 0.18 * t),
                thickness=thickness,
                part_id=part_id,
                uv_zone=UV_ZONE_STONE,
            )

    def add_curved_horn(
        self,
        base_pos: Vector,
        base_dir: Vector,
        curve_dir: Vector,
        length: float,
        r_base: float,
        curve_rad: float = 0.65,
        rings: int = 7,
        segs: int = 7,
        ridge_amp: float = 0.07,
        bronze_collar: bool = False,
        uv_zone: tuple[float, float] = UV_ZONE_STONE,
        part_id: int = PART_HEAD_JAW,
    ):
        """
        Sweeping ribbed carved stone dragon horn/spike/fang tapering to a sharp point.
        """
        d0 = _safe_norm(base_dir)
        c0 = _safe_norm(curve_dir - d0 * d0.dot(curve_dir), Vector((0.0, -1.0, 0.0)))
        axis = _safe_norm(d0.cross(c0), Vector((1.0, 0.0, 0.0)))

        stations = []
        cur_p = base_pos.copy()
        step = length / float(max(rings - 1, 1))
        for i in range(rings):
            t = i / float(max(rings - 1, 1))
            rot_m = Matrix.Rotation(curve_rad * (t ** 1.15), 3, axis)
            tan_i = rot_m @ d0
            if i > 0:
                cur_p = cur_p + tan_i * step
            r_t = r_base * ((1.0 - t) ** 1.10)
            stations.append((cur_p.copy(), max(r_t * 0.92, 0.0022), max(r_t * 1.08, 0.0022)))

        self.add_lofted_spine(
            stations,
            segs=segs,
            up_hint=c0,
            dorsal_keel=0.22,
            ring_ridge_amp=ridge_amp,
            sharp_tip=True,
            uv_zone=uv_zone,
            part_id=part_id,
            smooth=True,
        )

        if bronze_collar and r_base >= 0.022:
            p_c0 = base_pos + d0 * (length * 0.04)
            p_c1 = base_pos + d0 * (length * 0.16)
            self.add_lofted_spine(
                [
                    (p_c0, r_base * 1.08, r_base * 1.16),
                    (p_c1, r_base * 0.98, r_base * 1.05),
                ],
                segs=segs,
                up_hint=c0,
                uv_zone=UV_ZONE_BRONZE,
                part_id=part_id,
                smooth=False,
            )

    def add_dorsal_spines(
        self,
        frames: list[tuple[Vector, Vector, Vector]],
        count: int,
        len_start: float,
        len_end: float,
        r_base: float = 0.024,
        sweep_back: float = 0.45,
        radial_offset: float = 0.0,
        part_id: int = PART_WINGS_TAIL,
    ):
        """
        Row of swept horn-like carved stone dorsal dragon spines along a curve.
        """
        if len(frames) < 2 or count < 1:
            return
        n_f = len(frames)
        for k in range(count):
            t = (k + 0.5) / float(count)
            idx_f = min(n_f - 1, max(0, int(round(t * (n_f - 1)))))
            pos, tan_v, norm_v = frames[idx_f]
            sp_len = len_start + (len_end - len_start) * t
            sp_r = r_base * (0.68 + 0.50 * math.sin(math.pi * min(1.0, t * 0.9 + 0.1)))
            dir_v = _safe_norm(norm_v - tan_v * sweep_back)
            self.add_curved_horn(
                base_pos=pos + norm_v * (radial_offset + sp_r * 0.25),
                base_dir=dir_v,
                curve_dir=-tan_v,
                length=sp_len,
                r_base=sp_r,
                curve_rad=0.36,
                rings=5,
                segs=6,
                ridge_amp=0.04,
                uv_zone=UV_ZONE_STONE,
                part_id=part_id,
            )

    def add_dragon_claw_cluster(
        self,
        wrist_pos: Vector,
        forward_dir: Vector,
        up_dir: Vector,
        palm_radius: float = 0.046,
        talon_len: float = 0.098,
        num_talons: int = 3,
        spread_deg: float = 28.0,
        curl_deg: float = 48.0,
        add_dewclaw: bool = True,
        dewclaw_side: float = -1.0,
        part_id: int = PART_WEAPON_R,
    ):
        """
        Sculpted scaly stone dragon paw/hand with curved hooked talons & inner dewclaw.
        """
        basis = _frame_from_forward_up(forward_dir, up_dir)
        x_rt = Vector((basis[0][0], basis[1][0], basis[2][0]))
        y_fw = Vector((basis[0][1], basis[1][1], basis[2][1]))
        z_up = Vector((basis[0][2], basis[1][2], basis[2][2]))

        palm_stations = [
            (wrist_pos - y_fw * (palm_radius * 0.35), palm_radius * 0.86, palm_radius * 0.66),
            (wrist_pos + y_fw * (palm_radius * 0.55), palm_radius * 1.18, palm_radius * 0.72),
            (wrist_pos + y_fw * (palm_radius * 1.15), palm_radius * 0.96, palm_radius * 0.52),
        ]
        self.add_lofted_spine(
            palm_stations,
            segs=8,
            up_hint=z_up,
            dorsal_keel=0.22,
            uv_zone=UV_ZONE_SCALES,
            part_id=part_id,
        )

        for i in range(num_talons):
            frac = (i - 0.5 * (num_talons - 1)) / max(1.0, 0.5 * max(num_talons - 1, 1))
            ang = math.radians(spread_deg * frac)
            d_finger = _safe_norm(y_fw * math.cos(ang) + x_rt * math.sin(ang) + z_up * 0.10)
            knuckle = wrist_pos + d_finger * (palm_radius * 0.96)
            mid_scale = 1.14 if abs(frac) < 0.25 else 0.92
            self.add_curved_horn(
                base_pos=knuckle,
                base_dir=d_finger,
                curve_dir=-z_up,
                length=talon_len * mid_scale,
                r_base=palm_radius * 0.35 * mid_scale,
                curve_rad=math.radians(curl_deg),
                rings=6,
                segs=6,
                ridge_amp=0.03,
                uv_zone=UV_ZONE_STONE,
                part_id=part_id,
            )

        if add_dewclaw:
            dew_dir = _safe_norm(x_rt * dewclaw_side * 0.75 - y_fw * 0.35 - z_up * 0.45)
            self.add_curved_horn(
                base_pos=wrist_pos + x_rt * (dewclaw_side * palm_radius * 0.78),
                base_dir=dew_dir,
                curve_dir=-z_up,
                length=talon_len * 0.65,
                r_base=palm_radius * 0.26,
                curve_rad=0.58,
                rings=5,
                segs=5,
                ridge_amp=0.02,
                uv_zone=UV_ZONE_STONE,
                part_id=part_id,
            )

    def add_dragon_hindleg(
        self,
        hip_pos: Vector,
        knee_pos: Vector,
        ankle_pos: Vector,
        foot_pos: Vector,
        side: float,
        thigh_r: float = 0.088,
        shin_r: float = 0.058,
        talon_len: float = 0.090,
        foot_forward: Vector = Vector((0.0, 1.0, -0.18)),
        part_id: int = PART_LOWER_BODY,
    ):
        """
        True digitigrade reptilian/draconic hindlimb (`hip -> knee -> hock/ankle -> paw`)
        with muscular osteoderm-plated thigh, backward calcaneal heel-spur, and hooked talons!
        """
        # 1. Muscular Femur + Tibia + Metatarsus continuous scaly limb tube
        leg_stations = [
            (hip_pos, thigh_r * 0.92, thigh_r * 1.08),
            (hip_pos.lerp(knee_pos, 0.52), thigh_r * 1.02, thigh_r * 1.12),
            (knee_pos, shin_r * 1.18, shin_r * 1.15),
            (knee_pos.lerp(ankle_pos, 0.55), shin_r * 0.96, shin_r * 1.04),
            (ankle_pos, shin_r * 0.88, shin_r * 0.94),
            (ankle_pos.lerp(foot_pos, 0.58), shin_r * 0.72, shin_r * 0.78),
            (foot_pos, shin_r * 0.78, shin_r * 0.68),
        ]
        self.add_lofted_spine(
            leg_stations,
            segs=10,
            up_hint=Vector((side * 0.35, 0.65, 0.65)),
            dorsal_keel=0.24,
            uv_zone=UV_ZONE_SCALES,
            v_repeats=2,
            part_id=part_id,
        )

        # 2. Overlapping 3D osteoderm armor plates along lateral thigh
        for k_p in range(2):
            f_t = 0.28 + 0.38 * k_p
            p_th = hip_pos.lerp(knee_pos, f_t) + Vector((side * thigh_r * 0.82, 0.02, 0.01))
            self.add_3d_scale_plate(
                pos=p_th,
                outward_dir=Vector((side, 0.25, 0.18)),
                down_dir=_safe_norm(knee_pos - hip_pos),
                width=thigh_r * 1.25,
                length=thigh_r * 1.45,
                thickness=0.020,
                part_id=part_id,
            )

        # 3. Sharp calcaneal hock / heel spur jutting backward from digitigrade ankle
        self.add_curved_horn(
            base_pos=ankle_pos + Vector((0.0, -shin_r * 0.55, 0.0)),
            base_dir=_safe_norm(Vector((side * 0.18, -0.92, 0.34))),
            curve_dir=Vector((0.0, 0.0, 1.0)),
            length=shin_r * 1.65,
            r_base=shin_r * 0.42,
            curve_rad=0.42,
            rings=5,
            segs=6,
            uv_zone=UV_ZONE_STONE,
            part_id=part_id,
        )

        # 4. Spread dragon hind-talons gripping the crag ledge
        self.add_dragon_claw_cluster(
            wrist_pos=foot_pos,
            forward_dir=_safe_norm(Vector((side * 0.22, foot_forward.y, foot_forward.z))),
            up_dir=Vector((0.0, 0.20, 0.98)),
            palm_radius=shin_r * 0.82,
            talon_len=talon_len,
            num_talons=3,
            spread_deg=30.0,
            curl_deg=52.0,
            add_dewclaw=True,
            dewclaw_side=-side,
            part_id=part_id,
        )

    def add_dragon_forelimb(
        self,
        shoulder_pos: Vector,
        elbow_pos: Vector,
        wrist_pos: Vector,
        claw_forward: Vector,
        claw_up: Vector,
        side: float,
        upper_r: float = 0.068,
        fore_r: float = 0.052,
        talon_len: float = 0.095,
        num_talons: int = 3,
        curl_deg: float = 50.0,
        pauldron_spike_len: float = 0.09,
        part_id: int = PART_WEAPON_R,
    ):
        """
        Anatomical scaly dragon foreleg / raptorial claw-limb (`shoulder -> elbow -> wrist -> talons`)
        with layered deltoid osteoderm plates, olecranon elbow-horn, and wicked curved talons!
        """
        arm_stations = [
            (shoulder_pos, upper_r * 0.95, upper_r * 1.06),
            (shoulder_pos.lerp(elbow_pos, 0.52), upper_r * 0.92, upper_r * 0.98),
            (elbow_pos, fore_r * 1.12, fore_r * 1.10),
            (elbow_pos.lerp(wrist_pos, 0.55), fore_r * 0.94, fore_r * 0.98),
            (wrist_pos, fore_r * 0.84, fore_r * 0.80),
        ]
        self.add_lofted_spine(
            arm_stations,
            segs=10,
            up_hint=Vector((0.0, 0.0, 1.0)),
            dorsal_keel=0.26,
            uv_zone=UV_ZONE_SCALES,
            v_repeats=2,
            part_id=part_id,
        )

        # Layered deltoid shoulder osteoderm plates + shoulder horn spike
        for k_s in range(2):
            sh_p = shoulder_pos.lerp(elbow_pos, 0.16 + 0.28 * k_s) + Vector((side * upper_r * 0.78, 0.01, 0.02))
            self.add_3d_scale_plate(
                pos=sh_p,
                outward_dir=Vector((side, 0.22, 0.35 - 0.15 * k_s)),
                down_dir=_safe_norm(elbow_pos - shoulder_pos),
                width=upper_r * 1.45,
                length=upper_r * 1.55,
                thickness=0.020,
                part_id=part_id,
            )

        if pauldron_spike_len > 0.01:
            self.add_curved_horn(
                base_pos=shoulder_pos + Vector((side * upper_r * 0.75, -0.01, upper_r * 0.35)),
                base_dir=_safe_norm(Vector((side * 0.72, -0.38, 0.58))),
                curve_dir=Vector((0.0, -1.0, 0.2)),
                length=pauldron_spike_len,
                r_base=upper_r * 0.42,
                curve_rad=0.45,
                rings=5,
                segs=6,
                uv_zone=UV_ZONE_STONE,
                part_id=part_id,
            )

        # Sharp backward olecranon elbow-spike
        self.add_curved_horn(
            base_pos=elbow_pos + Vector((side * fore_r * 0.25, -fore_r * 0.55, 0.0)),
            base_dir=_safe_norm(Vector((side * 0.28, -0.90, 0.32))),
            curve_dir=Vector((0.0, 0.0, 1.0)),
            length=fore_r * 1.85,
            r_base=fore_r * 0.44,
            curve_rad=0.38,
            rings=5,
            segs=6,
            uv_zone=UV_ZONE_STONE,
            part_id=part_id,
        )

        # Raptorial dragon paw / talons
        self.add_dragon_claw_cluster(
            wrist_pos=wrist_pos,
            forward_dir=claw_forward,
            up_dir=claw_up,
            palm_radius=fore_r * 0.88,
            talon_len=talon_len,
            num_talons=num_talons,
            spread_deg=30.0,
            curl_deg=curl_deg,
            add_dewclaw=True,
            dewclaw_side=-side,
            part_id=part_id,
        )

    def add_anatomical_dragon_skull(
        self,
        neck_pos: Vector,
        forward_dir: Vector,
        up_dir: Vector = Vector((0.0, 0.0, 1.0)),
        scale: float = 1.0,
        snout_stretch: float = 1.0,
        jaw_open_deg: float = 28.0,
        horn_len: float = 0.28,
        horn_spread_deg: float = 24.0,
        horn_curve_rad: float = 0.62,
        horn_forward_sweep: float = -0.58,
        crown_horns: int = 0,
        central_crest_horn: float = 0.0,
        underbite_tusks: bool = False,
        frill_count: int = 2,
        bronze_horn_rings: bool = False,
        eye_outset: float = 0.0,
        eye_scale: float = 1.0,
        part_id: int = PART_HEAD_JAW,
    ):
        """
        Pure Anatomical Reptile/Dragon Skull:
          - Broad temporal cranium tapering into ridged crocodilian-wyrm maxilla/snout
          - Nasal osteoderm bosses + hooked nasal horn
          - Hinged roaring mandible with chin spike + glowing runic breath-furnace maw
          - Interlocking upper & lower stone fangs (plus optional behemoth underbite tusks)
          - Fierce supraorbital brow armor overhanging glowing slit dragon eyes
          - Swept squamosal cheek-frill spikes + customizable main/crown/sovereign horns!
        """
        basis = _frame_from_forward_up(forward_dir, up_dir)
        x_rt = Vector((basis[0][0], basis[1][0], basis[2][0]))
        y_fw = Vector((basis[0][1], basis[1][1], basis[2][1]))
        z_up = Vector((basis[0][2], basis[1][2], basis[2][2]))

        s = scale
        sn = snout_stretch

        # 1. Cranium & elongated ridged reptile upper snout (+Y_local)
        skull_stations = [
            (neck_pos - y_fw * (0.045 * s) + z_up * (0.010 * s), 0.098 * s, 0.090 * s),
            (neck_pos + y_fw * (0.045 * s) + z_up * (0.032 * s), 0.116 * s, 0.102 * s),
            (neck_pos + y_fw * (0.145 * s * sn) + z_up * (0.026 * s), 0.086 * s, 0.076 * s),
            (neck_pos + y_fw * (0.245 * s * sn) + z_up * (0.018 * s), 0.066 * s, 0.056 * s),
            (neck_pos + y_fw * (0.325 * s * sn) + z_up * (0.020 * s), 0.052 * s, 0.046 * s),
            (neck_pos + y_fw * (0.365 * s * sn) + z_up * (0.004 * s), 0.024 * s, 0.022 * s),
        ]
        self.add_lofted_spine(
            skull_stations,
            segs=12,
            up_hint=z_up,
            dorsal_keel=0.42,
            ventral_flat=0.40,
            uv_zone=UV_ZONE_SCALES,
            part_id=part_id,
        )

        # Nasal bridge osteoderm plate & hooked snout-tip horn
        self.add_3d_scale_plate(
            pos=neck_pos + y_fw * (0.19 * s * sn) + z_up * (0.068 * s),
            outward_dir=z_up,
            down_dir=y_fw,
            width=0.078 * s,
            length=0.115 * s,
            thickness=0.018 * s,
            part_id=part_id,
        )
        self.add_curved_horn(
            base_pos=neck_pos + y_fw * (0.305 * s * sn) + z_up * (0.042 * s),
            base_dir=_safe_norm(z_up * 0.84 + y_fw * 0.42),
            curve_dir=-y_fw,
            length=0.082 * s,
            r_base=0.021 * s,
            curve_rad=0.48,
            rings=5,
            segs=6,
            uv_zone=UV_ZONE_STONE,
            part_id=part_id,
        )

        # 2. Hinged Roaring Mandible (Lower Jaw) + Chin Beard-Spike
        jaw_ang = math.radians(jaw_open_deg)
        jaw_fw = _safe_norm(y_fw * math.cos(jaw_ang) - z_up * math.sin(jaw_ang))
        jaw_up = _safe_norm(z_up * math.cos(jaw_ang) + y_fw * math.sin(jaw_ang))
        jaw_hinge = neck_pos + y_fw * (0.038 * s) - z_up * (0.044 * s)

        jaw_stations = [
            (jaw_hinge, 0.086 * s, 0.048 * s),
            (jaw_hinge + jaw_fw * (0.105 * s * sn), 0.068 * s, 0.042 * s),
            (jaw_hinge + jaw_fw * (0.215 * s * sn), 0.048 * s, 0.034 * s),
            (jaw_hinge + jaw_fw * (0.295 * s * sn), 0.028 * s, 0.022 * s),
        ]
        self.add_lofted_spine(
            jaw_stations,
            segs=10,
            up_hint=-jaw_up,
            dorsal_keel=0.36,
            uv_zone=UV_ZONE_SCALES,
            part_id=part_id,
        )

        # Hooked chin keel spike under mandible symphysis
        self.add_curved_horn(
            base_pos=jaw_hinge + jaw_fw * (0.24 * s * sn) - jaw_up * (0.025 * s),
            base_dir=_safe_norm(-jaw_up * 0.78 + jaw_fw * 0.45),
            curve_dir=-jaw_fw,
            length=0.065 * s,
            r_base=0.017 * s,
            curve_rad=0.40,
            rings=4,
            segs=5,
            uv_zone=UV_ZONE_STONE,
            part_id=part_id,
        )

        # Glowing Runic Breath-Furnace Core deep inside roaring jaws
        maw_pos = neck_pos + y_fw * (0.105 * s) - z_up * (0.022 * s)
        self.add_lofted_spine(
            [
                (maw_pos - y_fw * (0.03 * s), 0.046 * s, 0.032 * s),
                (maw_pos + y_fw * (0.085 * s * sn) - z_up * (0.018 * s), 0.030 * s, 0.020 * s),
            ],
            segs=8,
            up_hint=z_up,
            uv_zone=UV_ZONE_RUNES,
            part_id=part_id,
        )

        # 3. Interlocking Curved Stone Fangs (3 pairs upper + 2 pairs lower)
        for fw_t, lat_x, f_len in ((0.29, 0.036, 0.058), (0.21, 0.048, 0.046), (0.14, 0.056, 0.038)):
            for sgn in (-1.0, 1.0):
                u_fang = neck_pos + y_fw * (fw_t * s * sn) + x_rt * (sgn * lat_x * s) - z_up * (0.012 * s)
                self.add_curved_horn(
                    base_pos=u_fang,
                    base_dir=_safe_norm(-z_up * 0.94 + y_fw * 0.18),
                    curve_dir=-y_fw,
                    length=f_len * s,
                    r_base=0.013 * s,
                    curve_rad=0.28,
                    rings=4,
                    segs=5,
                    ridge_amp=0.0,
                    uv_zone=UV_ZONE_STONE,
                    part_id=part_id,
                )

        for fw_t, lat_x, f_len in ((0.25, 0.032, 0.050), (0.16, 0.044, 0.040)):
            for sgn in (-1.0, 1.0):
                l_fang = jaw_hinge + jaw_fw * (fw_t * s * sn) + x_rt * (sgn * lat_x * s) + jaw_up * (0.014 * s)
                self.add_curved_horn(
                    base_pos=l_fang,
                    base_dir=_safe_norm(jaw_up * 0.95 + jaw_fw * 0.15),
                    curve_dir=-jaw_fw,
                    length=f_len * s,
                    r_base=0.011 * s,
                    curve_rad=0.25,
                    rings=4,
                    segs=5,
                    ridge_amp=0.0,
                    uv_zone=UV_ZONE_STONE,
                    part_id=part_id,
                )

        # Optional massive upturned Behemoth Underbite Tusks (`rook`)
        if underbite_tusks:
            for sgn in (-1.0, 1.0):
                tusk_base = jaw_hinge + jaw_fw * (0.24 * s * sn) + x_rt * (sgn * 0.048 * s) + jaw_up * (0.010 * s)
                self.add_curved_horn(
                    base_pos=tusk_base,
                    base_dir=_safe_norm(jaw_up * 0.85 + jaw_fw * 0.35 + x_rt * (sgn * 0.32)),
                    curve_dir=z_up,
                    length=0.125 * s,
                    r_base=0.024 * s,
                    curve_rad=0.55,
                    rings=5,
                    segs=6,
                    uv_zone=UV_ZONE_STONE,
                    part_id=part_id,
                )

        # 4. Fierce Supraorbital Brow Ridges, Glowing Slit Eyes, Frill Spikes & Main Horns
        for sgn in (-1.0, 1.0):
            # Armored supraorbital brow ridge
            brow_p = (
                neck_pos
                + y_fw * (0.115 * s * sn)
                + x_rt * (sgn * (0.072 + eye_outset * 0.45) * s)
                + z_up * ((0.058 + eye_outset * 0.25) * s)
            )
            self.add_3d_scale_plate(
                pos=brow_p,
                outward_dir=_safe_norm(x_rt * (sgn * 0.65) + z_up * 0.72),
                down_dir=y_fw,
                width=0.052 * s,
                length=0.095 * s,
                thickness=0.018 * s,
                part_id=part_id,
            )

            # Glowing Runic Slit Dragon Eye tucked beneath brow armor
            eye_pos = (
                neck_pos
                + y_fw * ((0.115 + (0.006 if eye_outset > 0.0 else 0.0)) * s * sn)
                + x_rt * (sgn * (0.076 + eye_outset) * s)
                + z_up * (0.035 * s)
            )
            es = eye_scale
            if es > 1.05 or eye_outset > 0.0:
                self.add_lofted_spine(
                    [
                        (eye_pos - y_fw * (0.031 * s * 1.15), 0.006 * s * es, 0.0045 * s * es),
                        (eye_pos + x_rt * (sgn * 0.004 * s), 0.017 * s * es, 0.0098 * s * es),
                        (eye_pos + y_fw * (0.034 * s * 1.15), 0.0055 * s * es, 0.0038 * s * es),
                    ],
                    segs=10,
                    up_hint=z_up,
                    uv_zone=UV_ZONE_RUNES,
                    part_id=part_id,
                )
            else:
                self.add_lofted_spine(
                    [
                        (eye_pos - y_fw * (0.026 * s), 0.015 * s, 0.011 * s),
                        (eye_pos + y_fw * (0.028 * s), 0.013 * s, 0.009 * s),
                    ],
                    segs=6,
                    up_hint=z_up,
                    uv_zone=UV_ZONE_RUNES,
                    part_id=part_id,
                )

            # Squamosal / jugal cheek-frill horns
            for f_i in range(frill_count):
                f_frac = f_i / float(max(frill_count - 1, 1)) if frill_count > 1 else 0.0
                cheek_base = (
                    neck_pos
                    + y_fw * ((0.025 - 0.03 * f_frac) * s)
                    + x_rt * (sgn * (0.096 - 0.01 * f_frac) * s)
                    + z_up * ((-0.022 + 0.045 * f_frac) * s)
                )
                self.add_curved_horn(
                    base_pos=cheek_base,
                    base_dir=_safe_norm(-y_fw * 0.72 + x_rt * (sgn * 0.60) + z_up * (-0.10 + 0.38 * f_frac)),
                    curve_dir=z_up,
                    length=(0.115 + 0.025 * f_frac) * s,
                    r_base=0.022 * s,
                    curve_rad=0.35,
                    rings=4,
                    segs=6,
                    uv_zone=UV_ZONE_STONE,
                    part_id=part_id,
                )

            # Primary Swept Ribbed Stone Dragon Horns
            sp_rad = math.radians(horn_spread_deg)
            h_base = neck_pos + y_fw * (0.025 * s) + x_rt * (sgn * 0.068 * s) + z_up * (0.068 * s)
            h_dir = _safe_norm(y_fw * horn_forward_sweep + z_up * 0.74 + x_rt * (sgn * math.sin(sp_rad)))
            self.add_curved_horn(
                base_pos=h_base,
                base_dir=h_dir,
                curve_dir=z_up if horn_forward_sweep < 0.0 else y_fw,
                length=horn_len * s,
                r_base=0.040 * s,
                curve_rad=horn_curve_rad,
                rings=8,
                segs=8,
                ridge_amp=0.07,
                bronze_collar=bronze_horn_rings,
                uv_zone=UV_ZONE_STONE,
                part_id=part_id,
            )

            # Secondary outer/upper crown horns (for 4-horned Elder Queen / Sovereign King)
            if crown_horns >= 2:
                h2_base = neck_pos - y_fw * (0.015 * s) + x_rt * (sgn * 0.088 * s) + z_up * (0.048 * s)
                h2_dir = _safe_norm(-y_fw * 0.68 + z_up * 0.48 + x_rt * (sgn * math.sin(sp_rad * 1.45)))
                self.add_curved_horn(
                    base_pos=h2_base,
                    base_dir=h2_dir,
                    curve_dir=z_up,
                    length=horn_len * 0.76 * s,
                    r_base=0.029 * s,
                    curve_rad=horn_curve_rad * 0.85,
                    rings=7,
                    segs=7,
                    ridge_amp=0.06,
                    uv_zone=UV_ZONE_STONE,
                    part_id=part_id,
                )

        # Central Sovereign Crown-Horn Crest (`king`)
        if central_crest_horn > 0.01:
            c_base = neck_pos + y_fw * (0.035 * s) + z_up * (0.082 * s)
            self.add_curved_horn(
                base_pos=c_base,
                base_dir=_safe_norm(-y_fw * 0.32 + z_up * 0.94),
                curve_dir=-y_fw,
                length=central_crest_horn * s,
                r_base=0.036 * s,
                curve_rad=0.45,
                rings=7,
                segs=7,
                ridge_amp=0.08,
                bronze_collar=bronze_horn_rings,
                uv_zone=UV_ZONE_STONE,
                part_id=part_id,
            )

            # Secondary outer/upper crown horns (for 4-horned Elder Queen / Sovereign King)
            if crown_horns >= 2:
                h2_base = neck_pos - y_fw * (0.015 * s) + x_rt * (sgn * 0.088 * s) + z_up * (0.048 * s)
                h2_dir = _safe_norm(-y_fw * 0.68 + z_up * 0.48 + x_rt * (sgn * math.sin(sp_rad * 1.45)))
                self.add_curved_horn(
                    base_pos=h2_base,
                    base_dir=h2_dir,
                    curve_dir=z_up,
                    length=horn_len * 0.76 * s,
                    r_base=0.029 * s,
                    curve_rad=horn_curve_rad * 0.85,
                    rings=7,
                    segs=7,
                    ridge_amp=0.06,
                    uv_zone=UV_ZONE_STONE,
                    part_id=part_id,
                )

        # Central Sovereign Crown-Horn Crest (`king`)
        if central_crest_horn > 0.01:
            c_base = neck_pos + y_fw * (0.035 * s) + z_up * (0.082 * s)
            self.add_curved_horn(
                base_pos=c_base,
                base_dir=_safe_norm(-y_fw * 0.32 + z_up * 0.94),
                curve_dir=-y_fw,
                length=central_crest_horn * s,
                r_base=0.036 * s,
                curve_rad=0.45,
                rings=7,
                segs=7,
                ridge_amp=0.08,
                bronze_collar=bronze_horn_rings,
                uv_zone=UV_ZONE_STONE,
                part_id=part_id,
            )

    # ==========================================================================
    # CARVED STONE DRAGON WINGS & ANATOMICAL TAILS (`PART_WINGS_TAIL = 6`)
    # ==========================================================================
    def add_wing_membrane_panel(
        self,
        curve_a: list[Vector],
        curve_b: list[Vector],
        scallop_depth: float = 0.085,
        billow_back: float = 0.028,
        thick_base: float = 0.018,
        sub_w: int = 4,
        u_offset: float = 0.18,
        part_id: int = PART_WINGS_TAIL,
    ):
        """
        Solid, double-sided watertight carved stone wing-membrane web spanning
        between adjacent wing-finger ribs `curve_a` and `curve_b`, with isotropic
        1:1 carved-stone UVs and a Gothic scalloped trailing arch.
        """
        m_pts = min(len(curve_a), len(curve_b))
        if m_pts < 2:
            return

        ca = [p.copy() for p in curve_a[:m_pts]]
        cb = [p.copy() for p in curve_b[:m_pts]]
        ca[0] = ca[0].lerp(ca[1], 0.16)
        cb[0] = cb[0].lerp(cb[1], 0.16)

        v_lo, v_hi = _zone_v_bounds(UV_ZONE_STONE)
        root_mid = ca[0].lerp(cb[0], 0.5)

        grid_p: list[list[Vector]] = []
        for i in range(m_pts):
            ti = i / float(m_pts - 1)
            row_p = []
            for j in range(sub_w + 1):
                sj = 0.02 + 0.96 * (j / float(sub_w))
                arch = 4.0 * sj * (1.0 - sj)
                p = ca[i].lerp(cb[i], sj)
                to_root = _safe_norm(root_mid - p, Vector((0.0, 0.0, 1.0)))
                p = p + to_root * (scallop_depth * (ti ** 1.85) * arch)
                p = p + Vector((0.0, -billow_back * arch * math.sin(math.pi * ti), 0.0))
                row_p.append(p)
            grid_p.append(row_p)

        front_v = []
        back_v = []
        for i in range(m_pts):
            ti = i / float(m_pts - 1)
            half_th = 0.5 * thick_base * (1.0 - 0.45 * ti)
            vc = _pingpong_v(ti, v_lo, v_hi, repeats=3)
            f_row = []
            b_row = []
            for j in range(sub_w + 1):
                i0, i1 = max(0, i - 1), min(m_pts - 1, i + 1)
                j0, j1 = max(0, j - 1), min(sub_w, j + 1)
                dp_dt = grid_p[i1][j] - grid_p[i0][j]
                dp_ds = grid_p[i][j1] - grid_p[i][j0]
                nrm = _safe_norm(dp_dt.cross(dp_ds), Vector((0.0, 1.0, 0.0)))
                uc = min(0.98, max(0.02, (u_offset + 0.14 * (j / float(sub_w))) % 0.96))
                f_row.append((self._new_vert(grid_p[i][j] + nrm * half_th, part_id), (uc, vc)))
                b_row.append((self._new_vert(grid_p[i][j] - nrm * half_th, part_id), (uc, vc)))
            front_v.append(f_row)
            back_v.append(b_row)

        for i in range(m_pts - 1):
            for j in range(sub_w):
                a00, uv00 = front_v[i][j]
                a10, uv10 = front_v[i + 1][j]
                a11, uv11 = front_v[i + 1][j + 1]
                a01, uv01 = front_v[i][j + 1]
                self._add_face([a00, a10, a11, a01], [uv00, uv10, uv11, uv01], smooth=True)

                b00, buv00 = back_v[i][j]
                b10, buv10 = back_v[i + 1][j]
                b11, buv11 = back_v[i + 1][j + 1]
                b01, buv01 = back_v[i][j + 1]
                self._add_face([b00, b01, b11, b10], [buv00, buv01, buv11, buv10], smooth=True)

        # Seal all 4 perimeter boundaries so every wing web is 100% watertight 2-manifold
        for j in range(sub_w):
            self._add_face(
                [front_v[0][j][0], front_v[0][j + 1][0], back_v[0][j + 1][0], back_v[0][j][0]],
                [front_v[0][j][1], front_v[0][j + 1][1], back_v[0][j + 1][1], back_v[0][j][1]],
                smooth=False,
            )
            il = m_pts - 1
            self._add_face(
                [front_v[il][j + 1][0], front_v[il][j][0], back_v[il][j][0], back_v[il][j + 1][0]],
                [front_v[il][j + 1][1], front_v[il][j][1], back_v[il][j][1], back_v[il][j + 1][1]],
                smooth=False,
            )
        for i in range(m_pts - 1):
            self._add_face(
                [front_v[i + 1][0][0], front_v[i][0][0], back_v[i][0][0], back_v[i + 1][0][0]],
                [front_v[i + 1][0][1], front_v[i][0][1], back_v[i][0][1], back_v[i + 1][0][1]],
                smooth=False,
            )
            jr = sub_w
            self._add_face(
                [front_v[i][jr][0], front_v[i + 1][jr][0], back_v[i + 1][jr][0], back_v[i][jr][0]],
                [front_v[i][jr][1], front_v[i + 1][jr][1], back_v[i + 1][jr][1], back_v[i][jr][1]],
                smooth=False,
            )

    def add_dragon_wing(
        self,
        shoulder_pos: Vector,
        side: float,
        wrist_pos: Vector,
        outer_tip: Vector,
        inner_tip: Vector,
        flank_anchor: Vector,
        num_fingers: int = 4,
        spar_r: float = 0.038,
        scallop_depth: float = 0.085,
        sub_w: int = 4,
        part_id: int = PART_WINGS_TAIL,
    ):
        """
        Complete Anatomical Carved-Stone Dragon Wing (`side` = +1.0 right, -1.0 left):
          - Muscular humerus -> elbow -> radius/ulna wing-arm spar (`UV_ZONE_SCALES`)
          - Hooked stone thumb-claw at the wing-wrist apex
          - `num_fingers` radiating curved stone phalanx ribs
          - Scalloped solid stone inter-digital webs + inner plagiopatagium flank web!
        """
        elbow_mid = shoulder_pos.lerp(wrist_pos, 0.46) + Vector((side * 0.03, -0.055, -0.045))

        arm_stations = []
        n_arm = 6
        for i in range(n_arm):
            t = i / float(n_arm - 1)
            p = ((1.0 - t) ** 2) * shoulder_pos + 2.0 * (1.0 - t) * t * elbow_mid + (t ** 2) * wrist_pos
            r_cur = spar_r * (1.14 - 0.30 * t)
            arm_stations.append((p, r_cur * 0.88, r_cur * 1.12))

        self.add_lofted_spine(
            arm_stations,
            segs=8,
            up_hint=Vector((0.0, 0.0, 1.0)),
            dorsal_keel=0.32,
            uv_zone=UV_ZONE_SCALES,
            part_id=part_id,
        )

        # Hooked stone thumb-claw at wrist apex
        self.add_curved_horn(
            base_pos=wrist_pos,
            base_dir=_safe_norm(Vector((side * 0.28, 0.48, 0.82))),
            curve_dir=Vector((0.0, 1.0, -0.35)),
            length=spar_r * 3.15,
            r_base=spar_r * 0.60,
            curve_rad=0.68,
            rings=5,
            segs=6,
            uv_zone=UV_ZONE_STONE,
            part_id=part_id,
        )

        # Radiating curved stone wing-finger ribs
        n_rib_pts = 7
        finger_curves: list[list[Vector]] = []
        for f_idx in range(num_fingers):
            frac = f_idx / float(max(num_fingers - 1, 1))
            tip_pos = outer_tip.lerp(inner_tip, frac ** 0.92)
            ctrl_pos = wrist_pos.lerp(tip_pos, 0.46) + Vector((
                side * 0.042 * (1.0 - 0.55 * frac),
                -0.042,
                0.068 * (1.0 - 0.65 * frac),
            ))
            curve_pts = []
            rib_stations = []
            for i in range(n_rib_pts):
                t = i / float(n_rib_pts - 1)
                p = ((1.0 - t) ** 2) * wrist_pos + 2.0 * (1.0 - t) * t * ctrl_pos + (t ** 2) * tip_pos
                curve_pts.append(p)
                rr = spar_r * 0.56 * ((1.0 - 0.78 * t) ** 0.95)
                rib_stations.append((p, rr, rr * 1.15))

            self.add_lofted_spine(
                rib_stations,
                segs=6,
                up_hint=Vector((0.0, 0.0, 1.0)),
                dorsal_keel=0.25,
                sharp_tip=True,
                uv_zone=UV_ZONE_STONE,
                part_id=part_id,
            )
            finger_curves.append(curve_pts)

        # Inter-digital scalloped membrane panels (sliced `[1:]` to prevent wrist apex pinch)
        for f_idx in range(num_fingers - 1):
            self.add_wing_membrane_panel(
                finger_curves[f_idx][1:],
                finger_curves[f_idx + 1][1:],
                scallop_depth=scallop_depth,
                billow_back=0.025,
                thick_base=spar_r * 0.46,
                sub_w=sub_w,
                u_offset=0.12 + 0.19 * f_idx + (0.07 if side < 0 else 0.0),
                part_id=part_id,
            )

        # Inner plagiopatagium membrane connecting innermost finger to dragon flank
        flank_curve = []
        for i in range(n_rib_pts):
            t = i / float(n_rib_pts - 1)
            flank_curve.append(shoulder_pos.lerp(flank_anchor, t ** 0.88))
        self.add_wing_membrane_panel(
            finger_curves[-1][1:],
            flank_curve[1:],
            scallop_depth=scallop_depth * 0.65,
            billow_back=0.018,
            thick_base=spar_r * 0.44,
            sub_w=max(2, sub_w - 1),
            u_offset=0.72 + (0.06 if side < 0 else 0.0),
            part_id=part_id,
        )

    def add_anatomical_dragon_tail(
        self,
        ctrl_pts: tuple[Vector, Vector, Vector, Vector],
        r_base: float = 0.088,
        r_tip: float = 0.022,
        n_stations: int = 14,
        spine_count: int = 7,
        tip_style: str = "spade",
        part_id: int = PART_WINGS_TAIL,
    ):
        """
        Sweeping 3D S-curved muscular stone dragon tail with dorsal spines and
        breed-distinctive weaponized tail crest (`barbed`, `club`, `spade`, `fin`, `ribbon`, `mace`).
        """
        p0, p1, p2, p3 = ctrl_pts
        stations = []
        for i in range(n_stations):
            t = i / float(n_stations - 1)
            pt = _cubic_bezier(p0, p1, p2, p3, t)
            r_cur = r_base * ((1.0 - t) ** 0.78) + r_tip * (t ** 0.78)
            stations.append((pt, r_cur * 0.94, r_cur * 1.08))

        frames = self.add_lofted_spine(
            stations,
            segs=10,
            up_hint=Vector((0.0, 0.0, 1.0)),
            dorsal_keel=0.35,
            ventral_flat=0.22,
            sharp_tip=(tip_style in ("barbed", "pointed")),
            uv_zone=UV_ZONE_SCALES,
            v_repeats=3,
            part_id=part_id,
        )

        self.add_dorsal_spines(
            frames[1:-2],
            count=spine_count,
            len_start=r_base * 0.95,
            len_end=r_base * 0.48,
            r_base=r_base * 0.28,
            sweep_back=0.52,
            radial_offset=r_base * 0.32,
            part_id=part_id,
        )

        tip_pos, tip_tan, tip_norm = frames[-1]
        tip_right = _safe_norm(tip_norm.cross(tip_tan))

        if tip_style == "barbed":
            # Scorpion-drake barbed stinger + twin lateral barbs
            for sgn in (-1.0, 1.0):
                self.add_curved_horn(
                    base_pos=frames[-3][0],
                    base_dir=_safe_norm(tip_tan * 0.62 + tip_right * (sgn * 0.72) + tip_norm * 0.25),
                    curve_dir=-tip_tan,
                    length=r_base * 1.15,
                    r_base=r_base * 0.26,
                    curve_rad=0.45,
                    rings=4,
                    segs=5,
                    part_id=part_id,
                )
        elif tip_style == "club":
            # Heavy Ankylosaur Fortress Earth-Drake Stone Tail-Club with 6 jutting spikes!
            club_c = tip_pos + tip_tan * 0.035
            club_stations = [
                (tip_pos - tip_tan * 0.04, 0.042, 0.038),
                (club_c, 0.098, 0.072),
                (club_c + tip_tan * 0.075, 0.088, 0.064),
                (club_c + tip_tan * 0.125, 0.038, 0.032),
            ]
            self.add_lofted_spine(
                club_stations,
                segs=10,
                up_hint=tip_norm,
                dorsal_keel=0.25,
                uv_zone=UV_ZONE_STONE,
                part_id=part_id,
                smooth=False,
            )
            for k_sp in range(6):
                a_sp = (k_sp / 6.0) * 2.0 * math.pi
                sp_dir = _safe_norm(tip_right * math.cos(a_sp) + tip_norm * math.sin(a_sp) * 0.8 + tip_tan * 0.28)
                self.add_curved_horn(
                    base_pos=club_c + tip_tan * 0.03 + sp_dir * 0.055,
                    base_dir=sp_dir,
                    curve_dir=tip_tan,
                    length=0.085,
                    r_base=0.026,
                    curve_rad=0.22,
                    rings=4,
                    segs=6,
                    part_id=part_id,
                )
        elif tip_style in ("spade", "ribbon"):
            # Aerodynamic diamond Wyvern Spade-Blade or Tri-Finned Celestial Ribbon-Lance
            basis = _frame_from_forward_up(tip_tan, tip_norm)
            sp_poly = [(0.0, -0.012), (0.068, 0.0), (0.0, 0.016), (-0.068, 0.0)]
            sp_slices = [
                (-0.02, 0.35, 0.8, 0.0, 0.0),
                (0.05, 1.05, 1.0, 0.0, 0.0),
                (0.12, 0.65, 0.8, 0.0, 0.0),
                (0.18, 0.08, 0.2, 0.0, 0.0),
            ]
            self.add_lofted_polygon(
                sp_poly,
                sp_slices,
                origin=tip_pos,
                basis=Euler((math.pi * 0.5, 0.0, 0.0)).to_matrix() if False else Matrix((
                    (tip_right.x, tip_norm.x, tip_tan.x),
                    (tip_right.y, tip_norm.y, tip_tan.y),
                    (tip_right.z, tip_norm.z, tip_tan.z),
                )),
                sharp_end=True,
                uv_zone=UV_ZONE_STONE,
                part_id=part_id,
                smooth=False,
            )
            if tip_style == "ribbon":
                for sgn in (-1.0, 1.0):
                    self.add_curved_horn(
                        base_pos=tip_pos + tip_right * (sgn * 0.025),
                        base_dir=_safe_norm(tip_tan * 0.72 + tip_right * (sgn * 0.62) + tip_norm * 0.22),
                        curve_dir=-tip_tan,
                        length=0.14,
                        r_base=0.018,
                        curve_rad=0.42,
                        rings=5,
                        segs=5,
                        part_id=part_id,
                    )
        elif tip_style == "fin":
            # Flared 3-spined Arcane Sea-Wyrm Caudal Fin (`bishop`)
            for f_ang in (-0.52, 0.0, 0.52):
                f_dir = _safe_norm(tip_tan * 0.78 + tip_right * math.sin(f_ang) * 0.75 + tip_norm * 0.28)
                self.add_curved_horn(
                    base_pos=tip_pos,
                    base_dir=f_dir,
                    curve_dir=tip_norm,
                    length=0.15 if abs(f_ang) < 0.1 else 0.125,
                    r_base=0.020,
                    curve_rad=0.32,
                    rings=5,
                    segs=6,
                    uv_zone=UV_ZONE_RUNES if abs(f_ang) < 0.1 else UV_ZONE_STONE,
                    part_id=part_id,
                )
        elif tip_style == "mace":
            # Bifurcated Spiked Battle-Mace Tail Crest (`king`)
            self.add_curved_horn(
                base_pos=tip_pos,
                base_dir=tip_tan,
                curve_dir=tip_norm,
                length=0.145,
                r_base=0.032,
                curve_rad=0.28,
                rings=5,
                segs=6,
                part_id=part_id,
            )
            for sgn in (-1.0, 1.0):
                for z_s in (-0.35, 0.45):
                    self.add_curved_horn(
                        base_pos=tip_pos - tip_tan * 0.02,
                        base_dir=_safe_norm(tip_tan * 0.52 + tip_right * (sgn * 0.75) + tip_norm * z_s),
                        curve_dir=-tip_tan,
                        length=0.105,
                        r_base=0.022,
                        curve_rad=0.35,
                        rings=4,
                        segs=5,
                        part_id=part_id,
                    )


# ==============================================================================
# 6 PURE ANATOMICAL CARVED-STONE DRAGON BREEDS
# ==============================================================================
def _sculpt_pawn(sc: DragonSculptor):
    """
    1. PAWN (1.08m) — 幼竜ドレイク (Quadruped Stone Hatchling Prowler):
       Low, feral 4-legged gargoyle drake crouched on a jagged slate rock,
       lunging forward (+Y) with raised right striking claw & flared bat-wings!
    """
    sc.add_jagged_stone_crag(seed=11, max_r=0.425, crag_h=0.195, spire_bias_y=0.02)

    # PART_LOWER_BODY: Crouched muscular pelvis & digitigrade hindlegs gripping slate crag
    pelvis_stations = [
        (Vector((0.0, -0.22, 0.36)), 0.085, 0.082),
        (Vector((0.0, -0.11, 0.41)), 0.112, 0.105),
        (Vector((0.0, -0.01, 0.44)), 0.118, 0.112),
    ]
    sc.add_lofted_spine(pelvis_stations, segs=12, dorsal_keel=0.28, uv_zone=UV_ZONE_SCALES, part_id=PART_LOWER_BODY)

    for sgn in (-1.0, 1.0):
        sc.add_dragon_hindleg(
            hip_pos=Vector((sgn * 0.105, -0.14, 0.39)),
            knee_pos=Vector((sgn * 0.175, -0.02, 0.33)),
            ankle_pos=Vector((sgn * 0.195, -0.20, 0.27)),
            foot_pos=Vector((sgn * 0.185, -0.10, 0.175)),
            side=sgn,
            thigh_r=0.072,
            shin_r=0.048,
            talon_len=0.078,
            part_id=PART_LOWER_BODY,
        )

    # PART_UPPER_BODY: Arched predatory spine, osteoderm-plated ribcage & lunging neck
    torso_pts = [
        (Vector((0.0, -0.02, 0.44)), 0.116, 0.112),
        (Vector((0.0, 0.08, 0.49)), 0.132, 0.126),
        (Vector((0.0, 0.16, 0.54)), 0.122, 0.118),
        (Vector((0.0, 0.21, 0.61)), 0.092, 0.095),
        (Vector((0.0, 0.23, 0.69)), 0.078, 0.082),
    ]
    t_frames = sc.add_lofted_spine(
        torso_pts, segs=12, dorsal_keel=0.34, ventral_flat=0.18, uv_zone=UV_ZONE_SCALES, v_repeats=2, part_id=PART_UPPER_BODY
    )
    sc.add_spine_osteoderms(
        t_frames, [(p[1], p[2]) for p in torso_pts], count=5, width=0.095, length=0.105, thickness=0.020, part_id=PART_UPPER_BODY
    )
    sc.add_dorsal_spines(
        t_frames[:-1], count=5, len_start=0.075, len_end=0.055, r_base=0.020, radial_offset=0.075, part_id=PART_UPPER_BODY
    )

    # PART_WEAPON_R (+X): Raised / lunging right clawed forelimb (Z >= 0.22m!)
    sc.add_dragon_forelimb(
        shoulder_pos=Vector((0.125, 0.13, 0.52)),
        elbow_pos=Vector((0.205, 0.06, 0.44)),
        wrist_pos=Vector((0.195, 0.29, 0.34)),
        claw_forward=Vector((-0.15, 0.92, -0.32)),
        claw_up=Vector((0.25, 0.30, 0.92)),
        side=1.0,
        upper_r=0.058,
        fore_r=0.045,
        talon_len=0.088,
        num_talons=3,
        curl_deg=54.0,
        pauldron_spike_len=0.075,
        part_id=PART_WEAPON_R,
    )

    # PART_SHIELD_L (-X): Braced left clawed forelimb gripping front-left crag rock (Z >= 0.175m!)
    sc.add_dragon_forelimb(
        shoulder_pos=Vector((-0.125, 0.13, 0.50)),
        elbow_pos=Vector((-0.205, 0.05, 0.38)),
        wrist_pos=Vector((-0.195, 0.22, 0.195)),
        claw_forward=Vector((0.12, 0.95, -0.22)),
        claw_up=Vector((0.0, 0.22, 0.97)),
        side=-1.0,
        upper_r=0.058,
        fore_r=0.045,
        talon_len=0.082,
        num_talons=3,
        curl_deg=48.0,
        pauldron_spike_len=0.075,
        part_id=PART_SHIELD_L,
    )

    # PART_HEAD_JAW: Fierce snarling horned hatchling reptile skull facing +Y
    sc.add_anatomical_dragon_skull(
        neck_pos=Vector((0.0, 0.23, 0.70)),
        forward_dir=Vector((0.0, 0.96, -0.24)),
        up_dir=Vector((0.0, 0.24, 0.96)),
        scale=0.82,
        snout_stretch=0.95,
        jaw_open_deg=30.0,
        horn_len=0.25,
        horn_spread_deg=26.0,
        horn_curve_rad=0.58,
        frill_count=2,
        part_id=PART_HEAD_JAW,
    )

    # PART_WINGS_TAIL: Flared juvenile bat-wings soaring to 1.08m + S-curved barbed tail
    for sgn in (-1.0, 1.0):
        sc.add_dragon_wing(
            shoulder_pos=Vector((sgn * 0.095, 0.06, 0.57)),
            side=sgn,
            wrist_pos=Vector((sgn * 0.33, -0.06, 1.04)),
            outer_tip=Vector((sgn * 0.46, -0.24, 1.08)),
            inner_tip=Vector((sgn * 0.18, -0.28, 0.48)),
            flank_anchor=Vector((sgn * 0.09, -0.14, 0.44)),
            num_fingers=4,
            spar_r=0.032,
            scallop_depth=0.072,
            sub_w=3,
            part_id=PART_WINGS_TAIL,
        )

    sc.add_anatomical_dragon_tail(
        ctrl_pts=(
            Vector((0.0, -0.20, 0.37)),
            Vector((0.06, -0.44, 0.28)),
            Vector((0.32, -0.42, 0.24)),
            Vector((0.38, -0.16, 0.34)),
        ),
        r_base=0.068,
        r_tip=0.016,
        n_stations=13,
        spine_count=6,
        tip_style="barbed",
        part_id=PART_WINGS_TAIL,
    )


def _sculpt_rook(sc: DragonSculptor):
    """
    2. ROOK (1.38m) — 重装鎧地竜 (Quadruped Armored Behemoth Earth-Drake):
       Colossal wide-stanced quadrupedal ankylosaur/tortoise-drake fortress dragon!
       Heavy overlapping carapace armor, spiked pauldrons, tusked battering-ram skull,
       armored dorsal wing-pinions, and a massive 6-spiked stone club-tail! ZERO castle tower!
    """
    sc.add_jagged_stone_crag(seed=23, max_r=0.455, crag_h=0.21, spire_bias_y=-0.01, slab_tilt=(0.08, 0.11, -0.18))

    # PART_LOWER_BODY: Massive wide pelvis & pillar-thick armored hindlegs
    pelvis_pts = [
        (Vector((0.0, -0.25, 0.46)), 0.155, 0.135),
        (Vector((0.0, -0.12, 0.54)), 0.205, 0.168),
        (Vector((0.0, 0.00, 0.58)), 0.220, 0.182),
    ]
    p_frames = sc.add_lofted_spine(pelvis_pts, segs=14, dorsal_keel=0.30, ventral_flat=0.28, uv_zone=UV_ZONE_SCALES, part_id=PART_LOWER_BODY)
    sc.add_spine_osteoderms(p_frames, [(p[1], p[2]) for p in pelvis_pts], count=3, width=0.16, length=0.14, thickness=0.028, part_id=PART_LOWER_BODY)

    for sgn in (-1.0, 1.0):
        sc.add_dragon_hindleg(
            hip_pos=Vector((sgn * 0.175, -0.16, 0.50)),
            knee_pos=Vector((sgn * 0.255, -0.05, 0.39)),
            ankle_pos=Vector((sgn * 0.265, -0.21, 0.29)),
            foot_pos=Vector((sgn * 0.245, -0.12, 0.185)),
            side=sgn,
            thigh_r=0.096,
            shin_r=0.068,
            talon_len=0.088,
            part_id=PART_LOWER_BODY,
        )

    # PART_UPPER_BODY: Colossal humped Ankylosaur-Drake Carapace & bull-dragon neck
    torso_pts = [
        (Vector((0.0, -0.02, 0.58)), 0.225, 0.188),
        (Vector((0.0, 0.08, 0.66)), 0.245, 0.212),
        (Vector((0.0, 0.16, 0.72)), 0.220, 0.195),
        (Vector((0.0, 0.22, 0.79)), 0.158, 0.152),
        (Vector((0.0, 0.24, 0.87)), 0.122, 0.122),
    ]
    t_frames = sc.add_lofted_spine(
        torso_pts, segs=14, dorsal_keel=0.38, ventral_flat=0.25, uv_zone=UV_ZONE_SCALES, v_repeats=2, part_id=PART_UPPER_BODY
    )
    # Central & twin lateral rows of heavy 3D carapace osteoderm armor plates!
    for lat_deg in (-42.0, 0.0, 42.0):
        sc.add_spine_osteoderms(
            t_frames[:-1],
            [(p[1], p[2]) for p in torso_pts[:-1]],
            count=4,
            width=0.155,
            length=0.145,
            thickness=0.032,
            lateral_angle_deg=lat_deg,
            part_id=PART_UPPER_BODY,
        )
    sc.add_dorsal_spines(
        t_frames[:-1], count=5, len_start=0.14, len_end=0.10, r_base=0.034, sweep_back=0.32, radial_offset=0.16, part_id=PART_UPPER_BODY
    )

    # PART_WEAPON_R & PART_SHIELD_L: Heavy armored earth-crushing forelimbs + giant spiked shoulder-plates (paws Z >= 0.18m)
    for sgn, pid in ((1.0, PART_WEAPON_R), (-1.0, PART_SHIELD_L)):
        sc.add_dragon_forelimb(
            shoulder_pos=Vector((sgn * 0.195, 0.14, 0.66)),
            elbow_pos=Vector((sgn * 0.285, 0.06, 0.48)),
            wrist_pos=Vector((sgn * 0.255, 0.21, 0.195)),
            claw_forward=Vector((-sgn * 0.08, 0.96, -0.20)),
            claw_up=Vector((0.0, 0.20, 0.98)),
            side=sgn,
            upper_r=0.086,
            fore_r=0.068,
            talon_len=0.095,
            num_talons=3,
            curl_deg=46.0,
            pauldron_spike_len=0.145,
            part_id=pid,
        )
        # Secondary lower shoulder spike for fortress-behemoth silhouette
        sc.add_curved_horn(
            base_pos=Vector((sgn * 0.255, 0.13, 0.58)),
            base_dir=_safe_norm(Vector((sgn * 0.88, 0.18, 0.42))),
            curve_dir=Vector((0.0, 0.0, 1.0)),
            length=0.125,
            r_base=0.034,
            curve_rad=0.32,
            rings=5,
            segs=6,
            part_id=pid,
        )

    # PART_HEAD_JAW: Colossal Battering-Ram Dragon Skull with forward bull-horns & upturned underbite tusks!
    sc.add_anatomical_dragon_skull(
        neck_pos=Vector((0.0, 0.23, 0.88)),
        forward_dir=Vector((0.0, 0.97, -0.22)),
        up_dir=Vector((0.0, 0.22, 0.97)),
        scale=1.06,
        snout_stretch=0.88,
        jaw_open_deg=26.0,
        horn_len=0.30,
        horn_spread_deg=36.0,
        horn_curve_rad=0.82,
        horn_forward_sweep=-0.22,
        underbite_tusks=True,
        frill_count=2,
        part_id=PART_HEAD_JAW,
    )

    # PART_WINGS_TAIL: Rugged armored dorsal wing-pinions rising to 1.38m + massive 6-spiked Ankylosaur Club-Tail!
    for sgn in (-1.0, 1.0):
        sc.add_dragon_wing(
            shoulder_pos=Vector((sgn * 0.14, 0.02, 0.76)),
            side=sgn,
            wrist_pos=Vector((sgn * 0.36, -0.10, 1.33)),
            outer_tip=Vector((sgn * 0.48, -0.25, 1.38)),
            inner_tip=Vector((sgn * 0.22, -0.28, 0.68)),
            flank_anchor=Vector((sgn * 0.15, -0.18, 0.58)),
            num_fingers=3,
            spar_r=0.044,
            scallop_depth=0.068,
            sub_w=3,
            part_id=PART_WINGS_TAIL,
        )

    sc.add_anatomical_dragon_tail(
        ctrl_pts=(
            Vector((0.0, -0.24, 0.48)),
            Vector((-0.12, -0.48, 0.36)),
            Vector((-0.38, -0.40, 0.30)),
            Vector((-0.40, -0.12, 0.38)),
        ),
        r_base=0.098,
        r_tip=0.042,
        n_stations=13,
        spine_count=6,
        tip_style="club",
        part_id=PART_WINGS_TAIL,
    )


def _sculpt_knight(sc: DragonSculptor):
    """
    3. KNIGHT (1.62m) — 双翼ワイバーン (Rearing Bipedal Winged Wyvern):
       Sleek, dynamic bipedal sky-predator rearing high on avian-reptile hindlegs
       atop a broken Gothic pinnacle crag, long S-curved neck, twin poised raptorial
       fore-talons, wide scalloped bat-wings soaring to 1.62m, and spade-blade tail!
    """
    sc.add_jagged_stone_crag(seed=37, max_r=0.435, crag_h=0.215, spire_bias_y=-0.03, slab_tilt=(0.18, -0.06, 0.15))

    # PART_LOWER_BODY: Powerful digitigrade wyvern haunches & long raptor-reptile hindlegs
    pelvis_pts = [
        (Vector((0.0, -0.12, 0.58)), 0.105, 0.105),
        (Vector((0.0, -0.06, 0.68)), 0.125, 0.122),
        (Vector((0.0, -0.01, 0.76)), 0.128, 0.126),
    ]
    sc.add_lofted_spine(pelvis_pts, segs=12, dorsal_keel=0.30, uv_zone=UV_ZONE_SCALES, part_id=PART_LOWER_BODY)

    for sgn in (-1.0, 1.0):
        sc.add_dragon_hindleg(
            hip_pos=Vector((sgn * 0.115, -0.08, 0.66)),
            knee_pos=Vector((sgn * 0.175, 0.08, 0.52)),
            ankle_pos=Vector((sgn * 0.185, -0.12, 0.36)),
            foot_pos=Vector((sgn * 0.165, 0.02, 0.195)),
            side=sgn,
            thigh_r=0.082,
            shin_r=0.052,
            talon_len=0.095,
            part_id=PART_LOWER_BODY,
        )

    # PART_UPPER_BODY: Sinuous S-curved dragon keel-chest & long arched wyvern neck
    spine_pts = [
        (Vector((0.0, -0.01, 0.76)), 0.126, 0.125),
        (Vector((0.0, 0.07, 0.88)), 0.145, 0.142),
        (Vector((0.0, 0.09, 1.00)), 0.132, 0.128),
        (Vector((0.0, 0.05, 1.11)), 0.096, 0.098),
        (Vector((0.0, 0.09, 1.20)), 0.082, 0.086),
        (Vector((0.0, 0.17, 1.25)), 0.076, 0.080),
    ]
    s_frames = sc.add_lofted_spine(
        spine_pts, segs=12, dorsal_keel=0.36, uv_zone=UV_ZONE_SCALES, v_repeats=3, part_id=PART_UPPER_BODY
    )
    sc.add_spine_osteoderms(
        s_frames[:-1], [(p[1], p[2]) for p in spine_pts[:-1]], count=6, width=0.10, length=0.11, thickness=0.020, part_id=PART_UPPER_BODY
    )
    sc.add_dorsal_spines(
        s_frames[:-1], count=7, len_start=0.095, len_end=0.065, r_base=0.022, sweep_back=0.48, radial_offset=0.082, part_id=PART_UPPER_BODY
    )

    # PART_WEAPON_R & PART_SHIELD_L: Twin poised raptorial striking fore-talons at chest height!
    sc.add_dragon_forelimb(
        shoulder_pos=Vector((0.135, 0.07, 0.98)),
        elbow_pos=Vector((0.225, -0.01, 0.89)),
        wrist_pos=Vector((0.185, 0.22, 0.88)),
        claw_forward=Vector((-0.25, 0.90, -0.35)),
        claw_up=Vector((0.25, 0.35, 0.90)),
        side=1.0,
        upper_r=0.056,
        fore_r=0.044,
        talon_len=0.105,
        num_talons=3,
        curl_deg=58.0,
        pauldron_spike_len=0.085,
        part_id=PART_WEAPON_R,
    )
    sc.add_dragon_forelimb(
        shoulder_pos=Vector((-0.135, 0.07, 0.96)),
        elbow_pos=Vector((-0.225, -0.01, 0.86)),
        wrist_pos=Vector((-0.185, 0.20, 0.82)),
        claw_forward=Vector((0.22, 0.90, -0.38)),
        claw_up=Vector((-0.22, 0.38, 0.90)),
        side=-1.0,
        upper_r=0.056,
        fore_r=0.044,
        talon_len=0.105,
        num_talons=3,
        curl_deg=58.0,
        pauldron_spike_len=0.085,
        part_id=PART_SHIELD_L,
    )

    # PART_HEAD_JAW: Aerodynamic horned Wyvern Skull roaring downward-forward (+Y)
    sc.add_anatomical_dragon_skull(
        neck_pos=Vector((0.0, 0.18, 1.25)),
        forward_dir=Vector((0.0, 0.94, -0.34)),
        up_dir=Vector((0.0, 0.34, 0.94)),
        scale=0.95,
        snout_stretch=1.08,
        jaw_open_deg=32.0,
        horn_len=0.32,
        horn_spread_deg=22.0,
        horn_curve_rad=0.52,
        frill_count=2,
        part_id=PART_HEAD_JAW,
    )

    # PART_WINGS_TAIL: Wide-spread 4-fingered scalloped Wyvern Wings soaring to 1.62m + whip Spade-Tail
    for sgn in (-1.0, 1.0):
        sc.add_dragon_wing(
            shoulder_pos=Vector((sgn * 0.115, 0.02, 0.99)),
            side=sgn,
            wrist_pos=Vector((sgn * 0.38, -0.06, 1.54)),
            outer_tip=Vector((sgn * 0.51, -0.18, 1.62)),
            inner_tip=Vector((sgn * 0.22, -0.26, 0.72)),
            flank_anchor=Vector((sgn * 0.10, -0.08, 0.76)),
            num_fingers=4,
            spar_r=0.038,
            scallop_depth=0.092,
            sub_w=4,
            part_id=PART_WINGS_TAIL,
        )

    sc.add_anatomical_dragon_tail(
        ctrl_pts=(
            Vector((0.0, -0.12, 0.60)),
            Vector((0.05, -0.44, 0.42)),
            Vector((0.34, -0.40, 0.26)),
            Vector((0.36, -0.08, 0.34)),
        ),
        r_base=0.078,
        r_tip=0.018,
        n_stations=14,
        spine_count=7,
        tip_style="spade",
        part_id=PART_WINGS_TAIL,
    )


def _sculpt_bishop(sc: DragonSculptor):
    """
    4. BISHOP (1.72m) — 双頭の秘術竜 (Twin-Headed Oracle Hydra-Wyrm):
       Coiled serpentine hydra-dragon with TWO full intertwining S-curved dragon necks
       & horned fanged dragon skulls (`PART_WEAPON_R` = Right Neck & Skull,
       `PART_SHIELD_L` = Left Neck & Skull), central glowing runic breath-nexus &
       arcane spine-crest (`PART_HEAD_JAW`), swept dragon wings, and fin-tipped tail!
    """
    sc.add_jagged_stone_crag(seed=51, max_r=0.45, crag_h=0.215, spire_bias_y=0.0, slab_tilt=(0.12, 0.12, 0.30))

    # PART_LOWER_BODY: Heavy muscular legless coiled serpent-wyrm lower body resting cleanly on crag / board
    coil_pts = []
    n_coil = 14
    for i in range(n_coil):
        t = i / float(n_coil - 1)
        ang = -0.65 * math.pi + t * 1.65 * math.pi
        rad = 0.24 * (1.0 - 0.58 * (t ** 1.25))
        cz = 0.22 + 0.48 * (t ** 1.05)
        r_tube = 0.096 + 0.026 * math.sin(math.pi * t)
        coil_pts.append((Vector((math.cos(ang) * rad, math.sin(ang) * rad - 0.03, cz)), r_tube * 1.04, r_tube * 0.96))

    c_frames = sc.add_lofted_spine(
        coil_pts, segs=12, dorsal_keel=0.30, uv_zone=UV_ZONE_SCALES, v_repeats=3, part_id=PART_LOWER_BODY
    )
    sc.add_spine_osteoderms(
        c_frames[2:], [(p[1], p[2]) for p in coil_pts[2:]], count=5, width=0.11, length=0.11, thickness=0.020, part_id=PART_LOWER_BODY
    )

    # PART_UPPER_BODY: Broad scaly hydra-wyrm chest bifurcating into twin shoulder-collars
    chest_pts = [
        (Vector((0.0, -0.02, 0.68)), 0.132, 0.122),
        (Vector((0.0, 0.04, 0.80)), 0.162, 0.138),
        (Vector((0.0, 0.06, 0.92)), 0.175, 0.135),
        (Vector((0.0, 0.05, 1.02)), 0.148, 0.112),
    ]
    ch_frames = sc.add_lofted_spine(
        chest_pts, segs=14, dorsal_keel=0.28, uv_zone=UV_ZONE_SCALES, v_repeats=2, part_id=PART_UPPER_BODY
    )
    sc.add_spine_osteoderms(
        ch_frames, [(p[1], p[2]) for p in chest_pts], count=4, width=0.125, length=0.12, thickness=0.022, part_id=PART_UPPER_BODY
    )

    # PART_HEAD_JAW: Central Glowing Runic Breath-Core & Tall Dorsal Spine-Fin Crest between twin necks!
    crest_pts = [
        (Vector((0.0, 0.04, 0.99)), 0.072, 0.078),
        (Vector((0.0, 0.08, 1.12)), 0.064, 0.076),
        (Vector((0.0, 0.06, 1.25)), 0.046, 0.062),
        (Vector((0.0, 0.02, 1.37)), 0.024, 0.036),
    ]
    cr_frames = sc.add_lofted_spine(
        crest_pts, segs=10, dorsal_keel=0.45, sharp_tip=True, uv_zone=UV_ZONE_SCALES, part_id=PART_HEAD_JAW
    )
    # Glowing Elder Runic Soul-Crystal Breath Nexus embedded in central hydra bifurcation!
    sc.add_box_bevel(
        size=Vector((0.078, 0.065, 0.16)),
        center=Vector((0.0, 0.12, 1.10)),
        rot_euler=(-0.18, 0.0, 0.0),
        taper_top=(0.65, 0.65),
        uv_zone=UV_ZONE_RUNES,
        part_id=PART_HEAD_JAW,
    )
    sc.add_dorsal_spines(
        cr_frames, count=4, len_start=0.13, len_end=0.09, r_base=0.024, sweep_back=0.35, radial_offset=0.035, part_id=PART_HEAD_JAW
    )

    # PART_WEAPON_R (+X): FULL RIGHT S-CURVED DRAGON NECK & HORNED FANGED SKULL!
    # Angled forward slightly to give dynamic predator poise while preserving majestic thickness
    r_neck_pts = [
        (Vector((0.11, 0.06, 0.94)), 0.082, 0.082),
        (Vector((0.20, 0.06, 1.06)), 0.075, 0.076),
        (Vector((0.24, 0.11, 1.18)), 0.069, 0.071),
        (Vector((0.21, 0.19, 1.29)), 0.065, 0.067),
        (Vector((0.17, 0.28, 1.35)), 0.063, 0.065),
    ]
    rn_frames = sc.add_lofted_spine(
        r_neck_pts, segs=10, dorsal_keel=0.34, uv_zone=UV_ZONE_SCALES, v_repeats=2, part_id=PART_WEAPON_R
    )
    sc.add_dorsal_spines(
        rn_frames[:-1], count=5, len_start=0.072, len_end=0.052, r_base=0.018, sweep_back=0.45, radial_offset=0.055, part_id=PART_WEAPON_R
    )
    sc.add_anatomical_dragon_skull(
        neck_pos=Vector((0.17, 0.28, 1.35)),
        forward_dir=_safe_norm(Vector((-0.14, 0.93, -0.33))),
        up_dir=_safe_norm(Vector((0.08, 0.33, 0.94))),
        scale=0.82,
        snout_stretch=1.02,
        jaw_open_deg=28.0,
        horn_len=0.28,
        horn_spread_deg=22.0,
        horn_curve_rad=0.58,
        frill_count=2,
        bronze_horn_rings=True,
        part_id=PART_WEAPON_R,
    )

    # PART_SHIELD_L (-X): FULL LEFT S-CURVED DRAGON NECK & HORNED FANGED SKULL!
    # Angled forward slightly to give dynamic predator poise while preserving majestic thickness
    l_neck_pts = [
        (Vector((-0.11, 0.06, 0.93)), 0.082, 0.082),
        (Vector((-0.21, 0.05, 1.04)), 0.075, 0.076),
        (Vector((-0.24, 0.11, 1.16)), 0.069, 0.071),
        (Vector((-0.20, 0.20, 1.27)), 0.065, 0.067),
        (Vector((-0.17, 0.29, 1.32)), 0.063, 0.065),
    ]
    ln_frames = sc.add_lofted_spine(
        l_neck_pts, segs=10, dorsal_keel=0.34, uv_zone=UV_ZONE_SCALES, v_repeats=2, part_id=PART_SHIELD_L
    )
    sc.add_dorsal_spines(
        ln_frames[:-1], count=5, len_start=0.072, len_end=0.052, r_base=0.018, sweep_back=0.45, radial_offset=0.055, part_id=PART_SHIELD_L
    )
    sc.add_anatomical_dragon_skull(
        neck_pos=Vector((-0.17, 0.29, 1.32)),
        forward_dir=_safe_norm(Vector((0.14, 0.92, -0.37))),
        up_dir=_safe_norm(Vector((-0.08, 0.37, 0.93))),
        scale=0.82,
        snout_stretch=1.02,
        jaw_open_deg=32.0,
        horn_len=0.28,
        horn_spread_deg=22.0,
        horn_curve_rad=0.58,
        frill_count=2,
        bronze_horn_rings=True,
        part_id=PART_SHIELD_L,
    )

    # PART_WINGS_TAIL: Swept arcane stone dragon wings rising to 1.72m + coiled fin-tipped tail
    for sgn in (-1.0, 1.0):
        sc.add_dragon_wing(
            shoulder_pos=Vector((sgn * 0.13, -0.03, 0.96)),
            side=sgn,
            wrist_pos=Vector((sgn * 0.38, -0.10, 1.63)),
            outer_tip=Vector((sgn * 0.50, -0.22, 1.72)),
            inner_tip=Vector((sgn * 0.22, -0.28, 0.72)),
            flank_anchor=Vector((sgn * 0.12, -0.10, 0.74)),
            num_fingers=4,
            spar_r=0.036,
            scallop_depth=0.088,
            sub_w=3,
            part_id=PART_WINGS_TAIL,
        )

    sc.add_anatomical_dragon_tail(
        ctrl_pts=(
            Vector((-0.10, -0.18, 0.28)),
            Vector((-0.34, -0.38, 0.24)),
            Vector((0.18, -0.46, 0.26)),
            Vector((0.36, -0.22, 0.38)),
        ),
        r_base=0.078,
        r_tip=0.020,
        n_stations=13,
        spine_count=6,
        tip_style="fin",
        part_id=PART_WINGS_TAIL,
    )


def _sculpt_queen(sc: DragonSculptor):
    """
    5. QUEEN (1.94m) — 四翼の飛翔女帝竜 (Four-Winged Celestial Elder Dragon):
       Graceful, lethal Four-Winged Elder Dragon tilted forward in a poised
       quadrupedal stance with both clawed forelimbs grounded alongside her
       hindfeet! Long swan-like serpentine neck, 4-horned Crowned Elder Dragon
       Skull with jaw-frills, FOUR sweeping carved-stone dragon wings (soaring
       primary + lower secondary seraph wings), and ribbon-lance tail!
    """
    sc.add_jagged_stone_crag(seed=64, max_r=0.45, crag_h=0.22, spire_bias_y=-0.02, slab_tilt=(0.16, -0.11, 0.25))

    # PART_LOWER_BODY: Digitigrade hindlimbs & lowered pelvis angled smoothly forward
    pelvis_pts = [
        (Vector((0.0, -0.20, 0.60)), 0.105, 0.102),
        (Vector((0.0, -0.11, 0.67)), 0.124, 0.118),
        (Vector((0.0, -0.02, 0.73)), 0.128, 0.122),
    ]
    sc.add_lofted_spine(pelvis_pts, segs=12, dorsal_keel=0.30, uv_zone=UV_ZONE_SCALES, part_id=PART_LOWER_BODY)

    for sgn in (-1.0, 1.0):
        sc.add_dragon_hindleg(
            hip_pos=Vector((sgn * 0.115, -0.13, 0.67)),
            knee_pos=Vector((sgn * 0.180, 0.02, 0.52)),
            ankle_pos=Vector((sgn * 0.190, -0.18, 0.36)),
            foot_pos=Vector((sgn * 0.165, -0.07, 0.198)),
            side=sgn,
            thigh_r=0.078,
            shin_r=0.050,
            talon_len=0.095,
            part_id=PART_LOWER_BODY,
        )

    # PART_UPPER_BODY: Forward-tilted sleek dragon ribcage & long swan-like S-curved serpentine neck
    spine_pts = [
        (Vector((0.0, -0.02, 0.73)), 0.126, 0.122),
        (Vector((0.0, 0.09, 0.82)), 0.142, 0.136),
        (Vector((0.0, 0.19, 0.92)), 0.132, 0.126),
        (Vector((0.0, 0.17, 1.07)), 0.094, 0.096),
        (Vector((0.0, 0.14, 1.23)), 0.080, 0.084),
        (Vector((0.0, 0.22, 1.37)), 0.072, 0.076),
    ]
    s_frames = sc.add_lofted_spine(
        spine_pts, segs=12, dorsal_keel=0.36, uv_zone=UV_ZONE_SCALES, v_repeats=3, part_id=PART_UPPER_BODY
    )
    sc.add_spine_osteoderms(
        s_frames[:-1], [(p[1], p[2]) for p in spine_pts[:-1]], count=7, width=0.105, length=0.115, thickness=0.020, part_id=PART_UPPER_BODY
    )
    sc.add_dorsal_spines(
        s_frames[:-1], count=7, len_start=0.105, len_end=0.068, r_base=0.022, sweep_back=0.50, radial_offset=0.080, part_id=PART_UPPER_BODY
    )

    # PART_WEAPON_R & PART_SHIELD_L: Grounded elder-dragon forelimbs bracing both clawed hands firmly on ground
    for sgn, pid in ((1.0, PART_WEAPON_R), (-1.0, PART_SHIELD_L)):
        sc.add_dragon_forelimb(
            shoulder_pos=Vector((sgn * 0.135, 0.17, 0.90)),
            elbow_pos=Vector((sgn * 0.235, 0.09, 0.58)),
            wrist_pos=Vector((sgn * 0.205, 0.29, 0.195)),
            claw_forward=Vector((-sgn * 0.10, 0.95, -0.20)),
            claw_up=Vector((0.0, 0.20, 0.98)),
            side=sgn,
            upper_r=0.056,
            fore_r=0.044,
            talon_len=0.096,
            num_talons=4,
            curl_deg=50.0,
            pauldron_spike_len=0.095,
            part_id=pid,
        )

    # PART_HEAD_JAW: Regal 4-Horned Crowned Elder Dragon Skull with 3-spined jaw-frills!
    sc.add_anatomical_dragon_skull(
        neck_pos=Vector((0.0, 0.23, 1.37)),
        forward_dir=Vector((0.0, 0.95, -0.28)),
        up_dir=Vector((0.0, 0.28, 0.95)),
        scale=0.96,
        snout_stretch=1.06,
        jaw_open_deg=26.0,
        horn_len=0.35,
        horn_spread_deg=20.0,
        horn_curve_rad=0.65,
        crown_horns=2,
        frill_count=3,
        bronze_horn_rings=True,
        part_id=PART_HEAD_JAW,
    )

    # PART_WINGS_TAIL: FOUR Sweeping Carved-Stone Dragon Wings (Upper Primary soaring to 1.94m + Lower Secondary Seraph Wings!)
    for sgn in (-1.0, 1.0):
        # 1. Grand Upper Primary Wings soaring to Z = 1.94m
        sc.add_dragon_wing(
            shoulder_pos=Vector((sgn * 0.115, 0.11, 0.98)),
            side=sgn,
            wrist_pos=Vector((sgn * 0.39, -0.02, 1.82)),
            outer_tip=Vector((sgn * 0.52, -0.16, 1.94)),
            inner_tip=Vector((sgn * 0.24, -0.20, 1.06)),
            flank_anchor=Vector((sgn * 0.11, 0.03, 0.84)),
            num_fingers=4,
            spar_r=0.036,
            scallop_depth=0.090,
            sub_w=3,
            part_id=PART_WINGS_TAIL,
        )
        # 2. Lower Secondary Seraph-Drake Wings splaying wide below primary wings!
        sc.add_dragon_wing(
            shoulder_pos=Vector((sgn * 0.105, 0.04, 0.82)),
            side=sgn,
            wrist_pos=Vector((sgn * 0.36, -0.08, 1.08)),
            outer_tip=Vector((sgn * 0.50, -0.22, 0.92)),
            inner_tip=Vector((sgn * 0.20, -0.22, 0.52)),
            flank_anchor=Vector((sgn * 0.10, -0.04, 0.66)),
            num_fingers=3,
            spar_r=0.028,
            scallop_depth=0.068,
            sub_w=2,
            part_id=PART_WINGS_TAIL,
        )

    sc.add_anatomical_dragon_tail(
        ctrl_pts=(
            Vector((0.0, -0.20, 0.60)),
            Vector((-0.08, -0.46, 0.42)),
            Vector((-0.36, -0.40, 0.25)),
            Vector((-0.34, -0.06, 0.33)),
        ),
        r_base=0.078,
        r_tip=0.018,
        n_stations=14,
        spine_count=7,
        tip_style="ribbon",
        part_id=PART_WINGS_TAIL,
    )


def _sculpt_king(sc: DragonSculptor):
    """
    6. KING (2.42m) — 大聖堂の覇王古竜 (Great Dragon Bipedal Sovereign Arch-Dragon):
       Iconic heavy pear-shaped bipedal Great Dragon build: massive muscular thighs &
       planted Z-bent hindlegs, rounded broad lower belly tapering smoothly into a graceful
       S-curved dorsal-spiked neck, compact forelimbs poised in front of the chest, swept-back
       mohawk crest-fin + twin Great Dragon horns over fierce brows, soaring cathedral bat-wings
       with tall wing-thumbs, and a thick ground-sweeping serrated tail!
    """
    sc.add_jagged_stone_crag(seed=79, max_r=0.465, crag_h=0.22, spire_bias_y=-0.02, slab_tilt=(0.14, 0.08, -0.22))

    # Unified seamless torso (pelvis -> pear belly -> chest -> S-curved neck) so waist bends with zero cap/seam gap!
    # 11 stations (10 rings) with v_repeats=5 -> cos(i*pi/2) gives uniform |dv|=0.5 on every ring.
    torso_pts = [
        (Vector((0.0, -0.06, 0.36)), 0.150, 0.160),
        (Vector((0.0,  0.01, 0.52)), 0.210, 0.222),
        (Vector((0.0,  0.05, 0.69)), 0.226, 0.232),
        (Vector((0.0,  0.06, 0.85)), 0.214, 0.218),
        (Vector((0.0,  0.06, 1.01)), 0.194, 0.196),
        (Vector((0.0,  0.07, 1.17)), 0.178, 0.180),
        (Vector((0.0,  0.05, 1.33)), 0.158, 0.160),
        (Vector((0.0,  0.00, 1.49)), 0.125, 0.128),
        (Vector((0.0, -0.02, 1.63)), 0.105, 0.110),
        (Vector((0.0,  0.05, 1.77)), 0.098, 0.104),
        (Vector((0.0,  0.18, 1.89)), 0.094, 0.100),
    ]
    torso_pids = [PART_LOWER_BODY] * 4 + [PART_UPPER_BODY] * 7
    t_frames = sc.add_lofted_spine(
        torso_pts,
        segs=14,
        dorsal_keel=0.28,
        uv_zone=UV_ZONE_SCALES,
        v_repeats=5,
        part_id=PART_UPPER_BODY,
        part_ids=torso_pids,
    )
    sc.add_dorsal_spines(
        t_frames[:4], count=4, len_start=0.075, len_end=0.085, r_base=0.024, sweep_back=0.52, radial_offset=0.14, part_id=PART_LOWER_BODY
    )
    sc.add_dorsal_spines(
        t_frames[4:], count=11, len_start=0.088, len_end=0.068, r_base=0.024, sweep_back=0.58, radial_offset=0.075, part_id=PART_UPPER_BODY
    )

    for sgn in (-1.0, 1.0):
        sc.add_dragon_hindleg(
            hip_pos=Vector((sgn * 0.175, -0.04, 0.68)),
            knee_pos=Vector((sgn * 0.275, 0.21, 0.50)),
            ankle_pos=Vector((sgn * 0.255, -0.06, 0.31)),
            foot_pos=Vector((sgn * 0.245, 0.17, 0.195)),
            side=sgn,
            thigh_r=0.142,
            shin_r=0.084,
            talon_len=0.125,
            foot_forward=Vector((sgn * 0.12, 1.0, -0.14)),
            part_id=PART_LOWER_BODY,
        )

    # PART_WEAPON_R (+X): Compact muscular right dragon forelimb curled in front of chest
    sc.add_dragon_forelimb(
        shoulder_pos=Vector((0.148, 0.07, 1.36)),
        elbow_pos=Vector((0.215, 0.04, 1.15)),
        wrist_pos=Vector((0.175, 0.24, 1.24)),
        claw_forward=Vector((-0.26, 0.88, -0.38)),
        claw_up=Vector((0.20, 0.36, 0.91)),
        side=1.0,
        upper_r=0.060,
        fore_r=0.048,
        talon_len=0.088,
        num_talons=4,
        curl_deg=58.0,
        pauldron_spike_len=0.0,
        part_id=PART_WEAPON_R,
    )

    # PART_SHIELD_L (-X): Compact muscular left dragon forelimb poised forward of chest
    sc.add_dragon_forelimb(
        shoulder_pos=Vector((-0.148, 0.07, 1.35)),
        elbow_pos=Vector((-0.215, 0.03, 1.14)),
        wrist_pos=Vector((-0.172, 0.25, 1.21)),
        claw_forward=Vector((0.24, 0.90, -0.36)),
        claw_up=Vector((-0.20, 0.34, 0.92)),
        side=-1.0,
        upper_r=0.060,
        fore_r=0.048,
        talon_len=0.088,
        num_talons=4,
        curl_deg=58.0,
        pauldron_spike_len=0.0,
        part_id=PART_SHIELD_L,
    )

    # PART_HEAD_JAW: Swept-crest Great Dragon skull with fierce brow, twin backward horns & snarling jaw
    head_neck = Vector((0.0, 0.20, 1.89))
    head_fw = Vector((0.0, 0.94, -0.34)).normalized()
    head_up = Vector((0.0, 0.34, 0.94)).normalized()
    sc.add_anatomical_dragon_skull(
        neck_pos=head_neck,
        forward_dir=head_fw,
        up_dir=head_up,
        scale=1.12,
        snout_stretch=1.10,
        jaw_open_deg=14.0,
        horn_len=0.35,
        horn_spread_deg=20.0,
        horn_curve_rad=0.38,
        horn_forward_sweep=-0.72,
        crown_horns=0,
        central_crest_horn=0.27,
        frill_count=1,
        bronze_horn_rings=False,
        eye_outset=0.022,
        eye_scale=1.55,
        part_id=PART_HEAD_JAW,
    )
    # Iconic Great Dragon swept mohawk-fin crest spines trailing behind the central horn crest
    for ci, (back_t, up_t, c_len, c_r) in enumerate((
        (0.015, 0.078, 0.22, 0.028),
        (-0.035, 0.066, 0.185, 0.024),
        (-0.082, 0.048, 0.150, 0.020),
    )):
        sc.add_curved_horn(
            base_pos=head_neck + head_fw * back_t + head_up * up_t,
            base_dir=(-head_fw * 0.56 + head_up * 0.83).normalized(),
            curve_dir=-head_fw,
            length=c_len,
            r_base=c_r,
            curve_rad=0.40,
            rings=5,
            segs=6,
            ridge_amp=0.04,
            uv_zone=UV_ZONE_STONE,
            part_id=PART_HEAD_JAW,
        )

    # PART_WINGS_TAIL: Soaring High-Mounted 4-Finger Bat-Wings + Thick Ground-Sweeping Spiked Tail
    for sgn in (-1.0, 1.0):
        sc.add_dragon_wing(
            shoulder_pos=Vector((sgn * 0.115, -0.05, 1.42)),
            side=sgn,
            wrist_pos=Vector((sgn * 0.46, -0.14, 2.26)),
            outer_tip=Vector((sgn * 0.58, -0.18, 2.40)),
            inner_tip=Vector((sgn * 0.48, -0.26, 0.72)),
            flank_anchor=Vector((sgn * 0.15, -0.08, 0.92)),
            num_fingers=4,
            spar_r=0.044,
            scallop_depth=0.125,
            sub_w=4,
            part_id=PART_WINGS_TAIL,
        )

    sc.add_anatomical_dragon_tail(
        ctrl_pts=(
            Vector((0.0, -0.14, 0.48)),
            Vector((-0.24, -0.44, 0.31)),
            Vector((0.36, -0.44, 0.30)),
            Vector((0.48, -0.02, 0.56)),
        ),
        r_base=0.145,
        r_tip=0.018,
        n_stations=16,
        spine_count=14,
        tip_style="pointed",
        part_id=PART_WINGS_TAIL,
    )


_PIECE_BUILDERS = {
    "pawn": _sculpt_pawn,
    "rook": _sculpt_rook,
    "knight": _sculpt_knight,
    "bishop": _sculpt_bishop,
    "queen": _sculpt_queen,
    "king": _sculpt_king,
}


def build_piece_mesh_data(piece_name: str) -> tuple[bpy.types.Mesh, list[int]]:
    """
    Build the complete sculpted Anatomical Carved-Stone Dragon BMesh for `piece_name`:
      - Grounds jagged ruined-stone crag (`PART_PEDESTAL`) flush at `Z = 0.0` (`Z in [0.0, 0.22]`, `r <= 0.472m`)
      - Normalizes dragon height cleanly to `[0.0, PIECE_HEIGHTS[piece_name]]`
      - Enforces `r_xy <= 0.555m` (`< MAX_WING_RADIUS = 0.56m`)
      - Preserves 100% closed 2-manifold topology (`nonMan == 0`), outward normals, and `[0, 1]` UVs
      - Returns `(mesh_data, part_ids)`
    """
    key = piece_name.strip().lower()
    if key not in _PIECE_BUILDERS:
        raise ValueError(f"Unknown dragon piece '{piece_name}'. Expected one of {tuple(_PIECE_BUILDERS.keys())}.")

    target_h = float(PIECE_HEIGHTS[key])
    sc = DragonSculptor()
    _PIECE_BUILDERS[key](sc)

    bm = sc.bm
    part_layer = sc.part_layer
    uv_layer = sc.uv_layer

    # Orient every closed 2-manifold shell outward
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    # Shift Z so lowest crag vertex sits at exact Z = 0.0000
    z_min = min(v.co.z for v in bm.verts)
    for v in bm.verts:
        v.co.z -= z_min
        # Snap near-zero crag bottom vertices cleanly to exact 0.0
        if int(v[part_layer]) == PART_PEDESTAL and abs(v.co.z) < 0.002:
            v.co.z = 0.0

    # Normalize upper dragon height above crag top (`0.22m`) to exact `target_h`
    crag_top = 0.220
    z_max = max(v.co.z for v in bm.verts)
    max_crag_r = min(0.472, float(MAX_CRAG_RADIUS) - 0.008)
    max_body_r = 0.78 if key == "king" else min(0.555, float(MAX_WING_RADIUS) - 0.005)

    if z_max > crag_top + 1e-4:
        upper_scale = (target_h - crag_top) / (z_max - crag_top)
        for v in bm.verts:
            pid = int(v[part_layer])
            if v.co.z > crag_top:
                v.co.z = crag_top + (v.co.z - crag_top) * upper_scale

            r_xy = math.hypot(v.co.x, v.co.y)
            if pid == PART_PEDESTAL:
                v.co.z = max(0.0, min(crag_top, v.co.z))
                if r_xy > max_crag_r:
                    s_xy = max_crag_r / r_xy
                    v.co.x *= s_xy
                    v.co.y *= s_xy
            else:
                v.co.z = max(0.04, v.co.z)
                if r_xy > max_body_r:
                    s_xy = max_body_r / r_xy
                    v.co.x *= s_xy
                    v.co.y *= s_xy

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for f in bm.faces:
        for loop in f.loops:
            u, v = loop[uv_layer].uv
            loop[uv_layer].uv = (max(0.0, min(1.0, float(u))), max(0.0, min(1.0, float(v))))

    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    part_ids = [int(v[part_layer]) for v in bm.verts]

    mesh_data = bpy.data.meshes.new(f"{key}_dragon_mesh")
    bm.to_mesh(mesh_data)
    bm.free()

    mesh_data.update()
    return mesh_data, part_ids


if __name__ == "__main__":
    for pname in PIECE_HEIGHTS:
        mdata, pids = build_piece_mesh_data(pname)
        mdata.calc_loop_triangles()
        print(f"[DragonMesh] {pname:6s} | verts={len(mdata.vertices):5d} | tris={len(mdata.loop_triangles):5d}")
