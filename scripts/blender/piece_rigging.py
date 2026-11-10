"""
Draconic 7-Bone Skeletal Rigging & glTF 2.0 Seam-Blended Skinning Module
for Pure Anatomical Carved-Stone Dragons on Jagged Stone Crags.

Adheres strictly to `scripts/blender/dragon_spec.py`:
- Supports all 6 anatomical Carved-Stone Dragon Breeds (`pawn` Hatchling Drake,
  `rook` Behemoth Earth-Drake, `knight` Rearing Wyvern, `bishop` Twin-Headed
  Oracle Hydra-Wyrm, `queen` Four-Winged Celestial Elder Dragon, `king`
  Sovereign Arch-Dragon) perched on jagged ruined-stone crags (`PART_PEDESTAL`).
- Constructs the 7-bone articulated draconic armature (`Root`, `Spine_Lower`,
  `Spine_Upper`, `Head_Jaw`, `Weapon_R`, `Shield_L`, `Wings_Tail`) with strictly
  vertical EditBones (`eb.tail = eb.head + Vector((0, 0, bone_len))`) and
  `eb.roll = 0.0` (`eb.use_deform = True`), placing each branch bone's `eb.head`
  at its true 3D anatomical junction root nearest `PART_UPPER_BODY` (including
  quadruped shoulders on `pawn`/`rook` and twin hydra neck roots on `bishop`).
- Locks jagged stone crags (`PART_PEDESTAL`, especially `Z <= 0.16m` and ground
  contact `Z <= 0.045m`) strictly to `Root = 1.0` (`0.0` drift), blends
  `PART_LOWER_BODY` smoothly into `PART_PEDESTAL` across their true 3D `KDTree`
  seam, and keeps low quadruped forepaws (`PART_WEAPON_R`, `PART_SHIELD_L`) and
  sweeping dragon tails (`PART_WINGS_TAIL`) at `Z >= 0.08m` completely free of
  `Root` lock so limbs, twin necks, 4-wing spans, and tails deform cleanly.
"""

from __future__ import annotations

import math
import os
import struct
import sys
from typing import Dict, List, Optional, Sequence, Set, Tuple

import bmesh
import bpy
from mathutils import Euler, Matrix, Quaternion, Vector
from mathutils.kdtree import KDTree

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from dragon_spec import (  # noqa: E402
    BONE_NAMES,
    PART_HEAD_JAW,
    PART_LOWER_BODY,
    PART_PEDESTAL,
    PART_SHIELD_L,
    PART_UPPER_BODY,
    PART_WEAPON_R,
    PART_WINGS_TAIL,
    PIECE_HEIGHTS,
    PIECE_SPECS,
)

# glTF 2.0 skinning invariants
MIN_WEIGHT_THRESHOLD = 1e-4
MAX_INFLUENCES_PER_VERTEX = 4


# ==============================================================================
# MATHEMATICAL, KDTREE & FLOAT32 HELPERS
# ==============================================================================
def _clamp(val: float, lo: float, hi: float) -> float:
    return lo if val < lo else (hi if val > hi else val)


def _smoothstep(edge0: float, edge1: float, x: float) -> float:
    """C1-continuous Hermite smoothstep interpolation on [edge0, edge1]."""
    if edge1 <= edge0:
        return 1.0 if x >= edge0 else 0.0
    t = _clamp((x - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _to_f32(val: float) -> float:
    """Round-trip Python float through IEEE-754 float32 (matches MDeformWeight)."""
    return struct.unpack("f", struct.pack("f", float(val)))[0]


def _centroid(coords: Sequence[Vector]) -> Vector:
    n = len(coords)
    if n == 0:
        return Vector((0.0, 0.0, 0.0))
    acc = Vector((0.0, 0.0, 0.0))
    for c in coords:
        acc += c
    return acc / float(n)


def _build_kdtree(coords: Sequence[Vector]) -> Optional[KDTree]:
    n = len(coords)
    if n == 0:
        return None
    kd = KDTree(n)
    for idx, co in enumerate(coords):
        kd.insert(co, idx)
    kd.balance()
    return kd


def _resolve_piece_key_and_height(
    piece_name: str, mesh_obj: bpy.types.Object
) -> Tuple[str, float]:
    """Resolve canonical dragon breed key and standardized target height H."""
    key = (piece_name or "pawn").lower().strip()
    if key in PIECE_HEIGHTS:
        return key, float(PIECE_HEIGHTS[key])
    for spec_name, spec_h in PIECE_SPECS:
        if spec_name in key:
            return spec_name, float(spec_h)
    verts = mesh_obj.data.vertices
    max_z = max((v.co.z for v in verts), default=1.60)
    return key, max(float(max_z), 0.90)


# ==============================================================================
# ANATOMICAL JUNCTION-ROOT PIVOT EXTRACTION (ALL 6 DRAGON BREEDS)
# ==============================================================================
def _piece_joint_defaults(piece_key: str, H: float) -> Dict[str, Vector]:
    """Breed-aware fallback anatomical branch bone pivots (`eb.head`)."""
    if piece_key == "pawn":
        # Quadruped Hatchling Gargoyle Drake
        return {
            "Head_Jaw": Vector((0.0, 0.16, 0.56 * H)),
            "Weapon_R": Vector((0.14, 0.14, 0.42 * H)),
            "Shield_L": Vector((-0.14, 0.14, 0.42 * H)),
            "Wings_Tail": Vector((0.0, -0.06, 0.48 * H)),
        }
    if piece_key == "rook":
        # Quadruped Behemoth Earth-Drake + Club Tail
        return {
            "Head_Jaw": Vector((0.0, 0.20, 0.54 * H)),
            "Weapon_R": Vector((0.18, 0.16, 0.40 * H)),
            "Shield_L": Vector((-0.18, 0.16, 0.40 * H)),
            "Wings_Tail": Vector((0.0, -0.14, 0.44 * H)),
        }
    if piece_key == "bishop":
        # Twin-Headed Oracle Hydra-Wyrm (Right & Left Dragon Necks on Weapon_R / Shield_L)
        return {
            "Head_Jaw": Vector((0.0, 0.02, 0.68 * H)),
            "Weapon_R": Vector((0.10, 0.06, 0.58 * H)),
            "Shield_L": Vector((-0.10, 0.06, 0.58 * H)),
            "Wings_Tail": Vector((0.0, -0.10, 0.52 * H)),
        }
    if piece_key == "knight":
        # Rearing Winged Wyvern
        return {
            "Head_Jaw": Vector((0.0, 0.10, 0.72 * H)),
            "Weapon_R": Vector((0.15, 0.10, 0.58 * H)),
            "Shield_L": Vector((-0.15, 0.10, 0.58 * H)),
            "Wings_Tail": Vector((0.0, -0.08, 0.58 * H)),
        }
    if piece_key == "queen":
        # Four-Winged Celestial Elder Dragon
        return {
            "Head_Jaw": Vector((0.0, 0.06, 0.74 * H)),
            "Weapon_R": Vector((0.15, 0.08, 0.60 * H)),
            "Shield_L": Vector((-0.15, 0.08, 0.60 * H)),
            "Wings_Tail": Vector((0.0, -0.09, 0.58 * H)),
        }
    # Sovereign Arch-Dragon ("king" or generic dragon)
    return {
        "Head_Jaw": Vector((0.0, 0.08, 0.74 * H)),
        "Weapon_R": Vector((0.17, 0.10, 0.60 * H)),
        "Shield_L": Vector((-0.17, 0.10, 0.60 * H)),
        "Wings_Tail": Vector((0.0, -0.10, 0.58 * H)),
    }


def _junction_cluster_centroid(
    verts_part: Sequence[Vector],
    seam_coords: Sequence[Vector],
    kd_parent: Optional[KDTree],
    H: float,
    tie_z_bias: float = 0.0,
) -> Optional[Vector]:
    """
    Find the 3D attachment root centroid of `verts_part` where it joins
    `PART_UPPER_BODY` (via welded seam edges or 3D KDTree surface proximity).

    `tie_z_bias > 0` slightly favors lower Z when distances tie (upward-growing
    necks/heads); `tie_z_bias < 0` slightly favors higher Z (downward-reaching
    quadruped forelimbs whose shoulders are at the top of the limb).
    """
    if len(seam_coords) >= 3:
        return _centroid(seam_coords)

    if len(verts_part) < 4:
        return None

    z_min = min(c.z for c in verts_part)
    z_max = max(c.z for c in verts_part)
    z_span = max(z_max - z_min, 0.05)

    if kd_parent is not None:
        dists = [kd_parent.find(c)[2] for c in verts_part]
        d_min = min(dists)
        band_tol = max(0.042, 0.028 * H)
        near_indices = [
            idx for idx, d in enumerate(dists) if d <= d_min + band_tol
        ]
        target_k = max(4, min(24, len(verts_part) // 6))
        if len(near_indices) > target_k * 2:
            near_indices.sort(
                key=lambda idx: dists[idx]
                + tie_z_bias * 0.035 * ((verts_part[idx].z - z_min) / z_span)
            )
            near_indices = near_indices[:target_k]
        elif len(near_indices) < 4:
            ranked = sorted(
                range(len(verts_part)),
                key=lambda idx: dists[idx]
                + tie_z_bias * 0.035 * ((verts_part[idx].z - z_min) / z_span),
            )
            near_indices = ranked[: min(len(verts_part), max(4, target_k))]
        return _centroid([verts_part[idx] for idx in near_indices])

    # Fallback when parent KDTree is empty: use proximal Z quantile
    sorted_z = sorted(verts_part, key=lambda c: c.z, reverse=(tie_z_bias < 0.0))
    k = max(4, len(sorted_z) // 5)
    return _centroid(sorted_z[:k])


def _compute_spine_and_branch_pivots(
    piece_key: str,
    H: float,
    mesh_data: bpy.types.Mesh,
    part_ids: Sequence[int],
) -> Tuple[float, float, float, Dict[str, Vector]]:
    """
    Compute spine segment Z heights (`z_spine_lo`, `z_spine_mid`, `z_spine_hi`)
    and 3D anatomical joint pivots (`eb.head`) for all 4 child branch bones.
    """
    defaults = _piece_joint_defaults(piece_key, H)
    verts = mesh_data.vertices
    n_verts = len(verts)

    part_coords: Dict[int, List[Vector]] = {}
    for idx in range(n_verts):
        pid = int(part_ids[idx])
        part_coords.setdefault(pid, []).append(verts[idx].co.copy())

    # Collect direct cross-part welded seam coordinates against PART_UPPER_BODY & PART_LOWER_BODY
    seam_upper: Dict[int, List[Vector]] = {}
    seam_lower_wt: List[Vector] = []
    seen_upper: Set[int] = set()
    seen_lower_wt: Set[int] = set()
    for edge in mesh_data.edges:
        u, v = edge.vertices[0], edge.vertices[1]
        pu, pv = int(part_ids[u]), int(part_ids[v])
        if pu == pv:
            continue
        if pv == PART_UPPER_BODY and u not in seen_upper:
            seen_upper.add(u)
            seam_upper.setdefault(pu, []).append(verts[u].co.copy())
        elif pu == PART_UPPER_BODY and v not in seen_upper:
            seen_upper.add(v)
            seam_upper.setdefault(pv, []).append(verts[v].co.copy())

        if pu == PART_WINGS_TAIL and pv == PART_LOWER_BODY and u not in seen_lower_wt:
            seen_lower_wt.add(u)
            seam_lower_wt.append(verts[u].co.copy())
        elif pv == PART_WINGS_TAIL and pu == PART_LOWER_BODY and v not in seen_lower_wt:
            seen_lower_wt.add(v)
            seam_lower_wt.append(verts[v].co.copy())

    verts_upper = part_coords.get(PART_UPPER_BODY, [])
    verts_lower = part_coords.get(PART_LOWER_BODY, [])
    kd_upper = _build_kdtree(verts_upper)
    kd_lower = _build_kdtree(verts_lower)
    kd_body = kd_upper if kd_upper is not None else kd_lower

    # Spine Z milestones adapted cleanly to crag height & lower/upper body junction
    z_spine_lo = min(0.19, 0.17 * H)
    seam_lu = seam_upper.get(PART_LOWER_BODY, [])
    if len(seam_lu) >= 3:
        z_lu = _centroid(seam_lu).z
        z_spine_mid = _clamp(z_lu, max(z_spine_lo + 0.14, 0.34 * H), 0.52 * H)
    elif verts_lower and verts_upper:
        z_lo_med = sorted(c.z for c in verts_lower)[len(verts_lower) // 2]
        z_up_med = sorted(c.z for c in verts_upper)[len(verts_upper) // 2]
        z_est = 0.5 * (z_lo_med + z_up_med)
        z_spine_mid = _clamp(z_est, max(z_spine_lo + 0.14, 0.35 * H), 0.50 * H)
    else:
        z_spine_mid = max(z_spine_lo + 0.15, 0.44 * H)

    z_spine_hi = _clamp(0.72 * H, z_spine_mid + 0.16, 0.84 * H)

    heads: Dict[str, Vector] = {}
    is_quadruped = piece_key in ("pawn", "rook")
    is_hydra = piece_key == "bishop"

    # 1. Head_Jaw: neck-base / dorsal-crest junction nearest PART_UPPER_BODY
    verts_hj = part_coords.get(PART_HEAD_JAW, [])
    c_hj = _junction_cluster_centroid(
        verts_hj,
        seam_upper.get(PART_HEAD_JAW, []),
        kd_body,
        H,
        tie_z_bias=1.0,
    )
    if c_hj is not None:
        mean_x_hj = sum(c.x for c in verts_hj) / len(verts_hj)
        x_hj = 0.0 if abs(mean_x_hj) < 0.035 else _clamp(c_hj.x, -0.16, 0.16)
        y_hj = _clamp(c_hj.y, -0.32, 0.44)
        z_hj = _clamp(c_hj.z, 0.22 * H, 0.90 * H)
        heads["Head_Jaw"] = Vector((x_hj, y_hj, z_hj))
    else:
        heads["Head_Jaw"] = defaults["Head_Jaw"].copy()

    # 2. Weapon_R: Right forelimb shoulder OR Right Hydra Dragon Neck root on PART_UPPER_BODY
    verts_wr = part_coords.get(PART_WEAPON_R, [])
    wr_bias = 1.0 if is_hydra else (-0.6 if is_quadruped else 0.0)
    c_wr = _junction_cluster_centroid(
        verts_wr,
        seam_upper.get(PART_WEAPON_R, []),
        kd_body,
        H,
        tie_z_bias=wr_bias,
    )
    if c_wr is not None:
        mean_x_wr = sum(c.x for c in verts_wr) / len(verts_wr)
        if mean_x_wr >= 0.02:
            x_wr = _clamp(c_wr.x, 0.03, 0.38)
        else:
            x_wr = _clamp(c_wr.x, -0.08, 0.28)
        y_wr = _clamp(c_wr.y, -0.32, 0.44)
        z_wr = _clamp(c_wr.z, 0.18 * H, 0.88 * H)
        heads["Weapon_R"] = Vector((x_wr, y_wr, z_wr))
    else:
        heads["Weapon_R"] = defaults["Weapon_R"].copy()

    # 3. Shield_L: Left forelimb shoulder OR Left Hydra Dragon Neck root on PART_UPPER_BODY
    verts_sl = part_coords.get(PART_SHIELD_L, [])
    sl_bias = 1.0 if is_hydra else (-0.6 if is_quadruped else 0.0)
    c_sl = _junction_cluster_centroid(
        verts_sl,
        seam_upper.get(PART_SHIELD_L, []),
        kd_body,
        H,
        tie_z_bias=sl_bias,
    )
    if c_sl is not None:
        mean_x_sl = sum(c.x for c in verts_sl) / len(verts_sl)
        if mean_x_sl <= -0.02:
            x_sl = _clamp(c_sl.x, -0.38, -0.03)
        else:
            x_sl = _clamp(c_sl.x, -0.28, 0.08)
        y_sl = _clamp(c_sl.y, -0.32, 0.44)
        z_sl = _clamp(c_sl.z, 0.18 * H, 0.88 * H)
        heads["Shield_L"] = Vector((x_sl, y_sl, z_sl))
    else:
        heads["Shield_L"] = defaults["Shield_L"].copy()

    # 4. Wings_Tail: dorsal wing-root junction on PART_UPPER_BODY (or pelvic tail-root on PART_LOWER_BODY)
    verts_wt = part_coords.get(PART_WINGS_TAIL, [])
    if len(verts_wt) >= 4:
        seam_wt_up = seam_upper.get(PART_WINGS_TAIL, [])
        has_upper_wing_junction = len(seam_wt_up) >= 3
        if not has_upper_wing_junction and kd_upper is not None:
            min_d_up = min(kd_upper.find(c)[2] for c in verts_wt)
            has_upper_wing_junction = min_d_up <= max(0.12, 0.08 * H)

        if has_upper_wing_junction:
            c_wt = _junction_cluster_centroid(
                verts_wt, seam_wt_up, kd_upper, H, tie_z_bias=0.0
            )
        else:
            c_wt = _junction_cluster_centroid(
                verts_wt,
                seam_lower_wt,
                kd_lower if kd_lower is not None else kd_upper,
                H,
                tie_z_bias=-0.4,
            )

        if c_wt is not None:
            mean_x_wt = sum(c.x for c in verts_wt) / len(verts_wt)
            x_wt = 0.0 if abs(mean_x_wt) < 0.05 else _clamp(c_wt.x, -0.12, 0.12)
            y_wt = _clamp(c_wt.y, -0.40, 0.20)
            z_wt = _clamp(c_wt.z, 0.16 * H, 0.82 * H)
            heads["Wings_Tail"] = Vector((x_wt, y_wt, z_wt))
        else:
            heads["Wings_Tail"] = defaults["Wings_Tail"].copy()
    else:
        heads["Wings_Tail"] = defaults["Wings_Tail"].copy()

    return z_spine_lo, z_spine_mid, z_spine_hi, heads


# ==============================================================================
# CRAG-SAFE, ANATOMY-AWARE SKINNING WEIGHT COMPUTATION
# ==============================================================================
def _sanitize_vertex_weights(raw_weights: Dict[str, float]) -> Dict[str, float]:
    """
    Strict glTF 2.0 Skinning Sanitization:
    1. Keep at most top 4 positive bone weights.
    2. Normalize and discard any weight < 1e-4.
    3. Re-normalize in IEEE-754 float32-safe precision so Blender's internal
       MDeformWeight float32 values sum to 1.0 within ~1e-7.
    """
    positive = [
        (bname, float(w))
        for bname, w in raw_weights.items()
        if w > 0.0 and bname in BONE_NAMES
    ]
    if not positive:
        return {"Root": 1.0}

    positive.sort(key=lambda item: item[1], reverse=True)
    top = positive[:MAX_INFLUENCES_PER_VERTEX]

    s0 = sum(w for _, w in top)
    if s0 <= 1e-12:
        return {"Root": 1.0}

    filtered = [
        (bname, w / s0)
        for bname, w in top
        if (w / s0) >= MIN_WEIGHT_THRESHOLD
    ]
    if not filtered:
        return {top[0][0]: 1.0}

    if len(filtered) == 1:
        return {filtered[0][0]: 1.0}

    s1 = sum(w for _, w in filtered)
    normed = [(bname, w / s1) for bname, w in filtered]
    normed.sort(key=lambda item: item[1], reverse=True)

    tail_f32: List[Tuple[str, float]] = []
    tail_sum = 0.0
    for bname, w in normed[1:]:
        wf = _to_f32(w)
        if wf >= MIN_WEIGHT_THRESHOLD:
            tail_f32.append((bname, wf))
            tail_sum += wf

    lead_w = _to_f32(max(MIN_WEIGHT_THRESHOLD, 1.0 - tail_sum))
    result: Dict[str, float] = {normed[0][0]: lead_w}
    for bname, wf in tail_f32:
        result[bname] = wf
    return result


def _compute_all_vertex_weights(
    mesh_data: bpy.types.Mesh,
    part_ids: Sequence[int],
    H: float,
    z_spine_mid: float,
    bone_heads: Dict[str, Vector],
) -> List[Dict[str, float]]:
    """
    Compute smooth, organic, crag-grounded, seam-blended vertex weights:
    - PART_PEDESTAL (crag rock) & ground plane (z <= 0.045m): 100% Root (0.0 drift).
    - PART_LOWER_BODY: smooth 3D KDTree seam blend from PART_PEDESTAL (Root) into
      Spine_Lower and across the waist into Spine_Upper.
    - PART_UPPER_BODY: Spine_Upper core with smooth waist & neck-collar transitions.
    - PART_HEAD_JAW, PART_WEAPON_R, PART_SHIELD_L, PART_WINGS_TAIL: zero Root lock
      for z >= 0.08m (so crouching quadruped paws at z ~ 0.16m and sweeping tails at
      z ~ 0.14m articulate freely!), smooth shoulder/neck/wing/tail root blending at
      proximal junctions, ramping to crisp distal control out to 0.56m wingspans.
    """
    verts = mesh_data.vertices
    n_verts = len(verts)

    part_coords: Dict[int, List[Vector]] = {}
    for i in range(n_verts):
        pid = int(part_ids[i])
        part_coords.setdefault(pid, []).append(verts[i].co.copy())

    kd_ped = _build_kdtree(part_coords.get(PART_PEDESTAL, []))
    kd_lower = _build_kdtree(part_coords.get(PART_LOWER_BODY, []))
    kd_upper = _build_kdtree(part_coords.get(PART_UPPER_BODY, []))
    kd_head = _build_kdtree(part_coords.get(PART_HEAD_JAW, []))

    part_to_bone = {
        PART_HEAD_JAW: "Head_Jaw",
        PART_WEAPON_R: "Weapon_R",
        PART_SHIELD_L: "Shield_L",
        PART_WINGS_TAIL: "Wings_Tail",
    }

    app_spans: Dict[int, float] = {}
    app_min_z: Dict[int, float] = {}
    for pid, bname in part_to_bone.items():
        pivot = bone_heads[bname]
        p_coords = part_coords.get(pid, [])
        if p_coords:
            app_min_z[pid] = min(c.z for c in p_coords)
            max_d = max((c - pivot).length for c in p_coords)
            app_spans[pid] = max(max_d, 0.16 * H, 0.14)
        else:
            app_min_z[pid] = H
            app_spans[pid] = max(0.24 * H, 0.18)

    raw_list: List[Dict[str, float]] = []
    pinned_root = [False] * n_verts

    for i in range(n_verts):
        co = verts[i].co
        z = co.z
        pid = int(part_ids[i])

        # 1. Jagged stone crag (PART_PEDESTAL) & universal floor contact (z <= 0.045m):
        #    Lock 100% to Root so crag rock never wobbles or drifts.
        if pid == PART_PEDESTAL or z <= 0.045:
            raw_list.append({"Root": 1.0})
            pinned_root[i] = True
            continue

        # 2. Haunches, hindlegs & lower serpent coil gripping the crag (PART_LOWER_BODY)
        if pid == PART_LOWER_BODY:
            if kd_ped is not None:
                d_ped = kd_ped.find(co)[2]
                s_crag = _smoothstep(0.008, 0.115, d_ped)
            else:
                s_crag = _smoothstep(0.045, 0.18, z)

            if kd_upper is not None:
                d_up = kd_upper.find(co)[2]
                u_waist = 0.42 * (1.0 - _smoothstep(0.0, 0.09 * H, d_up))
            else:
                u_waist = _smoothstep(z_spine_mid - 0.06 * H, z_spine_mid + 0.10 * H, z)

            raw_list.append(
                {
                    "Root": 1.0 - s_crag,
                    "Spine_Lower": s_crag * (1.0 - u_waist),
                    "Spine_Upper": s_crag * u_waist,
                }
            )
            continue

        # 3. Armored ribcage, shoulder girdle & dorsal spine (PART_UPPER_BODY)
        if pid == PART_UPPER_BODY:
            if kd_lower is not None:
                d_lo = kd_lower.find(co)[2]
                l_waist = 0.42 * (1.0 - _smoothstep(0.0, 0.09 * H, d_lo))
            else:
                l_waist = 1.0 - _smoothstep(
                    z_spine_mid - 0.08 * H, z_spine_mid + 0.06 * H, z
                )

            if kd_head is not None:
                d_hj = kd_head.find(co)[2]
                h_collar = 0.18 * (1.0 - _smoothstep(0.0, 0.055 * H, d_hj))
            else:
                h_collar = 0.0

            w_up = max(0.0, 1.0 - l_waist - h_collar)
            raw_list.append(
                {
                    "Spine_Lower": l_waist,
                    "Spine_Upper": w_up,
                    "Head_Jaw": h_collar,
                }
            )
            continue

        # 4. Sweeping dragon wings (2 or 4 wings) + sinuous/club dragon tail (PART_WINGS_TAIL)
        if pid == PART_WINGS_TAIL:
            pivot = bone_heads["Wings_Tail"]
            d_piv = (co - pivot).length / app_spans[PART_WINGS_TAIL]
            d_up = kd_upper.find(co)[2] if kd_upper is not None else 0.25 * H
            d_lo = kd_lower.find(co)[2] if kd_lower is not None else 0.25 * H

            # Distinguish upper/outer wings from low pelvis-rooted dragon tails smoothly in 3D
            tail_aff = _smoothstep(-0.05, 0.08, d_up - d_lo) * (
                1.0 - _smoothstep(0.32 * H, 0.50 * H, z)
            )

            # Wing weight profile: ~0.68 at scapular root -> 1.0 across wide wingspan
            d_wing_eff = max(d_piv, d_up / max(0.28 * H, 0.22))
            w_wt_wing = 0.68 + 0.32 * _smoothstep(0.03, 0.46, d_wing_eff)
            w_up_wing = 1.0 - w_wt_wing

            # Tail weight profile: ~0.58 Wings_Tail + ~0.42 Spine_Lower at pelvic base,
            # ramping to ~0.94 Wings_Tail + ~0.06 Spine_Lower toward distal tail tip/club
            d_tail_eff = d_lo / max(0.26 * H, 0.22)
            w_wt_tail = 0.58 + 0.36 * _smoothstep(0.04, 0.75, d_tail_eff)
            w_lo_tail = 1.0 - w_wt_tail

            weights = {
                "Wings_Tail": (1.0 - tail_aff) * w_wt_wing + tail_aff * w_wt_tail,
                "Spine_Upper": (1.0 - tail_aff) * w_up_wing,
                "Spine_Lower": tail_aff * w_lo_tail,
            }

            # Only blend toward Root below z < 0.08m if tail tip actually touches ground (z <= 0.045m)
            if app_min_z[PART_WINGS_TAIL] <= 0.045 and z < 0.08:
                c_gnd = _smoothstep(0.045, 0.08, z)
                weights = {
                    "Root": 1.0 - c_gnd,
                    **{k: c_gnd * val for k, val in weights.items()},
                }

            raw_list.append(weights)
            continue

        # 5. Primary Dragon Head/Jaw, Right Forelimb/Hydra-Neck, Left Forelimb/Hydra-Neck
        if pid in (PART_HEAD_JAW, PART_WEAPON_R, PART_SHIELD_L):
            bname = part_to_bone[pid]
            pivot = bone_heads[bname]
            d_piv = (co - pivot).length / app_spans[pid]
            d_up = kd_upper.find(co)[2] if kd_upper is not None else d_piv * app_spans[pid]
            d_eff = max(d_piv, d_up / max(0.26 * H, 0.20))

            # Proximal socket (~0.31 Spine_Upper + ~0.69 appendage) -> Distal claws/snout (1.0 appendage)
            w_app = 0.69 + 0.31 * _smoothstep(0.03, 0.48, d_eff)
            w_spine = 1.0 - w_app
            weights = {
                bname: w_app,
                "Spine_Upper": w_spine,
            }

            # Never pull z >= 0.08m onto Root; only ramp 0.045..0.08m if limb touches ground z <= 0.045m
            if app_min_z[pid] <= 0.045 and z < 0.08:
                c_gnd = _smoothstep(0.045, 0.08, z)
                weights = {
                    "Root": 1.0 - c_gnd,
                    **{k: c_gnd * val for k, val in weights.items()},
                }

            raw_list.append(weights)
            continue

        # Fallback for any unexpected PartID
        raw_list.append({"Spine_Upper": 1.0})

    # Crag-safe topological seam relaxation across welded anatomical junctions
    # (never unpins PART_PEDESTAL, and never bleeds PART_PEDESTAL Root onto limbs/wings/tails!)
    adj: List[List[int]] = [[] for _ in range(n_verts)]
    seam_ring = [False] * n_verts

    def _is_valid_seam_pair(pa: int, pb: int) -> bool:
        if pa == pb:
            return False
        if pa == PART_PEDESTAL or pb == PART_PEDESTAL:
            return (pa == PART_LOWER_BODY) or (pb == PART_LOWER_BODY)
        return True

    for edge in mesh_data.edges:
        u, v = edge.vertices[0], edge.vertices[1]
        pu, pv = int(part_ids[u]), int(part_ids[v])
        if pu == pv or _is_valid_seam_pair(pu, pv):
            adj[u].append(v)
            adj[v].append(u)
            if pu != pv:
                seam_ring[u] = True
                seam_ring[v] = True

    seam_zone = list(seam_ring)
    for i in range(n_verts):
        if seam_ring[i]:
            for nb in adj[i]:
                seam_zone[nb] = True

    if any(seam_zone):
        for _ in range(2):
            updated = list(raw_list)
            for i in range(n_verts):
                if pinned_root[i] or not seam_zone[i] or not adj[i]:
                    continue
                alpha = 0.30 if seam_ring[i] else 0.16
                nb_inv = 1.0 / float(len(adj[i]))
                merged: Dict[str, float] = {}
                for bname, val in raw_list[i].items():
                    merged[bname] = merged.get(bname, 0.0) + (1.0 - alpha) * val
                for nb in adj[i]:
                    w_scale = alpha * nb_inv
                    for bname, val in raw_list[nb].items():
                        merged[bname] = merged.get(bname, 0.0) + w_scale * val
                updated[i] = merged
            raw_list = updated

    return [_sanitize_vertex_weights(w_dict) for w_dict in raw_list]


# ==============================================================================
# PUBLIC API: 1. rig_dragon_piece
# ==============================================================================
def rig_dragon_piece(
    piece_name: str,
    mesh_obj: bpy.types.Object,
    part_ids: list[int],
) -> bpy.types.Object:
    """
    Construct the 7-bone articulated draconic armature for `piece_name`,
    place branch joint pivots at true `PART_UPPER_BODY` junction roots, bind
    `mesh_obj` with crag-safe glTF 2.0 skinning weights, and set QUATERNION mode.
    """
    if mesh_obj is None or mesh_obj.type != "MESH":
        raise ValueError("mesh_obj must be a valid Blender MESH object.")

    mesh_data: bpy.types.Mesh = mesh_obj.data
    n_verts = len(mesh_data.vertices)

    if part_ids is None or len(part_ids) == 0:
        attr = mesh_data.attributes.get("PartID")
        if attr is not None and len(attr.data) == n_verts:
            part_ids = [int(item.value) for item in attr.data]
        else:
            raise ValueError("part_ids must match len(mesh_obj.data.vertices).")
    elif len(part_ids) != n_verts:
        raise ValueError(
            f"part_ids length ({len(part_ids)}) != vertex count ({n_verts})."
        )

    # Persist PartID point attribute on mesh_data so validate_rig can inspect crag vs limbs
    part_attr = mesh_data.attributes.get("PartID")
    if part_attr is None:
        part_attr = mesh_data.attributes.new(name="PartID", type="INT", domain="POINT")
    if (
        part_attr.domain == "POINT"
        and part_attr.data_type == "INT"
        and len(part_attr.data) == n_verts
    ):
        part_attr.data.foreach_set("value", [int(p) for p in part_ids])

    piece_key, H = _resolve_piece_key_and_height(piece_name, mesh_obj)

    if (
        bpy.context.active_object is not None
        and bpy.context.active_object.mode != "OBJECT"
    ):
        bpy.ops.object.mode_set(mode="OBJECT")

    if len(mesh_obj.users_collection) == 0:
        bpy.context.collection.objects.link(mesh_obj)

    z_spine_lo, z_spine_mid, z_spine_hi, branch_heads = (
        _compute_spine_and_branch_pivots(piece_key, H, mesh_data, part_ids)
    )

    arm_data_name = f"{piece_name}_armature_data"
    arm_obj_name = f"{piece_name}_armature"

    arm_data = bpy.data.armatures.new(arm_data_name)
    arm_obj = bpy.data.objects.new(arm_obj_name, arm_data)
    arm_obj.location = Vector((0.0, 0.0, 0.0))
    arm_obj.rotation_mode = "XYZ"
    arm_obj.rotation_euler = Euler((0.0, 0.0, 0.0), "XYZ")
    arm_obj.scale = Vector((1.0, 1.0, 1.0))
    bpy.context.collection.objects.link(arm_obj)

    for sel_obj in list(bpy.context.selected_objects):
        sel_obj.select_set(False)
    arm_obj.select_set(True)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode="EDIT")

    head_hj = branch_heads["Head_Jaw"]
    head_wr = branch_heads["Weapon_R"]
    head_sl = branch_heads["Shield_L"]
    head_wt = branch_heads["Wings_Tail"]

    bone_specs = [
        (
            "Root",
            None,
            False,
            Vector((0.0, 0.0, 0.0)),
            Vector((0.0, 0.0, z_spine_lo)),
        ),
        (
            "Spine_Lower",
            "Root",
            True,
            Vector((0.0, 0.0, z_spine_lo)),
            Vector((0.0, 0.0, z_spine_mid)),
        ),
        (
            "Spine_Upper",
            "Spine_Lower",
            True,
            Vector((0.0, 0.0, z_spine_mid)),
            Vector((0.0, 0.0, z_spine_hi)),
        ),
        (
            "Head_Jaw",
            "Spine_Upper",
            False,
            head_hj,
            head_hj + Vector((0.0, 0.0, max(0.16, 0.22 * H))),
        ),
        (
            "Weapon_R",
            "Spine_Upper",
            False,
            head_wr,
            head_wr + Vector((0.0, 0.0, max(0.16, 0.22 * H))),
        ),
        (
            "Shield_L",
            "Spine_Upper",
            False,
            head_sl,
            head_sl + Vector((0.0, 0.0, max(0.16, 0.22 * H))),
        ),
        (
            "Wings_Tail",
            "Spine_Upper",
            False,
            head_wt,
            head_wt + Vector((0.0, 0.0, max(0.18, 0.24 * H))),
        ),
    ]

    edit_bones: Dict[str, bpy.types.EditBone] = {}
    for bname, parent_name, use_conn, b_head, b_tail in bone_specs:
        eb = arm_data.edit_bones.new(bname)
        eb.head = b_head
        eb.tail = b_tail
        eb.use_deform = True
        if parent_name is not None:
            eb.parent = edit_bones[parent_name]
            eb.use_connect = use_conn
        edit_bones[bname] = eb

    # Enforce exact roll = 0.0 AFTER head/tail/parent/connect assignment
    for bname in BONE_NAMES:
        edit_bones[bname].roll = 0.0

    bpy.ops.object.mode_set(mode="OBJECT")

    for mod in list(mesh_obj.modifiers):
        if mod.type == "ARMATURE":
            mesh_obj.modifiers.remove(mod)

    mesh_obj.parent = arm_obj
    mesh_obj.matrix_parent_inverse = arm_obj.matrix_world.inverted()

    arm_mod = mesh_obj.modifiers.new(name="Armature", type="ARMATURE")
    arm_mod.object = arm_obj
    arm_mod.use_vertex_groups = True
    arm_mod.use_bone_envelopes = False

    mesh_obj.vertex_groups.clear()
    vgroups = {bname: mesh_obj.vertex_groups.new(name=bname) for bname in BONE_NAMES}

    all_bone_heads = {
        "Root": Vector((0.0, 0.0, 0.0)),
        "Spine_Lower": Vector((0.0, 0.0, z_spine_lo)),
        "Spine_Upper": Vector((0.0, 0.0, z_spine_mid)),
        **branch_heads,
    }

    sanitized_weights = _compute_all_vertex_weights(
        mesh_data=mesh_data,
        part_ids=part_ids,
        H=H,
        z_spine_mid=z_spine_mid,
        bone_heads=all_bone_heads,
    )

    for v_idx, w_map in enumerate(sanitized_weights):
        for bname, w_val in w_map.items():
            vgroups[bname].add([v_idx], float(w_val), "REPLACE")

    for pbone in arm_obj.pose.bones:
        pbone.rotation_mode = "QUATERNION"
        pbone.location = Vector((0.0, 0.0, 0.0))
        pbone.rotation_quaternion = Quaternion((1.0, 0.0, 0.0, 0.0))
        pbone.scale = Vector((1.0, 1.0, 1.0))

    bpy.context.view_layer.update()
    return arm_obj


# ==============================================================================
# PUBLIC API: 2. validate_rig
# ==============================================================================
def validate_rig(
    arm_obj: bpy.types.Object,
    mesh_obj: bpy.types.Object,
    part_ids: Optional[Sequence[int]] = None,
) -> dict:
    """
    Validate 7-bone draconic hierarchy, vertical bone axes & zero roll,
    glTF 2.0 vertex weight invariants (<= 4 influences, >= 1e-4, IEEE-754
    float32 sum == 1.0, grounded crag PART_PEDESTAL at Z <= 0.16m / Z <= 0.04m
    with 0.0 drift), and clean non-NaN deformation under articulated poses.
    """
    errors: List[str] = []

    if arm_obj is None or arm_obj.type != "ARMATURE":
        return {"valid": False, "passed": False, "errors": ["Invalid armature object."]}
    if mesh_obj is None or mesh_obj.type != "MESH":
        return {"valid": False, "passed": False, "errors": ["Invalid mesh object."]}

    if (
        bpy.context.active_object is not None
        and bpy.context.active_object.mode != "OBJECT"
    ):
        bpy.ops.object.mode_set(mode="OBJECT")

    bones = arm_obj.data.bones
    bone_names = [b.name for b in bones]
    if bone_names != BONE_NAMES:
        errors.append(f"Bone list mismatch: expected {BONE_NAMES}, got {bone_names}.")

    expected_parents = {
        "Root": (None, False),
        "Spine_Lower": ("Root", True),
        "Spine_Upper": ("Spine_Lower", True),
        "Head_Jaw": ("Spine_Upper", False),
        "Weapon_R": ("Spine_Upper", False),
        "Shield_L": ("Spine_Upper", False),
        "Wings_Tail": ("Spine_Upper", False),
    }

    vertical_axes_ok = True
    identical_axes_ok = True
    ref_rot_3x3: Optional[Matrix] = None

    for bname in BONE_NAMES:
        if bname not in bones:
            vertical_axes_ok = False
            identical_axes_ok = False
            continue
        b = bones[bname]
        exp_parent, exp_conn = expected_parents[bname]
        actual_parent = b.parent.name if b.parent else None
        if actual_parent != exp_parent:
            errors.append(
                f"Bone '{bname}' parent mismatch: expected {exp_parent}, got {actual_parent}."
            )
        if bool(b.use_connect) != exp_conn:
            errors.append(
                f"Bone '{bname}' use_connect mismatch: expected {exp_conn}, got {b.use_connect}."
            )
        if not b.use_deform:
            errors.append(f"Bone '{bname}' has use_deform=False.")

        vec = b.tail_local - b.head_local
        if vec.length < 0.05:
            vertical_axes_ok = False
            errors.append(f"Bone '{bname}' length too short ({vec.length:.5f}).")
        else:
            unit = vec.normalized()
            if (unit - Vector((0.0, 0.0, 1.0))).length > 1e-5:
                vertical_axes_ok = False
                errors.append(
                    f"Bone '{bname}' is not strictly vertical: dir={tuple(unit)}."
                )

        rot3 = b.matrix_local.to_3x3()
        if ref_rot_3x3 is None:
            ref_rot_3x3 = rot3
        else:
            max_mat_diff = max(
                abs(rot3[r][c] - ref_rot_3x3[r][c])
                for r in range(3)
                for c in range(3)
            )
            if max_mat_diff > 1e-5:
                identical_axes_ok = False
                errors.append(
                    f"Bone '{bname}' local axes differ from Root (diff={max_mat_diff:.6f})."
                )

    quat_ok = all(pb.rotation_mode == "QUATERNION" for pb in arm_obj.pose.bones)
    if not quat_ok:
        errors.append("Not all PoseBones use rotation_mode == 'QUATERNION'.")

    if mesh_obj.parent != arm_obj:
        errors.append("mesh_obj.parent is not arm_obj.")

    arm_mods = [
        m for m in mesh_obj.modifiers if m.type == "ARMATURE" and m.object == arm_obj
    ]
    if not arm_mods:
        errors.append("mesh_obj is missing an ARMATURE modifier pointing to arm_obj.")

    vg_index_to_name = {vg.index: vg.name for vg in mesh_obj.vertex_groups}
    missing_vgs = [b for b in BONE_NAMES if b not in mesh_obj.vertex_groups]
    if missing_vgs:
        errors.append(f"Missing vertex groups: {missing_vgs}.")

    verts = mesh_obj.data.vertices
    n_verts = len(verts)

    resolved_pids: Optional[List[int]] = None
    if part_ids is not None and len(part_ids) == n_verts:
        resolved_pids = [int(p) for p in part_ids]
    else:
        attr = mesh_obj.data.attributes.get("PartID")
        if (
            attr is not None
            and attr.domain == "POINT"
            and len(attr.data) == n_verts
        ):
            resolved_pids = [int(item.value) for item in attr.data]

    unweighted_count = 0
    over4_count = 0
    sub_thresh_count = 0
    max_inf = 0
    max_sum_err = 0.0
    grounded_indices: List[int] = []
    ungrounded_crag_count = 0

    bone_set = set(BONE_NAMES)
    for v_idx, v in enumerate(verts):
        deform_groups = [
            g for g in v.groups if vg_index_to_name.get(g.group) in bone_set
        ]
        k = len(deform_groups)
        if k > max_inf:
            max_inf = k

        if k == 0:
            unweighted_count += 1
            continue
        if k > MAX_INFLUENCES_PER_VERTEX:
            over4_count += 1

        w_sum = 0.0
        root_w = 0.0
        for g in deform_groups:
            w = float(g.weight)
            w_sum += w
            if w < MIN_WEIGHT_THRESHOLD - 1e-6:
                sub_thresh_count += 1
            if vg_index_to_name.get(g.group) == "Root":
                root_w = w

        sum_err = abs(w_sum - 1.0)
        if sum_err > max_sum_err:
            max_sum_err = sum_err

        if resolved_pids is not None:
            is_grounded_crag = (
                resolved_pids[v_idx] == PART_PEDESTAL and v.co.z <= 0.16
            ) or (v.co.z <= 0.04)
        else:
            is_grounded_crag = v.co.z <= 0.04

        if is_grounded_crag:
            grounded_indices.append(v_idx)
            if abs(root_w - 1.0) > 1e-6:
                ungrounded_crag_count += 1

    if unweighted_count > 0:
        errors.append(f"{unweighted_count} unweighted vertices detected.")
    if over4_count > 0:
        errors.append(f"{over4_count} vertices exceed 4 bone influences.")
    if sub_thresh_count > 0:
        errors.append(f"{sub_thresh_count} weights fall below 1e-4 threshold.")
    if max_sum_err > 1e-5:
        errors.append(f"Max vertex weight sum error {max_sum_err:.2e} > 1e-5.")
    if ungrounded_crag_count > 0:
        errors.append(
            f"{ungrounded_crag_count} grounded crag vertices not locked 100% to Root."
        )

    # Non-destructive articulated dragon combat pose evaluation
    saved_pose = {
        pb.name: (
            pb.location.copy(),
            pb.rotation_quaternion.copy(),
            pb.scale.copy(),
            pb.rotation_mode,
        )
        for pb in arm_obj.pose.bones
    }
    saved_action = (
        arm_obj.animation_data.action if arm_obj.animation_data else None
    )
    saved_nla_mutes = (
        [(tr, tr.mute) for tr in arm_obj.animation_data.nla_tracks]
        if arm_obj.animation_data
        else []
    )

    nan_count = 0
    max_disp = 0.0
    max_pedestal_drift = 0.0

    try:
        if arm_obj.animation_data:
            arm_obj.animation_data.action = None
            for tr, _ in saved_nla_mutes:
                tr.mute = True

        for pb in arm_obj.pose.bones:
            pb.location = Vector((0.0, 0.0, 0.0))
            pb.rotation_quaternion = Quaternion((1.0, 0.0, 0.0, 0.0))
            pb.scale = Vector((1.0, 1.0, 1.0))

        bpy.context.view_layer.update()
        deps_rest = bpy.context.evaluated_depsgraph_get()
        eval_rest_obj = mesh_obj.evaluated_get(deps_rest)
        eval_rest_mesh = eval_rest_obj.to_mesh()
        rest_coords = [v.co.copy() for v in eval_rest_mesh.vertices]
        eval_rest_obj.to_mesh_clear()

        test_rot_deg = {
            "Root": (0.0, 0.0, 0.0),
            "Spine_Lower": (-10.0, 5.0, 3.0),
            "Spine_Upper": (-16.0, -8.0, 5.0),
            "Head_Jaw": (-24.0, 10.0, -4.0),
            "Weapon_R": (-36.0, 12.0, 16.0),
            "Shield_L": (-22.0, -10.0, -14.0),
            "Wings_Tail": (26.0, 8.0, 14.0),
        }
        for bname, (rx_d, ry_d, rz_d) in test_rot_deg.items():
            if bname in arm_obj.pose.bones:
                eul = Euler(
                    (math.radians(rx_d), math.radians(ry_d), math.radians(rz_d)),
                    "XYZ",
                )
                arm_obj.pose.bones[bname].rotation_quaternion = eul.to_quaternion()

        bpy.context.view_layer.update()
        deps_pose = bpy.context.evaluated_depsgraph_get()
        eval_pose_obj = mesh_obj.evaluated_get(deps_pose)
        eval_pose_mesh = eval_pose_obj.to_mesh()

        for idx, pv in enumerate(eval_pose_mesh.vertices):
            c = pv.co
            n = pv.normal
            if (
                not (math.isfinite(c.x) and math.isfinite(c.y) and math.isfinite(c.z))
                or not (
                    math.isfinite(n.x) and math.isfinite(n.y) and math.isfinite(n.z)
                )
            ):
                nan_count += 1
                continue

            disp = (c - rest_coords[idx]).length
            if disp > max_disp:
                max_disp = disp

        for g_idx in grounded_indices:
            drift = (eval_pose_mesh.vertices[g_idx].co - rest_coords[g_idx]).length
            if drift > max_pedestal_drift:
                max_pedestal_drift = drift

        eval_pose_obj.to_mesh_clear()
    finally:
        for bname, (loc, quat, scl, rmode) in saved_pose.items():
            pb = arm_obj.pose.bones[bname]
            pb.rotation_mode = rmode
            pb.location = loc
            pb.rotation_quaternion = quat
            pb.scale = scl
        if arm_obj.animation_data:
            arm_obj.animation_data.action = saved_action
            for tr, mute_state in saved_nla_mutes:
                tr.mute = mute_state
        bpy.context.view_layer.update()

    if nan_count > 0:
        errors.append(f"{nan_count} NaN/Inf vertices or normals during pose evaluation.")
    if n_verts > 0 and max_disp < 0.01:
        errors.append(
            f"Pose deformation displacement too small ({max_disp:.5f}m); skinning inactive."
        )
    if max_pedestal_drift > 1e-6:
        errors.append(
            f"Grounded crag drifted by {max_pedestal_drift:.2e}m under pose."
        )

    return {
        "valid": len(errors) == 0,
        "passed": len(errors) == 0,
        "armature_name": arm_obj.name,
        "mesh_name": mesh_obj.name,
        "bone_count": len(bone_names),
        "bone_names": bone_names,
        "bone_heads": {
            b.name: tuple(round(v, 5) for v in b.head_local) for b in bones
        },
        "bone_lengths": {
            b.name: round((b.tail_local - b.head_local).length, 5) for b in bones
        },
        "vertical_axes_ok": vertical_axes_ok,
        "identical_local_axes_ok": identical_axes_ok,
        "quaternion_mode_ok": quat_ok,
        "vertex_count": n_verts,
        "unweighted_vertices": unweighted_count,
        "over_4_influences": over4_count,
        "sub_threshold_weights": sub_thresh_count,
        "max_influences_per_vertex": max_inf,
        "max_weight_sum_error": float(max_sum_err),
        "grounded_pedestal_vertices": len(grounded_indices),
        "max_pedestal_drift": float(max_pedestal_drift),
        "pose_eval_nan_vertices": nan_count,
        "pose_eval_max_displacement": float(max_disp),
        "errors": errors,
    }


# ==============================================================================
# SELF-TEST IN HEADLESS BLENDER 5.2 (6 ANATOMICAL CARVED-STONE DRAGON BREEDS)
# ==============================================================================
def _build_synthetic_anatomical_dragon(
    piece_name: str, H: float
) -> Tuple[bpy.types.Object, List[int]]:
    """
    Construct synthetic anatomical Carved-Stone Dragon meshes perched on jagged
    stone crags across all 6 PIECE_SPECS (quadruped drakes `pawn`/`rook` with
    crouching forepaws at Z=0.16m & low tails at Z=0.14m, twin-headed hydra
    `bishop`, 4-winged `queen` out to r=0.54m, rearing `knight` & `king`).
    """
    bm = bmesh.new()
    part_layer = bm.verts.layers.int.new("PartID")

    def add_tube(rings: List[Tuple[Vector, float, float, int]], segs: int = 14):
        ring_verts: List[List[bmesh.types.BMVert]] = []
        for center, rx, ry, pid in rings:
            row = []
            for s in range(segs):
                ang = (2.0 * math.pi * s) / segs
                v = bm.verts.new(
                    Vector(
                        (
                            center.x + rx * math.cos(ang),
                            center.y + ry * math.sin(ang),
                            center.z,
                        )
                    )
                )
                v[part_layer] = pid
                row.append(v)
            ring_verts.append(row)

        for r_i in range(len(ring_verts) - 1):
            r0, r1 = ring_verts[r_i], ring_verts[r_i + 1]
            for s in range(segs):
                s_next = (s + 1) % segs
                bm.faces.new((r0[s], r0[s_next], r1[s_next], r1[s]))

        bm.faces.new(list(reversed(ring_verts[0])))
        bm.faces.new(ring_verts[-1])

    # Jagged stone crag base (PART_PEDESTAL = 0, Z in [0.0, 0.21], r <= 0.46m)
    add_tube(
        [
            (Vector((0.0, 0.0, 0.00)), 0.44, 0.42, PART_PEDESTAL),
            (Vector((0.02, -0.02, 0.11)), 0.39, 0.37, PART_PEDESTAL),
            (Vector((-0.01, 0.01, 0.20)), 0.28, 0.27, PART_PEDESTAL),
        ],
        segs=16,
    )

    if piece_name in ("pawn", "rook"):
        # Quadruped dragon: horizontal spine + downward-crouching forelimbs to Z=0.16m + tail at Z=0.14m
        add_tube(
            [
                (Vector((0.0, -0.14, 0.19)), 0.16, 0.15, PART_LOWER_BODY),
                (Vector((0.0, -0.12, 0.38 * H)), 0.17, 0.18, PART_LOWER_BODY),
                (Vector((0.0, 0.06, 0.43 * H)), 0.18, 0.19, PART_UPPER_BODY),
                (Vector((0.0, 0.20, 0.48 * H)), 0.15, 0.15, PART_UPPER_BODY),
                (Vector((0.0, 0.26, 0.64 * H)), 0.12, 0.14, PART_HEAD_JAW),
                (Vector((0.0, 0.34, H)), 0.07, 0.11, PART_HEAD_JAW),
            ],
            segs=14,
        )
        for side, pid in ((1.0, PART_WEAPON_R), (-1.0, PART_SHIELD_L)):
            add_tube(
                [
                    (Vector((side * 0.16, 0.15, 0.44 * H)), 0.06, 0.06, pid),
                    (Vector((side * 0.18, 0.20, 0.26)), 0.05, 0.05, pid),
                    (Vector((side * 0.20, 0.24, 0.16)), 0.055, 0.065, pid),
                ],
                segs=10,
            )
        add_tube(
            [
                (Vector((0.0, -0.22, 0.35 * H)), 0.07, 0.07, PART_WINGS_TAIL),
                (Vector((0.0, -0.34, 0.20)), 0.05, 0.05, PART_WINGS_TAIL),
                (Vector((0.06, -0.42, 0.14)), 0.06, 0.06, PART_WINGS_TAIL),
            ],
            segs=10,
        )
    elif piece_name == "bishop":
        # Twin-Headed Oracle Hydra-Wyrm: coiled torso + TWO horned dragon necks/skulls on PartID 4 & 5
        add_tube(
            [
                (Vector((0.0, -0.04, 0.19)), 0.21, 0.20, PART_LOWER_BODY),
                (Vector((0.0, 0.00, 0.40 * H)), 0.18, 0.17, PART_LOWER_BODY),
                (Vector((0.0, 0.03, 0.56 * H)), 0.17, 0.15, PART_UPPER_BODY),
                (Vector((0.0, 0.02, 0.66 * H)), 0.07, 0.09, PART_HEAD_JAW),
                (Vector((0.0, -0.02, 0.78 * H)), 0.03, 0.06, PART_HEAD_JAW),
            ],
            segs=14,
        )
        for side, pid in ((1.0, PART_WEAPON_R), (-1.0, PART_SHIELD_L)):
            add_tube(
                [
                    (Vector((side * 0.09, 0.05, 0.57 * H)), 0.065, 0.065, pid),
                    (Vector((side * 0.17, 0.16, 0.78 * H)), 0.055, 0.060, pid),
                    (Vector((side * 0.22, 0.28, H)), 0.050, 0.085, pid),
                ],
                segs=10,
            )
        for side in (-1.0, 1.0):
            add_tube(
                [
                    (Vector((side * 0.08, -0.07, 0.54 * H)), 0.04, 0.05, PART_WINGS_TAIL),
                    (Vector((side * 0.36, -0.18, 0.78 * H)), 0.03, 0.08, PART_WINGS_TAIL),
                ],
                segs=8,
            )
    else:
        # Rearing Winged Wyvern / 4-Winged Celestial Queen / Sovereign Arch-Dragon
        add_tube(
            [
                (Vector((0.0, -0.04, 0.19)), 0.21, 0.20, PART_LOWER_BODY),
                (Vector((0.0, -0.02, 0.42 * H)), 0.18, 0.17, PART_LOWER_BODY),
                (Vector((0.0, 0.02, 0.58 * H)), 0.19, 0.17, PART_UPPER_BODY),
                (Vector((0.0, 0.05, 0.72 * H)), 0.14, 0.14, PART_UPPER_BODY),
                (Vector((0.0, 0.09, 0.76 * H)), 0.11, 0.13, PART_HEAD_JAW),
                (Vector((0.0, 0.22, H)), 0.06, 0.11, PART_HEAD_JAW),
            ],
            segs=14,
        )
        for side, pid in ((1.0, PART_WEAPON_R), (-1.0, PART_SHIELD_L)):
            add_tube(
                [
                    (Vector((side * 0.15, 0.07, 0.60 * H)), 0.055, 0.055, pid),
                    (Vector((side * 0.22, 0.22, 0.52 * H)), 0.045, 0.050, pid),
                ],
                segs=10,
            )
        wing_span_x = 0.53 if piece_name in ("queen", "king") else 0.48
        for side in (-1.0, 1.0):
            add_tube(
                [
                    (Vector((side * 0.08, -0.08, 0.58 * H)), 0.045, 0.055, PART_WINGS_TAIL),
                    (Vector((side * 0.32, -0.16, 0.76 * H)), 0.040, 0.090, PART_WINGS_TAIL),
                    (Vector((side * wing_span_x, -0.22, 0.90 * H)), 0.025, 0.065, PART_WINGS_TAIL),
                ],
                segs=8,
            )
        add_tube(
            [
                (Vector((0.0, -0.18, 0.34 * H)), 0.06, 0.06, PART_WINGS_TAIL),
                (Vector((0.05, -0.36, 0.17)), 0.04, 0.04, PART_WINGS_TAIL),
            ],
            segs=8,
        )

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.verts.ensure_lookup_table()
    pids = [int(v[part_layer]) for v in bm.verts]

    mesh_data = bpy.data.meshes.new(f"{piece_name}_test_mesh")
    bm.to_mesh(mesh_data)
    bm.free()

    mesh_obj = bpy.data.objects.new(f"{piece_name}_test_mesh", mesh_data)
    bpy.context.collection.objects.link(mesh_obj)
    return mesh_obj, pids


def _run_self_test() -> None:
    print("\n=== [piece_rigging.py] Anatomical Crag-Dragon Blender 5.2 Self-Test ===")
    all_passed = True

    for piece_name, target_h in PIECE_SPECS:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        mesh_obj, pids = _build_synthetic_anatomical_dragon(piece_name, target_h)
        arm_obj = rig_dragon_piece(piece_name, mesh_obj, pids)
        report = validate_rig(arm_obj, mesh_obj)

        # Verify non-pedestal paws/tails at Z >= 0.08m have ZERO Root lock
        root_vg = mesh_obj.vertex_groups["Root"].index
        bad_limb_root = 0
        for idx, v in enumerate(mesh_obj.data.vertices):
            if pids[idx] in (PART_WEAPON_R, PART_SHIELD_L, PART_WINGS_TAIL) and v.co.z >= 0.08:
                for g in v.groups:
                    if g.group == root_vg and g.weight > 1e-4:
                        bad_limb_root += 1
        if bad_limb_root > 0:
            report["valid"] = False
            report["errors"].append(
                f"{bad_limb_root} limb/tail vertices at Z >= 0.08m erroneously weighted to Root."
            )

        status = "PASS" if report["valid"] else "FAIL"
        print(
            f"  [{status}] {piece_name:6s} (H={target_h:.2f}m) | "
            f"bones={report['bone_count']} | verts={report['vertex_count']} | "
            f"max_inf={report['max_influences_per_vertex']} | "
            f"sum_err={report['max_weight_sum_error']:.2e} | "
            f"crag_drift={report['max_pedestal_drift']:.2e} | "
            f"pose_disp={report['pose_eval_max_displacement']:.3f}m | "
            f"Weapon_R={report['bone_heads']['Weapon_R']} "
            f"Shield_L={report['bone_heads']['Shield_L']}"
        )
        if not report["valid"]:
            all_passed = False
            for err in report["errors"]:
                print(f"    -> ERROR: {err}")

    if not all_passed:
        raise AssertionError("piece_rigging.py validation failed!")
    print("=== ALL 6 ANATOMICAL DRAGON RIGS PASSED 100% VALIDATION ===\n")


if __name__ == "__main__":
    _run_self_test()
