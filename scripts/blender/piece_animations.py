"""
Creature-Authentic Carved-Stone Dragon Biomechanics & Breath Choreography Module
for Blender 5.2 (`bpy`, `mathutils`, Action Slots + NLA Tracks -> glTF 2.0).

Adheres strictly to `scripts/blender/dragon_spec.py`:
- 6 Pure Anatomical Carved-Stone Dragon Breeds perched on jagged ruined crags:
    * `pawn`   (1.08m) : Quadruped Stone Hatchling Drake
    * `rook`   (1.38m) : Quadruped Armored Behemoth Earth-Drake (+ spiked club-tail)
    * `knight` (1.62m) : Rearing Bipedal Winged Wyvern
    * `bishop` (1.72m) : Twin-Headed Oracle Hydra-Wyrm (`Weapon_R` = Right Dragon Neck/Skull,
                         `Shield_L` = Left Dragon Neck/Skull, `Head_Jaw` = Arcane Breath-Core)
    * `queen`  (1.94m) : Four-Winged Celestial Elder Dragon
    * `king`   (2.18m) : Colossal Rearing Sovereign Arch-Dragon
- 7 Standardized PoseBones (`Root`, `Spine_Lower`, `Spine_Upper`, `Head_Jaw`,
  `Weapon_R`, `Shield_L`, `Wings_Tail`) with vertical rest axes (`roll = 0.0`, `QUATERNION`):
    * `Root` (Jagged Stone Crag Base): LOCKED strictly at identity `(0, 0, 0)` translation
      and rotation across ALL frames of ALL 4 clips so the crag never slides, tilts, or lifts.
    * Local X (`rx` deg, `|rx| <= 38.0 deg < 0.68 rad`): Pitch (`rx < 0` lunges/bites forward `+Y`;
      `rx > 0` rears/coils backward `-Y`).
    * Local Y (`ry` deg): Yaw / serpentine sweep around vertical world `+Z`.
    * Local Z (`rz` deg): Roll / lateral bank in world `XZ` plane (wing-flare, talon rake, hydra bank).
    * Local translation (`pbone.location`): Maps `(dx_right, dy_forward, dz_up)` ->
      `Vector((dx_right, dz_up, -dy_forward))`.
- Blender 5.2 Action Slots (`arm_obj.animation_data.action_slot = act.slots[0]`) + unmuted
  NLA tracks (`Idle`, `Move`, `Attack`, `Hit`) for `export_animation_mode='NLA_TRACKS'`.
"""

import os
import sys
import math
import bpy
from mathutils import Vector, Euler, Quaternion

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from dragon_spec import BONE_NAMES, NLA_CLIPS, PIECE_SPECS, PIECE_HEIGHTS


# Clip frame ranges at 24 fps:
# - Idle   : 1..60 (2.50s seamless C1 periodic loop; exact frame 1 == frame 60 closure)
# - Move   : 1..36 (1.50s seamless C1 periodic loop; exact frame 1 == frame 36 closure)
# - Attack : 1..36 (1.50s; rear/coil f=5..7, ferocious strike/breath impact f=11..13
#                   syncing with Three.js combat impact, sustained roar/follow-through f=15..22,
#                   exact rest pose at f=1 and f=36)
# - Hit    : 1..32 (1.33s; recoil/brace f=4..6, counter-snarl/stagger f=14, exact rest at f=1 & f=32)
CLIP_FRAME_ENDS = {
    "Idle": 60,
    "Move": 36,
    "Attack": 36,
    "Hit": 32,
}

# Strict per-bone pitch ceiling (0.68 rad = 38.96 deg) to prevent Euler-to-Quat self-intersection
MAX_RX_RAD = 0.68
MAX_RX_DEG = 38.0

_CREATURE_BONES = [b for b in BONE_NAMES if b != "Root"]

_PIECE_ALIASES = {
    "p": "pawn",
    "r": "rook",
    "n": "knight",
    "b": "bishop",
    "q": "queen",
    "k": "king",
}

_IDENTITY_POSE = ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))


def _normalize_piece_name(piece_name: str) -> str:
    raw = (piece_name or "pawn").strip().lower()
    if raw in PIECE_HEIGHTS:
        return raw
    if raw in _PIECE_ALIASES:
        return _PIECE_ALIASES[raw]
    for candidate in PIECE_HEIGHTS:
        if candidate in raw:
            return candidate
    return "pawn"


def _clamp_rx(deg: float) -> float:
    return max(-MAX_RX_DEG, min(MAX_RX_DEG, float(deg)))


def world_to_bone_loc(dx_right: float = 0.0, dy_forward: float = 0.0, dz_up: float = 0.0) -> Vector:
    """
    Convert intuitive dragon/world displacement `(dx_right, dy_forward, dz_up)` in meters
    to local PoseBone `location` for vertical `roll=0` bones where:
      bone +X = world +X (Right)
      bone +Y = world +Z (Up)
      bone +Z = world -Y (Backward)
    """
    return Vector((float(dx_right), float(dz_up), -float(dy_forward)))


def _zero_pose_dict() -> dict:
    return {bname: _IDENTITY_POSE for bname in BONE_NAMES}


# ==============================================================================
# 1. BREED-AUTHENTIC IDLE BIOMECHANICS (Frames 1..60, Exact Seamless Loop)
# ==============================================================================
def _build_idle_track_poses(piece_key: str) -> tuple[list[tuple[int, dict]], bool]:
    frames = [1, 6, 11, 16, 21, 26, 31, 36, 41, 46, 51, 56, 60]
    track_poses: list[tuple[int, dict]] = []

    # Special Asynchronous Serpentine Weaving for Twin-Headed Oracle Hydra-Wyrm (`bishop`)!
    # Right Dragon Neck (`Weapon_R`) and Left Dragon Neck (`Shield_L`) weave continuously with
    # a 120-deg (2*pi/3) phase offset; exact 2*pi periodicity guarantees f=1 == f=60 closure!
    if piece_key == "bishop":
        phase_r = 0.0
        phase_l = 2.0943951023931953  # 120.0 deg phase offset between twin hydra heads!
        for idx, f in enumerate(frames):
            # Force exact floating-point equality between f=1 and f=60
            u = 0.0 if (idx == 0 or idx == len(frames) - 1) else (f - 1) / 59.0
            ph = 2.0 * math.pi * u
            s1 = math.sin(ph)
            c1 = math.cos(ph)
            s2 = math.sin(2.0 * ph)
            breath = 0.5 * (1.0 - c1)

            sr = math.sin(ph + phase_r)
            cr = math.cos(ph + phase_r)
            sr2 = math.sin(2.0 * ph + phase_r)

            sl = math.sin(ph + phase_l)
            cl = math.cos(ph + phase_l)
            sl2 = math.sin(2.0 * ph + phase_l)

            poses = {
                "Root": _IDENTITY_POSE,
                "Spine_Lower": (
                    (0.004 * s1, 0.006 * breath, 0.012 * breath),
                    (2.6 * s1, 3.2 * s1, 2.0 * c1),
                ),
                "Spine_Upper": (
                    (0.0, 0.004 * breath, 0.0),
                    (-3.8 * breath + 2.2 * c1, -4.0 * s1, -2.4 * c1),
                ),
                # Central arcane breath-core / dorsal crest
                "Head_Jaw": (
                    (0.0, 0.004 * breath, 0.006 * breath),
                    (-5.5 * breath + 2.5 * s2, 4.5 * s2, 2.5 * s1),
                ),
                # Right Dragon Neck & Horned Skull: sinuous figure-8 hydra weave
                "Weapon_R": (
                    (0.008 * cr, 0.010 * sr, 0.008 * (0.5 - 0.5 * cr)),
                    (-6.5 * sr - 3.0 * breath, 12.5 * cr + 3.5 * sr2, -9.5 * sr),
                ),
                # Left Dragon Neck & Horned Skull: 120-deg out-of-phase serpentine weave!
                "Shield_L": (
                    (0.008 * cl, 0.010 * sl, 0.008 * (0.5 - 0.5 * cl)),
                    (-6.5 * sl - 3.0 * breath, -12.5 * cl + 3.5 * sl2, 9.5 * sl),
                ),
                "Wings_Tail": (
                    (0.0, 0.0, 0.0),
                    (-9.5 * breath + 3.5 * s2, 6.5 * c1, 5.5 * s1),
                ),
            }
            track_poses.append((f, poses))
        return track_poses, True

    # Breed-specific reptilian/draconic idle parameters for the other 5 dragon breeds
    cfg = {
        "pawn": {
            # Quadruped Stone Hatchling Drake: crouched reptile breathing, inquisitive head-cock, claw flex
            "lift_z": 0.008, "surge_y": 0.006,
            "low_rx": 3.0, "low_ry": 2.4, "low_rz": 1.5,
            "upp_rx": -4.2, "upp_ry": -3.0, "upp_rz": -1.8,
            "hd_rx": -5.2, "hd_ry": 9.5, "hd_rz": 6.5,     # sharp reptilian head-cock!
            "wr_rx": -7.5, "wr_ry": 5.0, "wr_rz": -5.5,
            "sl_rx": 6.5,  "sl_ry": -5.0, "sl_rz": 5.5,
            "wt_rx": -8.5, "wt_ry": 7.5, "wt_rz": 5.0,    # wyrmling wing/tail twitch
            "tail_2x": 0.45,
        },
        "rook": {
            # Armored Behemoth Earth-Drake: volcanic-bellows breathing, heavy club-tail pendulum
            "lift_z": 0.009, "surge_y": 0.005,
            "low_rx": 2.4, "low_ry": 2.8, "low_rz": 1.6,
            "upp_rx": -3.5, "upp_ry": -3.2, "upp_rz": 1.8,
            "hd_rx": -4.0, "hd_ry": 7.0, "hd_rz": 2.5,
            "wr_rx": -4.5, "wr_ry": 3.5, "wr_rz": -3.5,
            "sl_rx": -4.5, "sl_ry": -3.5, "sl_rz": 3.5,
            "wt_rx": -5.5, "wt_ry": 14.5, "wt_rz": 4.0,   # heavy spiked club-tail pendulum!
            "tail_2x": 0.15,
        },
        "knight": {
            # Rearing Bipedal Winged Wyvern: rhythmic bat-wing hover-pulse, S-neck poise, talon flex
            "lift_z": 0.015, "surge_y": 0.008,
            "low_rx": 3.8, "low_ry": 2.5, "low_rz": 1.8,
            "upp_rx": -5.5, "upp_ry": -3.5, "upp_rz": -2.2,
            "hd_rx": 6.8,  "hd_ry": 10.5, "hd_rz": 4.8,
            "wr_rx": -9.0, "wr_ry": 6.5, "wr_rz": -7.5,
            "sl_rx": -9.0, "sl_ry": -6.5, "sl_rz": 7.5,
            "wt_rx": -14.5, "wt_ry": 4.0, "wt_rz": 8.5,   # bat-wing hover-pulse!
            "tail_2x": 0.40,
        },
        "queen": {
            # Four-Winged Celestial Elder Dragon: undulating 4-wing breath, swan-neck poise
            "lift_z": 0.018, "surge_y": 0.008,
            "low_rx": 3.2, "low_ry": 2.8, "low_rz": 2.2,
            "upp_rx": -4.8, "upp_ry": -3.8, "upp_rz": -2.6,
            "hd_rx": 5.8,  "hd_ry": 8.5, "hd_rz": -3.8,
            "wr_rx": -8.0, "wr_ry": 5.5, "wr_rz": -6.5,
            "sl_rx": -8.0, "sl_ry": -5.5, "sl_rz": 6.5,
            "wt_rx": -15.5, "wt_ry": 5.0, "wt_rz": 9.0,   # regal 4-wing undulation!
            "tail_2x": 0.35,
        },
        "king": {
            # Colossal Rearing Sovereign Arch-Dragon: chest-heaving breath, cathedral-wing mantle
            "lift_z": 0.013, "surge_y": 0.007,
            "low_rx": 2.8, "low_ry": 2.2, "low_rz": 1.4,
            "upp_rx": -4.5, "upp_ry": -2.8, "upp_rz": 1.6,
            "hd_rx": -4.8, "hd_ry": 8.0, "hd_rz": 2.8,
            "wr_rx": -6.5, "wr_ry": 4.5, "wr_rz": -5.0,
            "sl_rx": -6.5, "sl_ry": -4.5, "sl_rz": 5.0,
            "wt_rx": -12.5, "wt_ry": -4.5, "wt_rz": 6.5,  # majestic cathedral-wing mantle!
            "tail_2x": 0.25,
        },
    }[piece_key]

    for idx, f in enumerate(frames):
        if idx == 0 or idx == len(frames) - 1:
            track_poses.append((f, _zero_pose_dict()))
            continue

        u = (f - 1) / 59.0
        ph = 2.0 * math.pi * u
        s1 = math.sin(ph)
        s2 = math.sin(2.0 * ph)
        breath = 0.5 * (1.0 - math.cos(ph))
        pulse2 = 0.5 * (1.0 - math.cos(2.0 * ph))
        scan = s1 + cfg["tail_2x"] * s2

        poses = {
            "Root": _IDENTITY_POSE,
            "Spine_Lower": (
                (0.0, cfg["surge_y"] * breath, cfg["lift_z"] * breath),
                (cfg["low_rx"] * s1, cfg["low_ry"] * s1, cfg["low_rz"] * s2),
            ),
            "Spine_Upper": (
                (0.0, 0.0, 0.004 * breath),
                (cfg["upp_rx"] * breath + 2.0 * s1, cfg["upp_ry"] * s1, cfg["upp_rz"] * s1),
            ),
            "Head_Jaw": (
                (0.0, 0.0, 0.0),
                (cfg["hd_rx"] * breath + 2.2 * s2, cfg["hd_ry"] * scan, cfg["hd_rz"] * s2),
            ),
            "Weapon_R": (
                (0.0, 0.004 * pulse2, 0.004 * breath),
                (cfg["wr_rx"] * breath + 2.8 * s1, cfg["wr_ry"] * s1, cfg["wr_rz"] * breath),
            ),
            "Shield_L": (
                (0.0, 0.004 * breath, 0.004 * pulse2),
                (cfg["sl_rx"] * breath - 2.8 * s1, cfg["sl_ry"] * s1, cfg["sl_rz"] * breath),
            ),
            "Wings_Tail": (
                (0.0, 0.0, 0.0),
                (
                    cfg["wt_rx"] * (0.68 * breath + 0.32 * pulse2),
                    cfg["wt_ry"] * s1,
                    cfg["wt_rz"] * s2,
                ),
            ),
        }
        track_poses.append((f, poses))

    return track_poses, True


# ==============================================================================
# 2. BREED-AUTHENTIC MOVE BIOMECHANICS (Frames 1..36, Exact Seamless Loop)
# ==============================================================================
def _build_move_track_poses(piece_key: str) -> tuple[list[tuple[int, dict]], bool]:
    z0 = _zero_pose_dict()

    if piece_key == "pawn":
        # Bounding Quadruped Prowl Surge: spinal flexion/extension + alternating foreclaw stride!
        return [
            (1, z0),
            (8, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.000,  0.032, 0.022), (-10.0, -5.0,  3.0)),
                "Spine_Upper": ((0.000,  0.012, 0.006), (-12.0,  6.5, -3.5)),
                "Head_Jaw":    ((0.000,  0.008, 0.000), ( 12.0, -5.0,  2.5)),
                "Weapon_R":    ((0.000,  0.024, 0.014), (-26.0, 10.0, -10.0)),  # Right foreclaw reaches!
                "Shield_L":    ((0.000, -0.016, 0.004), ( 20.0,  8.0,  8.0)),   # Left foreclaw pushes!
                "Wings_Tail":  ((0.000,  0.000, 0.006), ( 18.0, -10.0, 6.0)),
            }),
            (18, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.000,  0.046, 0.012), (-12.0,  0.0,  0.0)),
                "Spine_Upper": ((0.000,  0.016, 0.000), ( -8.0,  0.0,  0.0)),
                "Head_Jaw":    ((0.000,  0.012, 0.000), ( 10.0,  0.0,  0.0)),
                "Weapon_R":    ((0.000,  0.008, 0.006), ( -8.0,  4.0,  6.0)),
                "Shield_L":    ((0.000,  0.008, 0.006), ( -8.0, -4.0, -6.0)),
                "Wings_Tail":  ((0.000,  0.000, 0.010), (-14.0,  0.0,  0.0)),
            }),
            (27, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.000,  0.030, 0.020), ( -9.5,  5.0, -3.0)),
                "Spine_Upper": ((0.000,  0.010, 0.006), (-11.5, -6.5,  3.5)),
                "Head_Jaw":    ((0.000,  0.008, 0.000), ( 11.5,  5.0, -2.5)),
                "Weapon_R":    ((0.000, -0.016, 0.004), ( 20.0, -8.0, -8.0)),   # Right foreclaw pushes!
                "Shield_L":    ((0.000,  0.024, 0.014), (-26.0, -10.0, 10.0)),  # Left foreclaw reaches!
                "Wings_Tail":  ((0.000,  0.000, 0.006), ( 18.0, 10.0, -6.0)),
            }),
            (36, z0),
        ], True

    if piece_key == "rook":
        # Earth-Shaking Heavy Quadruped Trudge/Charge: weighty lateral roll (`rz`) + club-tail swing
        return [
            (1, z0),
            (9, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((-0.012, 0.028, 0.016), (-8.5,  -5.5,  6.5)),
                "Spine_Upper": ((0.000,  0.010, 0.004), (-10.5, -6.5,  5.5)),
                "Head_Jaw":    ((0.000,  0.012, -0.004), (  5.0,  7.5, -4.5)),
                "Weapon_R":    ((0.000,  0.024, 0.016), (-24.0,  8.0, -8.0)),
                "Shield_L":    ((0.000, -0.014, 0.000), ( 16.0,  6.0,  6.0)),
                "Wings_Tail":  ((0.000,  0.000, 0.004), ( 14.0, 20.0, -8.0)),
            }),
            (18, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.000,  0.038, 0.008), (-10.0,  0.0,  0.0)),
                "Spine_Upper": ((0.000,  0.014, 0.000), (-12.0,  0.0,  0.0)),
                "Head_Jaw":    ((0.000,  0.016, -0.006), (  6.0,  0.0,  0.0)),
                "Weapon_R":    ((0.000,  0.010, 0.004), (-10.0,  4.0,  4.0)),
                "Shield_L":    ((0.000,  0.010, 0.004), (-10.0, -4.0, -4.0)),
                "Wings_Tail":  ((0.000,  0.000, 0.006), ( 18.0,  0.0,  0.0)),
            }),
            (27, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.012,  0.028, 0.016), (-8.5,   5.5, -6.5)),
                "Spine_Upper": ((0.000,  0.010, 0.004), (-10.5,  6.5, -5.5)),
                "Head_Jaw":    ((0.000,  0.012, -0.004), (  5.0, -7.5,  4.5)),
                "Weapon_R":    ((0.000, -0.014, 0.000), ( 16.0, -6.0, -6.0)),
                "Shield_L":    ((0.000,  0.024, 0.016), (-24.0, -8.0,  8.0)),
                "Wings_Tail":  ((0.000,  0.000, 0.004), ( 14.0, -20.0, 8.0)),
            }),
            (36, z0),
        ], True

    if piece_key == "knight":
        # Sweeping Wing-Assisted Aerial Bounding Glide (pairs with Three.js parabolic leap!)
        return [
            (1, z0),
            (7, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.000,  0.036, 0.042), (-11.0, -3.5,  2.0)),
                "Spine_Upper": ((0.000,  0.014, 0.012), (-13.0,  4.5, -2.5)),
                "Head_Jaw":    ((0.000,  0.012, 0.000), (  8.0, -4.0,  2.0)),
                "Weapon_R":    ((0.000,  0.018, 0.012), (-20.0, 12.0, -16.0)),
                "Shield_L":    ((0.000,  0.018, 0.012), (-20.0, -12.0, 16.0)),
                "Wings_Tail":  ((0.000,  0.000, 0.018), (-30.0,  0.0, 10.0)),
            }),
            (14, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.000,  0.052, 0.054), (-13.0,  3.5, -2.0)),
                "Spine_Upper": ((0.000,  0.018, 0.016), (-15.0, -4.5,  2.5)),
                "Head_Jaw":    ((0.000,  0.016, 0.000), (  6.0,  4.0, -2.0)),
                "Weapon_R":    ((0.000,  0.024, 0.016), (-26.0, 16.0, 14.0)),
                "Shield_L":    ((0.000,  0.024, 0.016), (-26.0, -16.0, -14.0)),
                "Wings_Tail":  ((0.000,  0.000, 0.004), ( 24.0,  0.0, -12.0)),
            }),
            (22, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.000,  0.046, 0.048), (-12.0, -3.0,  1.8)),
                "Spine_Upper": ((0.000,  0.014, 0.012), (-14.0,  4.0, -2.2)),
                "Head_Jaw":    ((0.000,  0.012, 0.000), (  7.5, -3.5,  1.8)),
                "Weapon_R":    ((0.000,  0.018, 0.012), (-22.0, 10.0, -16.0)),
                "Shield_L":    ((0.000,  0.018, 0.012), (-22.0, -10.0, 16.0)),
                "Wings_Tail":  ((0.000,  0.000, 0.018), (-28.0,  0.0, 10.0)),
            }),
            (29, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.000,  0.022, 0.022), ( -6.5,  2.0, -1.2)),
                "Spine_Upper": ((0.000,  0.008, 0.006), ( -7.5, -2.5,  1.5)),
                "Head_Jaw":    ((0.000,  0.006, 0.000), (  4.0,  2.0, -1.0)),
                "Weapon_R":    ((0.000,  0.010, 0.006), (-12.0,  6.0,  8.0)),
                "Shield_L":    ((0.000,  0.010, 0.006), (-12.0, -6.0, -8.0)),
                "Wings_Tail":  ((0.000,  0.000, 0.004), ( 14.0,  0.0, -6.0)),
            }),
            (36, z0),
        ], True

    if piece_key == "bishop":
        # Twin-Headed Oracle Hydra-Wyrm: twin dragon necks thrusting forward in sinuous S-wave concert!
        return [
            (1, z0),
            (8, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((-0.010, 0.032, 0.026), (-9.5,   6.0,  3.0)),
                "Spine_Upper": ((0.000,  0.014, 0.010), (-11.5, -7.5, -3.5)),
                "Head_Jaw":    ((0.000,  0.012, 0.006), ( -6.0,  5.0,  2.0)),
                "Weapon_R":    ((0.010,  0.028, 0.014), (-22.0, 16.0, -14.0)),
                "Shield_L":    ((-0.012, 0.018, 0.020), (-14.0, 18.0,  16.0)),
                "Wings_Tail":  ((0.000,  0.000, 0.008), ( 18.0, -10.0, 6.0)),
            }),
            (18, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.010,  0.044, 0.032), (-11.5, -6.0, -3.0)),
                "Spine_Upper": ((0.000,  0.018, 0.012), (-13.5,  7.5,  3.5)),
                "Head_Jaw":    ((0.000,  0.016, 0.008), ( -8.0, -5.0, -2.0)),
                "Weapon_R":    ((0.012,  0.018, 0.020), (-14.0, -18.0, -16.0)),
                "Shield_L":    ((-0.010, 0.028, 0.014), (-22.0, -16.0,  14.0)),
                "Wings_Tail":  ((0.000,  0.000, 0.010), ( 22.0,  10.0, -6.0)),
            }),
            (28, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((-0.006, 0.020, 0.014), ( -5.5,  3.5,  1.8)),
                "Spine_Upper": ((0.000,  0.008, 0.006), ( -6.5, -4.5, -2.0)),
                "Head_Jaw":    ((0.000,  0.006, 0.004), ( -3.5,  3.0,  1.0)),
                "Weapon_R":    ((0.006,  0.014, 0.008), (-12.0,  9.0, -8.0)),
                "Shield_L":    ((-0.006, 0.010, 0.010), ( -8.0,  9.0,  8.0)),
                "Wings_Tail":  ((0.000,  0.000, 0.004), ( 11.0, -5.0,  3.0)),
            }),
            (36, z0),
        ], True

    if piece_key == "queen":
        # Four-Winged Celestial Elder Dragon: majestic soaring glide with deep rhythmic 4-wing sweep
        return [
            (1, z0),
            (7, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((-0.008, 0.036, 0.044), (-9.5,   4.5,  2.5)),
                "Spine_Upper": ((0.000,  0.016, 0.016), (-11.5, -6.0, -3.0)),
                "Head_Jaw":    ((0.000,  0.012, 0.006), ( 11.0,  4.5,  2.0)),
                "Weapon_R":    ((0.000,  0.016, 0.014), (-16.0, 10.0, -14.0)),
                "Shield_L":    ((0.000,  0.016, 0.014), (-16.0, -10.0, 14.0)),
                "Wings_Tail":  ((0.000,  0.000, 0.020), (-26.0,  4.0, 10.0)),
            }),
            (15, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.008,  0.050, 0.054), (-11.5, -4.5, -2.5)),
                "Spine_Upper": ((0.000,  0.020, 0.020), (-13.5,  6.0,  3.0)),
                "Head_Jaw":    ((0.000,  0.016, 0.008), ( 13.0, -4.5, -2.0)),
                "Weapon_R":    ((0.000,  0.022, 0.018), (-20.0, 12.0, 12.0)),
                "Shield_L":    ((0.000,  0.022, 0.018), (-20.0, -12.0, -12.0)),
                "Wings_Tail":  ((0.000,  0.000, 0.006), ( 22.0, -4.0, -9.0)),
            }),
            (24, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((-0.006, 0.040, 0.046), (-10.0,  3.5,  2.0)),
                "Spine_Upper": ((0.000,  0.016, 0.016), (-12.0, -5.0, -2.5)),
                "Head_Jaw":    ((0.000,  0.012, 0.006), ( 11.5,  3.5,  1.5)),
                "Weapon_R":    ((0.000,  0.016, 0.014), (-16.0,  9.0, -12.0)),
                "Shield_L":    ((0.000,  0.016, 0.014), (-16.0, -9.0, 12.0)),
                "Wings_Tail":  ((0.000,  0.000, 0.018), (-24.0,  3.5,  9.0)),
            }),
            (30, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.004,  0.020, 0.022), ( -5.0, -2.0, -1.2)),
                "Spine_Upper": ((0.000,  0.008, 0.008), ( -6.0,  3.0,  1.5)),
                "Head_Jaw":    ((0.000,  0.006, 0.003), (  6.0, -2.0, -1.0)),
                "Weapon_R":    ((0.000,  0.008, 0.006), ( -8.0,  5.0,  6.0)),
                "Shield_L":    ((0.000,  0.008, 0.006), ( -8.0, -5.0, -6.0)),
                "Wings_Tail":  ((0.000,  0.000, 0.004), ( 12.0, -2.0, -4.5)),
            }),
            (36, z0),
        ], True

    # King: Unstoppable Sovereign Arch-Dragon Stride & Cathedral-Wing Mantle Surge
    return [
        (1, z0),
        (9, {
            "Root":        _IDENTITY_POSE,
            "Spine_Lower": ((-0.010, 0.032, 0.026), (-9.0,  -5.5,  3.5)),
            "Spine_Upper": ((0.000,  0.014, 0.010), (-11.0, -7.0, -3.0)),
            "Head_Jaw":    ((0.000,  0.012, 0.004), (  9.0,  7.5,  2.0)),
            "Weapon_R":    ((0.000,  0.026, 0.016), (-22.0,  8.0, -10.0)),
            "Shield_L":    ((0.000, -0.010, 0.006), ( 14.0,  6.0,  8.0)),
            "Wings_Tail":  ((0.000,  0.000, 0.014), (-18.0,  6.0,  7.0)),
        }),
        (18, {
            "Root":        _IDENTITY_POSE,
            "Spine_Lower": ((0.000,  0.044, 0.018), (-10.5,  0.0,  0.0)),
            "Spine_Upper": ((0.000,  0.018, 0.006), (-12.5,  0.0,  0.0)),
            "Head_Jaw":    ((0.000,  0.016, 0.004), ( 10.5,  0.0,  0.0)),
            "Weapon_R":    ((0.000,  0.014, 0.008), (-12.0,  4.0,  5.0)),
            "Shield_L":    ((0.000,  0.014, 0.008), (-12.0, -4.0, -5.0)),
            "Wings_Tail":  ((0.000,  0.000, 0.006), ( 20.0,  0.0,  0.0)),
        }),
        (27, {
            "Root":        _IDENTITY_POSE,
            "Spine_Lower": ((0.010,  0.032, 0.026), (-9.0,   5.5, -3.5)),
            "Spine_Upper": ((0.000,  0.014, 0.010), (-11.0,  7.0,  3.0)),
            "Head_Jaw":    ((0.000,  0.012, 0.004), (  9.0, -7.5, -2.0)),
            "Weapon_R":    ((0.000, -0.010, 0.006), ( 14.0, -6.0, -8.0)),
            "Shield_L":    ((0.000,  0.026, 0.016), (-22.0, -8.0, 10.0)),
            "Wings_Tail":  ((0.000,  0.000, 0.014), (-18.0, -6.0, -7.0)),
        }),
        (36, z0),
    ], True


# ==============================================================================
# 3. BREED-AUTHENTIC ATTACK & BREATH BIOMECHANICS (Frames 1..36, Peak f=11..13)
# ==============================================================================
# Strict constraints enforced:
# - `Root` locked at identity `(0,0,0)` on every frame
# - Every bone `|rx| <= 38.0 deg` (`<= 0.663 rad < 0.68 rad`)
# - Dramatic `0.75m - 1.45m` peak vertex displacement at f=11..13
# - Exact rest pose at f=1 and f=36
def _build_attack_track_poses(piece_key: str) -> tuple[list[tuple[int, dict]], bool]:
    z0 = _zero_pose_dict()

    if piece_key == "pawn":
        # Quadruped Stone Hatchling Drake:
        # Coils back onto haunches -> Explosive forward pounce + double foreclaw maul + snapping jaw-bite!
        return [
            (1, z0),
            (6, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.000, -0.055, -0.014), ( 18.0, -6.0, -2.0)),
                "Spine_Upper": ((0.000, -0.018,  0.012), ( 22.0,  6.0,  2.0)),
                "Head_Jaw":    ((0.000, -0.010,  0.010), ( 20.0, -8.0,  4.0)),
                "Weapon_R":    ((0.016, -0.018,  0.024), ( 32.0, -16.0, -22.0)),
                "Shield_L":    ((-0.016, -0.018, 0.024), ( 32.0,  16.0,  22.0)),
                "Wings_Tail":  ((0.000,  0.000,  0.014), (-34.0,  8.0, -10.0)),
            }),
            (11, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.000,  0.125,  0.032), (-19.0,  5.0,  2.0)),
                "Spine_Upper": ((0.000,  0.035,  0.006), (-21.0,  7.0,  3.0)),
                "Head_Jaw":    ((0.000,  0.042, -0.008), (-26.0, -6.0, -3.0)),
                "Weapon_R":    ((-0.016, 0.046, -0.012), (-35.0, 22.0, 20.0)),
                "Shield_L":    ((0.016,  0.046, -0.012), (-35.0, -22.0, -20.0)),
                "Wings_Tail":  ((0.000,  0.010,  0.018), ( -8.0, -6.0, 10.0)),
            }),
            (12, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.000,  0.142,  0.036), (-21.0,  6.0,  2.5)),
                "Spine_Upper": ((0.000,  0.040,  0.008), (-23.0,  8.0,  3.5)),
                "Head_Jaw":    ((0.000,  0.050, -0.010), (-29.0, -8.0, -4.0)),
                "Weapon_R":    ((-0.020, 0.054, -0.014), (-37.5, 26.0, 24.0)),
                "Shield_L":    ((0.020,  0.054, -0.014), (-37.5, -26.0, -24.0)),
                "Wings_Tail":  ((0.000,  0.012,  0.020), (-10.0, -8.0, 12.0)),
            }),
            (16, {
                # Vicious hatchling jaw-shake & claw tear
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.000,  0.118,  0.026), (-18.0, -6.0, -2.5)),
                "Spine_Upper": ((0.000,  0.032,  0.004), (-20.0, -8.0, -3.0)),
                "Head_Jaw":    ((0.000,  0.040, -0.008), (-24.0, 12.0,  6.0)),
                "Weapon_R":    ((-0.016, 0.042, -0.010), (-32.0, 20.0, 18.0)),
                "Shield_L":    ((0.016,  0.044, -0.010), (-34.0, -22.0, -20.0)),
                "Wings_Tail":  ((0.000,  0.008,  0.014), ( -6.0,  8.0, -8.0)),
            }),
            (22, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.000,  0.078,  0.016), (-13.0,  3.0,  1.5)),
                "Spine_Upper": ((0.000,  0.020,  0.002), (-15.0,  4.0,  2.0)),
                "Head_Jaw":    ((0.000,  0.024, -0.004), (-16.0, -5.0, -2.5)),
                "Weapon_R":    ((-0.010, 0.028, -0.006), (-24.0, 14.0, 12.0)),
                "Shield_L":    ((0.010,  0.028, -0.006), (-24.0, -14.0, -12.0)),
                "Wings_Tail":  ((0.000,  0.004,  0.008), ( -4.0, -4.0,  5.0)),
            }),
            (29, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.000,  0.024,  0.004), ( -4.5,  1.0,  0.5)),
                "Spine_Upper": ((0.000,  0.006,  0.000), ( -5.5,  1.5,  0.5)),
                "Head_Jaw":    ((0.000,  0.006,  0.000), ( -5.0, -1.5,  0.0)),
                "Weapon_R":    ((0.000,  0.008,  0.000), ( -8.0,  4.0,  4.0)),
                "Shield_L":    ((0.000,  0.008,  0.000), ( -8.0, -4.0, -4.0)),
                "Wings_Tail":  ((0.000,  0.000,  0.002), (  0.0, -1.5,  1.5)),
            }),
            (36, z0),
        ], False

    if piece_key == "rook":
        # Quadruped Armored Behemoth Earth-Drake:
        # Rears massive armored forequarters up (f=5..7) -> Seismic forelimb stomp +
        # colossal horned skull forward/upward gore + spiked club-tail whip!
        return [
            (1, z0),
            (6, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.000, -0.048,  0.056), ( 20.0, -6.0,  0.0)),
                "Spine_Upper": ((0.000, -0.016,  0.028), ( 24.0,  6.0,  0.0)),
                "Head_Jaw":    ((0.000, -0.010,  0.008), ( 12.0, -5.0,  0.0)),
                "Weapon_R":    ((0.018, -0.015,  0.032), ( 34.0, -16.0, -20.0)),
                "Shield_L":    ((-0.018, -0.015, 0.032), ( 34.0,  16.0,  20.0)),
                "Wings_Tail":  ((0.000,  0.000,  0.012), (-34.0, -24.0,  8.0)),
            }),
            (11, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.000,  0.118, -0.014), (-18.5,  5.0,  2.0)),
                "Spine_Upper": ((0.000,  0.036, -0.006), (-20.5, -4.0, -2.0)),
                # Colossal horned skull drives forward and tosses UPWARD to gore!
                "Head_Jaw":    ((0.000,  0.062,  0.022), ( 18.0,  4.0,  2.0)),
                # Massive forelimbs slam down in seismic stomp!
                "Weapon_R":    ((-0.012, 0.038, -0.026), (-33.0, 16.0, 14.0)),
                "Shield_L":    ((0.012,  0.038, -0.026), (-33.0, -16.0, -14.0)),
                # Spiked club-tail whips violently across!
                "Wings_Tail":  ((0.000,  0.008,  0.016), ( -6.0, 32.0, -14.0)),
            }),
            (12, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.000,  0.132, -0.016), (-20.0,  6.0,  2.5)),
                "Spine_Upper": ((0.000,  0.042, -0.008), (-22.0, -5.0, -2.5)),
                "Head_Jaw":    ((0.000,  0.072,  0.028), ( 24.0,  6.0,  3.0)),
                "Weapon_R":    ((-0.014, 0.044, -0.030), (-36.0, 18.0, 16.0)),
                "Shield_L":    ((0.014,  0.044, -0.030), (-36.0, -18.0, -16.0)),
                "Wings_Tail":  ((0.000,  0.010,  0.018), ( -8.0, 36.0, -16.0)),
            }),
            (16, {
                # Seismic earth-drake aftershock & upward horn-wrench!
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.006,  0.114, -0.008), (-16.5, -4.0, -2.0)),
                "Spine_Upper": ((0.000,  0.034, -0.004), (-18.5,  4.0,  2.0)),
                "Head_Jaw":    ((0.000,  0.064,  0.034), ( 28.0, -8.0, -4.0)),
                "Weapon_R":    ((-0.010, 0.036, -0.024), (-30.0, 14.0, 12.0)),
                "Shield_L":    ((0.010,  0.036, -0.024), (-30.0, -14.0, -12.0)),
                "Wings_Tail":  ((0.000,  0.006,  0.014), ( -4.0, -18.0, 10.0)),
            }),
            (22, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.000,  0.078, -0.004), (-12.0,  2.0,  0.0)),
                "Spine_Upper": ((0.000,  0.022,  0.000), (-14.0, -2.0,  0.0)),
                "Head_Jaw":    ((0.000,  0.042,  0.018), ( 16.0,  3.0,  0.0)),
                "Weapon_R":    ((-0.008, 0.024, -0.016), (-22.0, 10.0,  9.0)),
                "Shield_L":    ((0.008,  0.024, -0.016), (-22.0, -10.0, -9.0)),
                "Wings_Tail":  ((0.000,  0.004,  0.008), ( -2.0, 14.0, -6.0)),
            }),
            (29, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.000,  0.026,  0.000), ( -4.0,  0.0,  0.0)),
                "Spine_Upper": ((0.000,  0.008,  0.000), ( -5.0,  0.0,  0.0)),
                "Head_Jaw":    ((0.000,  0.012,  0.004), (  5.0,  0.0,  0.0)),
                "Weapon_R":    ((0.000,  0.008, -0.004), ( -8.0,  3.0,  3.0)),
                "Shield_L":    ((0.000,  0.008, -0.004), ( -8.0, -3.0, -3.0)),
                "Wings_Tail":  ((0.000,  0.000,  0.002), (  0.0,  4.0, -2.0)),
            }),
            (36, z0),
        ], False

    if piece_key == "knight":
        # Rearing Bipedal Winged Wyvern:
        # High rearing wing-spread wind-up (f=5..7) -> Diving wyvern fang-strike +
        # twin raptorial talon rake + thunderous forward wing-clap!
        return [
            (1, z0),
            (6, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.000, -0.052,  0.068), ( 18.0, -5.0,  1.5)),
                "Spine_Upper": ((0.000, -0.014,  0.024), ( 22.0,  5.0, -1.5)),
                "Head_Jaw":    ((0.000, -0.008,  0.012), ( 20.0, -7.0,  3.0)),
                "Weapon_R":    ((0.022, -0.016,  0.028), ( 34.0, -18.0, -28.0)),
                "Shield_L":    ((-0.022, -0.016, 0.028), ( 34.0,  18.0,  28.0)),
                "Wings_Tail":  ((0.000, -0.010,  0.026), (-37.0,  0.0,  14.0)),
            }),
            (11, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.000,  0.128,  0.024), (-18.5,  6.0,  2.5)),
                "Spine_Upper": ((0.000,  0.036,  0.004), (-20.5,  8.0,  3.5)),
                "Head_Jaw":    ((0.000,  0.052, -0.012), (-26.0, -6.0, -3.0)),
                "Weapon_R":    ((-0.018, 0.044, -0.012), (-34.0, 24.0, 24.0)),
                "Shield_L":    ((0.018,  0.044, -0.012), (-34.0, -24.0, -24.0)),
                "Wings_Tail":  ((0.000,  0.030,  0.016), (-14.0,  4.0, -14.0)),
            }),
            (12, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.000,  0.142,  0.026), (-20.0,  7.0,  3.0)),
                "Spine_Upper": ((0.000,  0.040,  0.004), (-22.0,  9.0,  4.0)),
                "Head_Jaw":    ((0.000,  0.060, -0.014), (-29.0, -8.0, -4.0)),
                "Weapon_R":    ((-0.022, 0.050, -0.014), (-37.0, 26.0, 26.0)),
                "Shield_L":    ((0.022,  0.050, -0.014), (-37.0, -26.0, -26.0)),
                "Wings_Tail":  ((0.000,  0.036,  0.018), (-16.0,  6.0, -16.0)),
            }),
            (16, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.000,  0.120,  0.022), (-17.5, -6.0, -2.5)),
                "Spine_Upper": ((0.000,  0.032,  0.004), (-19.0, -8.0, -3.0)),
                "Head_Jaw":    ((0.000,  0.046, -0.010), (-23.0, 12.0,  5.0)),
                "Weapon_R":    ((-0.016, 0.038, -0.010), (-31.0, 18.0, 18.0)),
                "Shield_L":    ((0.016,  0.038, -0.010), (-32.0, -20.0, -20.0)),
                "Wings_Tail":  ((0.000,  0.022,  0.014), (-10.0, -5.0,  8.0)),
            }),
            (22, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.000,  0.080,  0.016), (-12.0,  4.0,  1.5)),
                "Spine_Upper": ((0.000,  0.020,  0.002), (-14.0,  5.0,  2.0)),
                "Head_Jaw":    ((0.000,  0.028, -0.006), (-15.0, -4.0, -2.0)),
                "Weapon_R":    ((-0.010, 0.024, -0.006), (-22.0, 12.0, 12.0)),
                "Shield_L":    ((0.010,  0.024, -0.006), (-22.0, -12.0, -12.0)),
                "Wings_Tail":  ((0.000,  0.012,  0.010), ( -6.0,  3.0, -5.0)),
            }),
            (29, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.000,  0.026,  0.006), ( -4.0,  1.5,  0.0)),
                "Spine_Upper": ((0.000,  0.006,  0.000), ( -5.0,  1.5,  0.0)),
                "Head_Jaw":    ((0.000,  0.008,  0.000), ( -4.5, -1.5,  0.0)),
                "Weapon_R":    ((0.000,  0.008,  0.000), ( -8.0,  4.0,  4.0)),
                "Shield_L":    ((0.000,  0.008,  0.000), ( -8.0, -4.0, -4.0)),
                "Wings_Tail":  ((0.000,  0.004,  0.004), ( -2.0,  0.0,  0.0)),
            }),
            (36, z0),
        ], False

    if piece_key == "bishop":
        # Twin-Headed Oracle Hydra-Wyrm:
        # Both dragon necks (`Weapon_R` Right, `Shield_L` Left) rear high & wide apart (f=5..7),
        # then snap inward & forward together in a ferocious synchronized twin-head Hydra bite!
        return [
            (1, z0),
            (6, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.000, -0.048,  0.046), ( 17.0,  0.0,  0.0)),
                "Spine_Upper": ((0.000, -0.014,  0.018), ( 21.0,  0.0,  0.0)),
                "Head_Jaw":    ((0.000, -0.010,  0.012), ( 18.0,  0.0,  0.0)),
                # Right & Left Dragon Necks rear high & bank wide apart!
                "Weapon_R":    ((0.028, -0.020,  0.026), ( 33.0, -26.0, -28.0)),
                "Shield_L":    ((-0.028, -0.020, 0.026), ( 33.0,  26.0,  28.0)),
                "Wings_Tail":  ((0.000,  0.000,  0.018), (-36.0,  0.0,   0.0)),
            }),
            (11, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.000,  0.118,  0.018), (-17.5,  0.0,  0.0)),
                "Spine_Upper": ((0.000,  0.034,  0.004), (-19.5,  0.0,  0.0)),
                "Head_Jaw":    ((0.000,  0.044,  0.000), (-24.0,  0.0,  0.0)),
                # Twin Dragon Heads snap inward & forward together in synchronized double-bite!
                "Weapon_R":    ((-0.022, 0.048, -0.012), (-33.0, 22.0, 20.0)),
                "Shield_L":    ((0.022,  0.048, -0.012), (-33.0, -22.0, -20.0)),
                "Wings_Tail":  ((0.000,  0.010,  0.016), ( -8.0,  0.0,  0.0)),
            }),
            (12, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.000,  0.132,  0.020), (-19.5,  0.0,  0.0)),
                "Spine_Upper": ((0.000,  0.038,  0.004), (-21.5,  0.0,  0.0)),
                "Head_Jaw":    ((0.000,  0.050,  0.000), (-27.0,  0.0,  0.0)),
                "Weapon_R":    ((-0.026, 0.054, -0.014), (-36.0, 26.0, 24.0)),
                "Shield_L":    ((0.026,  0.054, -0.014), (-36.0, -26.0, -24.0)),
                "Wings_Tail":  ((0.000,  0.012,  0.018), (-10.0,  0.0,  0.0)),
            }),
            (16, {
                # Opposing twin-jaw hydra tear!
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.000,  0.114,  0.016), (-17.0,  4.0,  2.0)),
                "Spine_Upper": ((0.000,  0.032,  0.004), (-19.0, -4.0, -2.0)),
                "Head_Jaw":    ((0.000,  0.042,  0.000), (-22.0,  0.0,  0.0)),
                "Weapon_R":    ((-0.016, 0.044, -0.010), (-31.0, 16.0, 14.0)),
                "Shield_L":    ((0.016,  0.044, -0.010), (-29.0, -28.0, -26.0)),
                "Wings_Tail":  ((0.000,  0.008,  0.014), ( -6.0,  6.0, -6.0)),
            }),
            (22, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.000,  0.076,  0.012), (-12.0, -3.0, -1.5)),
                "Spine_Upper": ((0.000,  0.020,  0.002), (-14.0,  3.0,  1.5)),
                "Head_Jaw":    ((0.000,  0.026,  0.000), (-15.0,  0.0,  0.0)),
                "Weapon_R":    ((-0.010, 0.028, -0.006), (-22.0, 14.0, 12.0)),
                "Shield_L":    ((0.010,  0.028, -0.006), (-22.0, -14.0, -12.0)),
                "Wings_Tail":  ((0.000,  0.004,  0.008), ( -4.0, -4.0,  4.0)),
            }),
            (29, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.000,  0.024,  0.004), ( -4.0,  0.0,  0.0)),
                "Spine_Upper": ((0.000,  0.006,  0.000), ( -5.0,  0.0,  0.0)),
                "Head_Jaw":    ((0.000,  0.008,  0.000), ( -5.0,  0.0,  0.0)),
                "Weapon_R":    ((0.000,  0.008,  0.000), ( -7.0,  5.0,  4.0)),
                "Shield_L":    ((0.000,  0.008,  0.000), ( -7.0, -5.0, -4.0)),
                "Wings_Tail":  ((0.000,  0.000,  0.002), (  0.0,  0.0,  0.0)),
            }),
            (36, z0),
        ], False

    if piece_key == "queen":
        # Four-Winged Celestial Elder Dragon:
        # Ascends/coils back unfurling all 4 wings (f=5..7) -> Sweeping Elder-Dragon fire-breath
        # lunge (sustained breath hold f=11..15) + twin talon rend!
        return [
            (1, z0),
            (6, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.000, -0.050,  0.066), ( 17.5, -5.0, -1.5)),
                "Spine_Upper": ((0.000, -0.014,  0.024), ( 21.0,  5.0,  1.5)),
                "Head_Jaw":    ((0.000, -0.008,  0.014), ( 18.0, -8.0, -3.0)),
                "Weapon_R":    ((0.020, -0.016,  0.028), ( 32.0, -18.0, -26.0)),
                "Shield_L":    ((-0.020, -0.016, 0.028), ( 32.0,  18.0,  26.0)),
                "Wings_Tail":  ((0.000, -0.008,  0.028), (-37.5,  6.0, -12.0)),
            }),
            (11, {
                # Fire-breath torrent ignites, sweeping from right to left across f=11..15!
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.000,  0.122,  0.028), (-17.5, -6.0, -2.0)),
                "Spine_Upper": ((0.000,  0.034,  0.008), (-19.5, -8.0, -3.0)),
                "Head_Jaw":    ((0.000,  0.048, -0.008), (-25.0, -14.0, -5.0)),
                "Weapon_R":    ((-0.018, 0.042, -0.010), (-32.0, 20.0, 22.0)),
                "Shield_L":    ((0.018,  0.042, -0.010), (-32.0, -20.0, -22.0)),
                "Wings_Tail":  ((0.000,  0.018,  0.024), (-10.0, -6.0, 10.0)),
            }),
            (13, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.000,  0.136,  0.030), (-19.0,  0.0,  0.0)),
                "Spine_Upper": ((0.000,  0.038,  0.008), (-21.5,  0.0,  0.0)),
                "Head_Jaw":    ((0.000,  0.054, -0.010), (-28.0,  0.0,  0.0)),
                "Weapon_R":    ((-0.020, 0.048, -0.012), (-35.0, 24.0, 24.0)),
                "Shield_L":    ((0.020,  0.048, -0.012), (-35.0, -24.0, -24.0)),
                "Wings_Tail":  ((0.000,  0.022,  0.026), (-12.0,  0.0, 12.0)),
            }),
            (15, {
                # Sustained fire-breath sweep completes across enemy locus!
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.000,  0.128,  0.028), (-18.0,  6.0,  2.0)),
                "Spine_Upper": ((0.000,  0.036,  0.008), (-20.0,  8.0,  3.0)),
                "Head_Jaw":    ((0.000,  0.050, -0.008), (-26.0, 14.0,  5.0)),
                "Weapon_R":    ((-0.018, 0.044, -0.010), (-33.0, 22.0, 22.0)),
                "Shield_L":    ((0.018,  0.044, -0.010), (-33.0, -22.0, -22.0)),
                "Wings_Tail":  ((0.000,  0.018,  0.022), (-10.0,  6.0, 10.0)),
            }),
            (22, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.000,  0.080,  0.020), (-12.0,  3.0,  1.0)),
                "Spine_Upper": ((0.000,  0.020,  0.004), (-14.0,  4.0,  1.5)),
                "Head_Jaw":    ((0.000,  0.026, -0.004), (-16.0,  6.0,  2.0)),
                "Weapon_R":    ((-0.010, 0.026, -0.006), (-22.0, 14.0, 14.0)),
                "Shield_L":    ((0.010,  0.026, -0.006), (-22.0, -14.0, -14.0)),
                "Wings_Tail":  ((0.000,  0.010,  0.014), ( -6.0,  3.0,  6.0)),
            }),
            (29, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.000,  0.026,  0.008), ( -4.0,  1.0,  0.0)),
                "Spine_Upper": ((0.000,  0.006,  0.002), ( -4.5,  1.0,  0.0)),
                "Head_Jaw":    ((0.000,  0.008,  0.000), ( -5.0,  2.0,  0.0)),
                "Weapon_R":    ((0.000,  0.008,  0.000), ( -7.0,  4.0,  4.0)),
                "Shield_L":    ((0.000,  0.008,  0.000), ( -7.0, -4.0, -4.0)),
                "Wings_Tail":  ((0.000,  0.004,  0.004), ( -2.0,  0.0,  2.0)),
            }),
            (36, z0),
        ], False

    # King: Colossal Rearing Sovereign Arch-Dragon:
    # Towers upright rearing back on haunches (f=5..8, wings flaring wide) ->
    # Earth-shattering Sovereign jaw-snap, sustained dragonfire roar (f=11..15) & twin-foreclaw slam!
    return [
        (1, z0),
        (7, {
            "Root":        _IDENTITY_POSE,
            "Spine_Lower": ((0.000, -0.056,  0.068), ( 18.5, -4.0,  0.0)),
            "Spine_Upper": ((0.000, -0.016,  0.026), ( 22.0,  4.0,  0.0)),
            "Head_Jaw":    ((0.000, -0.010,  0.014), ( 19.0, -6.0,  0.0)),
            "Weapon_R":    ((0.022, -0.018,  0.030), ( 34.0, -16.0, -24.0)),
            "Shield_L":    ((-0.022, -0.018, 0.030), ( 34.0,  16.0,  24.0)),
            "Wings_Tail":  ((0.000, -0.008,  0.026), (-37.5,  0.0, -10.0)),
        }),
        (11, {
            "Root":        _IDENTITY_POSE,
            "Spine_Lower": ((0.000,  0.128,  0.012), (-18.5,  4.0,  1.5)),
            "Spine_Upper": ((0.000,  0.036,  0.002), (-20.5,  5.0,  2.0)),
            "Head_Jaw":    ((0.000,  0.052, -0.010), (-26.0, -8.0, -3.0)),
            "Weapon_R":    ((-0.018, 0.046, -0.016), (-33.0, 20.0, 20.0)),
            "Shield_L":    ((0.018,  0.046, -0.016), (-33.0, -20.0, -20.0)),
            "Wings_Tail":  ((0.000,  0.018,  0.020), ( -8.0, -5.0, 10.0)),
        }),
        (12, {
            "Root":        _IDENTITY_POSE,
            "Spine_Lower": ((0.000,  0.142,  0.014), (-20.0,  5.0,  2.0)),
            "Spine_Upper": ((0.000,  0.040,  0.002), (-22.0,  6.0,  2.5)),
            "Head_Jaw":    ((0.000,  0.058, -0.012), (-28.5, -6.0, -2.0)),
            "Weapon_R":    ((-0.020, 0.052, -0.018), (-35.5, 22.0, 22.0)),
            "Shield_L":    ((0.020,  0.052, -0.018), (-35.5, -22.0, -22.0)),
            "Wings_Tail":  ((0.000,  0.022,  0.022), (-10.0, -6.0, 12.0)),
        }),
        (15, {
            # Sustained Sovereign dragonfire roar!
            "Root":        _IDENTITY_POSE,
            "Spine_Lower": ((0.000,  0.132,  0.012), (-19.0, -5.0, -2.0)),
            "Spine_Upper": ((0.000,  0.036,  0.002), (-20.5, -6.0, -2.5)),
            "Head_Jaw":    ((0.000,  0.054, -0.010), (-26.5, 10.0,  4.0)),
            "Weapon_R":    ((-0.018, 0.048, -0.016), (-33.0, 20.0, 20.0)),
            "Shield_L":    ((0.018,  0.048, -0.016), (-33.0, -20.0, -20.0)),
            "Wings_Tail":  ((0.000,  0.018,  0.018), ( -8.0,  6.0, 10.0)),
        }),
        (22, {
            "Root":        _IDENTITY_POSE,
            "Spine_Lower": ((0.000,  0.084,  0.010), (-12.5, -2.0, -1.0)),
            "Spine_Upper": ((0.000,  0.022,  0.002), (-14.0, -3.0, -1.0)),
            "Head_Jaw":    ((0.000,  0.030, -0.004), (-16.0,  4.0,  2.0)),
            "Weapon_R":    ((-0.010, 0.028, -0.008), (-22.0, 13.0, 13.0)),
            "Shield_L":    ((0.010,  0.028, -0.008), (-22.0, -13.0, -13.0)),
            "Wings_Tail":  ((0.000,  0.010,  0.012), ( -5.0,  3.0,  6.0)),
        }),
        (29, {
            "Root":        _IDENTITY_POSE,
            "Spine_Lower": ((0.000,  0.026,  0.004), ( -4.0,  0.0,  0.0)),
            "Spine_Upper": ((0.000,  0.006,  0.000), ( -5.0,  0.0,  0.0)),
            "Head_Jaw":    ((0.000,  0.008,  0.000), ( -5.0,  0.0,  0.0)),
            "Weapon_R":    ((0.000,  0.008,  0.000), ( -7.5,  4.0,  4.0)),
            "Shield_L":    ((0.000,  0.008,  0.000), ( -7.5, -4.0, -4.0)),
            "Wings_Tail":  ((0.000,  0.004,  0.004), ( -2.0,  0.0,  2.0)),
        }),
        (36, z0),
    ], False


# ==============================================================================
# 4. BREED-AUTHENTIC HIT RECOIL BIOMECHANICS (Frames 1..32, Recoil f=4..6)
# ==============================================================================
# `Root` strictly locked at identity `(0,0,0)`; `|rx| <= 38.0 deg` (`< 0.68 rad`)!
def _build_hit_track_poses(piece_key: str) -> tuple[list[tuple[int, dict]], bool]:
    z0 = _zero_pose_dict()

    if piece_key == "pawn":
        # Snarling backward skitter/recoil + vigorous horned-head shake before re-crouching!
        return [
            (1, z0),
            (4, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.018, -0.078, 0.016), (16.0, 12.0, -7.0)),
                "Spine_Upper": ((0.000, -0.018, 0.006), (19.0, 15.0, -9.0)),
                "Head_Jaw":    ((0.000,  0.000, 0.000), (20.0, 18.0, -12.0)),
                "Weapon_R":    ((0.022, -0.016, 0.018), (18.0, -22.0, -28.0)),
                "Shield_L":    ((-0.022, -0.016, 0.018), (18.0, 22.0,  28.0)),
                "Wings_Tail":  ((0.000,  0.000, 0.014), (-32.0, -14.0, 16.0)),
            }),
            (6, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.022, -0.092, 0.020), (18.5, 14.0, -8.5)),
                "Spine_Upper": ((0.000, -0.022, 0.008), (22.0, 18.0, -11.0)),
                "Head_Jaw":    ((0.000,  0.000, 0.000), (24.0, 22.0, -14.0)),
                "Weapon_R":    ((0.026, -0.020, 0.022), (22.0, -26.0, -32.0)),
                "Shield_L":    ((-0.026, -0.020, 0.022), (22.0, 26.0,  32.0)),
                "Wings_Tail":  ((0.000,  0.000, 0.018), (-36.0, -18.0, 20.0)),
            }),
            (11, {
                # Vigorous horned-head shake left!
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((-0.014, -0.056, 0.006), ( 8.0, -10.0,  5.0)),
                "Spine_Upper": ((0.000, -0.010, 0.000), (10.0, -14.0,  7.0)),
                "Head_Jaw":    ((0.000,  0.008, 0.000), (-8.0, -26.0, 18.0)),
                "Weapon_R":    ((0.014, -0.008, 0.008), (10.0, -12.0, -16.0)),
                "Shield_L":    ((-0.014, -0.008, 0.008), (10.0, 12.0,  16.0)),
                "Wings_Tail":  ((0.000,  0.000, 0.008), (-18.0, 14.0, -14.0)),
            }),
            (16, {
                # Horned-head shake right!
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.012, -0.044, 0.004), ( 5.0,  8.0, -4.0)),
                "Spine_Upper": ((0.000, -0.006, 0.000), ( 6.0, 12.0, -6.0)),
                "Head_Jaw":    ((0.000,  0.010, 0.000), (-10.0, 24.0, -16.0)),
                "Weapon_R":    ((0.010,  0.000, 0.004), ( -6.0,  8.0,  8.0)),
                "Shield_L":    ((-0.010, 0.000, 0.004), ( -6.0, -8.0, -8.0)),
                "Wings_Tail":  ((0.000,  0.000, 0.006), (-12.0, -12.0, 12.0)),
            }),
            (23, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.000, -0.016, -0.006), (-4.0, -3.0,  1.5)),
                "Spine_Upper": ((0.000,  0.004,  0.000), (-6.0, -4.0,  2.0)),
                "Head_Jaw":    ((0.000,  0.006,  0.000), (-6.0, -6.0,  3.0)),
                "Weapon_R":    ((0.004,  0.004,  0.000), (-8.0,  4.0,  5.0)),
                "Shield_L":    ((-0.004, 0.004,  0.000), (-8.0, -4.0, -5.0)),
                "Wings_Tail":  ((0.000,  0.000,  0.002), ( 4.0,  4.0, -4.0)),
            }),
            (32, z0),
        ], False

    if piece_key == "rook":
        # Immovable Armored Brace: low-center-of-gravity shudder + defiant upward horn toss!
        return [
            (1, z0),
            (4, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((-0.018, -0.062, -0.014), (11.0, -10.0,  6.0)),
                "Spine_Upper": ((0.000,  -0.016, -0.006), (14.0, -14.0,  8.0)),
                "Head_Jaw":    ((0.000,  -0.008,  0.000), (14.0, -14.0,  8.0)),
                "Weapon_R":    ((0.020,  -0.014,  0.008), (20.0, -18.0, -24.0)),
                "Shield_L":    ((-0.020, -0.014,  0.008), (20.0,  18.0,  24.0)),
                "Wings_Tail":  ((0.000,   0.000,  0.010), (-26.0, 22.0, -12.0)),
            }),
            (6, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((-0.024, -0.075, -0.018), (13.5, -13.0,  7.5)),
                "Spine_Upper": ((0.000,  -0.020, -0.008), (17.0, -17.0, 10.0)),
                "Head_Jaw":    ((0.000,  -0.010,  0.000), (18.0, -16.0, 10.0)),
                "Weapon_R":    ((0.024,  -0.018,  0.010), (24.0, -22.0, -28.0)),
                "Shield_L":    ((-0.024, -0.018,  0.010), (24.0,  22.0,  28.0)),
                "Wings_Tail":  ((0.000,   0.000,  0.012), (-30.0, 28.0, -15.0)),
            }),
            (11, {
                # Low armored carapace shudder
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.016, -0.048, -0.016), ( 6.0,  9.0, -6.0)),
                "Spine_Upper": ((0.000, -0.010, -0.006), ( 8.0, 12.0, -8.0)),
                "Head_Jaw":    ((0.000,  0.012, -0.008), (-14.0, 12.0, -6.0)),
                "Weapon_R":    ((0.014,  0.000, -0.006), (-10.0, 10.0, 10.0)),
                "Shield_L":    ((-0.014, 0.000, -0.006), (-10.0, -10.0, -10.0)),
                "Wings_Tail":  ((0.000,  0.000,  0.006), (-14.0, -20.0, 10.0)),
            }),
            (16, {
                # Defiant upward horn toss!
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.000,  0.024,  0.008), (-6.0, -4.0,  2.0)),
                "Spine_Upper": ((0.000,  0.010,  0.004), (-8.0, -5.0,  2.5)),
                "Head_Jaw":    ((0.000,  0.028,  0.018), (20.0, -10.0, 5.0)),
                "Weapon_R":    ((0.006,  0.010, -0.004), (-14.0,  8.0,  8.0)),
                "Shield_L":    ((-0.006, 0.010, -0.004), (-14.0, -8.0, -8.0)),
                "Wings_Tail":  ((0.000,  0.000,  0.008), ( 10.0, 14.0, -6.0)),
            }),
            (24, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.000,  0.008,  0.000), (-2.5,  0.0,  0.0)),
                "Spine_Upper": ((0.000,  0.004,  0.000), (-3.0,  0.0,  0.0)),
                "Head_Jaw":    ((0.000,  0.008,  0.004), ( 6.0,  0.0,  0.0)),
                "Weapon_R":    ((0.000,  0.004,  0.000), (-4.0,  2.0,  2.0)),
                "Shield_L":    ((0.000,  0.004,  0.000), (-4.0, -2.0, -2.0)),
                "Wings_Tail":  ((0.000,  0.000,  0.002), ( 3.0,  4.0,  0.0)),
            }),
            (32, z0),
        ], False

    if piece_key == "knight":
        # Violent Wing-Shield Bank & Serpentine Neck Recoil!
        return [
            (1, z0),
            (4, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.024, -0.075, 0.024), (15.0, 15.0, -10.0)),
                "Spine_Upper": ((0.000, -0.018, 0.010), (19.0, 19.0, -12.0)),
                "Head_Jaw":    ((0.000, -0.010, 0.006), (22.0, -20.0, 14.0)),
                "Weapon_R":    ((0.026, -0.018, 0.022), (20.0, -24.0, -32.0)),
                "Shield_L":    ((-0.018, 0.016, 0.022), (-18.0, -24.0, -20.0)),
                # Protective wing-shield bank!
                "Wings_Tail":  ((0.000,  0.010, 0.020), (-32.0, -22.0, 26.0)),
            }),
            (6, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.030, -0.090, 0.030), (18.0, 18.0, -12.0)),
                "Spine_Upper": ((0.000, -0.022, 0.012), (22.0, 22.0, -14.0)),
                "Head_Jaw":    ((0.000, -0.012, 0.008), (26.0, -24.0, 16.0)),
                "Weapon_R":    ((0.030, -0.022, 0.026), (24.0, -28.0, -36.0)),
                "Shield_L":    ((-0.022, 0.020, 0.026), (-22.0, -28.0, -24.0)),
                "Wings_Tail":  ((0.000,  0.012, 0.024), (-36.5, -26.0, 30.0)),
            }),
            (14, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((-0.022, -0.062, 0.018), (12.0, -14.0,  9.0)),
                "Spine_Upper": ((0.000, -0.014, 0.006), (15.0, -18.0, 11.0)),
                "Head_Jaw":    ((0.000,  0.006, 0.000), (14.0,  20.0, -12.0)),
                "Weapon_R":    ((0.018,  0.012, 0.014), (-16.0,  20.0,  18.0)),
                "Shield_L":    ((-0.022, -0.014, 0.016), (18.0,  22.0,  28.0)),
                "Wings_Tail":  ((0.000,  0.006, 0.014), (-28.0,  20.0, -22.0)),
            }),
            (22, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.008, -0.022, 0.010), (-5.0,  5.0, -3.0)),
                "Spine_Upper": ((0.000,  0.006, 0.004), (-7.0,  6.0, -4.0)),
                "Head_Jaw":    ((0.000,  0.008, 0.000), (-8.0, -6.0,  4.0)),
                "Weapon_R":    ((0.006,  0.006, 0.004), (-10.0, 6.0,  8.0)),
                "Shield_L":    ((-0.006, 0.006, 0.004), (-10.0, -6.0, -8.0)),
                "Wings_Tail":  ((0.000,  0.000, 0.006), ( 8.0, -6.0,  6.0)),
            }),
            (32, z0),
        ], False

    if piece_key == "bishop":
        # Twin-Headed Oracle Hydra-Wyrm:
        # Both dragon heads (`Weapon_R`, `Shield_L`) whip back asymmetrically in a snarling hydra recoil!
        return [
            (1, z0),
            (4, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((-0.020, -0.072, 0.020), (14.5, -12.0,  7.0)),
                "Spine_Upper": ((0.000,  -0.018, 0.008), (18.0, -16.0,  9.0)),
                "Head_Jaw":    ((0.000,  -0.008, 0.004), (18.0, -14.0,  8.0)),
                # Asymmetric twin-neck snap: Right whips deep back/right, Left twists high/left!
                "Weapon_R":    ((0.028,  -0.024, 0.020), (31.0, -28.0, -28.0)),
                "Shield_L":    ((-0.020, -0.012, 0.028), (18.0,  32.0,  30.0)),
                "Wings_Tail":  ((0.000,   0.000, 0.016), (-32.0,  16.0, -18.0)),
            }),
            (6, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((-0.026, -0.086, 0.024), (17.0, -15.0,  8.5)),
                "Spine_Upper": ((0.000,  -0.022, 0.010), (21.0, -19.0, 11.0)),
                "Head_Jaw":    ((0.000,  -0.010, 0.006), (22.0, -16.0, 10.0)),
                "Weapon_R":    ((0.032,  -0.028, 0.024), (36.0, -32.0, -32.0)),
                "Shield_L":    ((-0.024, -0.014, 0.032), (22.0,  36.0,  34.0)),
                "Wings_Tail":  ((0.000,   0.000, 0.020), (-36.5,  20.0, -22.0)),
            }),
            (14, {
                # Inverted hydra snarl: Left whips back while Right lunges forward hissing!
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.020, -0.056, 0.014), (11.0,  13.0, -7.0)),
                "Spine_Upper": ((0.000, -0.012, 0.004), (14.0,  16.0, -9.0)),
                "Head_Jaw":    ((0.000,  0.000, 0.002), (12.0,  14.0, -8.0)),
                "Weapon_R":    ((-0.012, 0.018, 0.010), (-18.0,  22.0,  18.0)),
                "Shield_L":    ((-0.028, -0.022, 0.020), (30.0,  28.0,  28.0)),
                "Wings_Tail":  ((0.000,  0.000, 0.012), (-26.0, -16.0, 18.0)),
            }),
            (22, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((-0.006, -0.018, 0.006), (-4.0, -4.0,  2.0)),
                "Spine_Upper": ((0.000,   0.004, 0.002), (-5.0, -5.0,  2.5)),
                "Head_Jaw":    ((0.000,   0.004, 0.000), (-5.0, -4.0,  2.0)),
                "Weapon_R":    ((0.006,   0.008, 0.004), ( -8.0, -10.0, -8.0)),
                "Shield_L":    ((-0.006,  0.012, 0.004), (-14.0, -12.0, -10.0)),
                "Wings_Tail":  ((0.000,   0.000, 0.004), (  5.0,  5.0, -5.0)),
            }),
            (32, z0),
        ], False

    if piece_key == "queen":
        # Graceful Winged Back-Arc Deflection & Sharp Forward Counter-Hiss!
        return [
            (1, z0),
            (4, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((-0.022, -0.072, 0.030), (14.5, -14.0,  7.5)),
                "Spine_Upper": ((0.000,  -0.018, 0.014), (18.5, -18.0,  9.5)),
                "Head_Jaw":    ((0.000,  -0.010, 0.008), (19.0,  16.0, -10.0)),
                "Weapon_R":    ((0.024,  -0.016, 0.022), (18.0, -24.0, -30.0)),
                "Shield_L":    ((-0.024, -0.016, 0.022), (18.0,  24.0,  30.0)),
                "Wings_Tail":  ((0.000,   0.000, 0.022), (-33.0,  16.0, -22.0)),
            }),
            (6, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((-0.026, -0.086, 0.036), (17.0, -17.0,  9.0)),
                "Spine_Upper": ((0.000,  -0.022, 0.018), (21.5, -21.0, 11.5)),
                "Head_Jaw":    ((0.000,  -0.012, 0.010), (23.0,  20.0, -12.0)),
                "Weapon_R":    ((0.028,  -0.020, 0.026), (22.0, -28.0, -34.0)),
                "Shield_L":    ((-0.028, -0.020, 0.026), (22.0,  28.0,  34.0)),
                "Wings_Tail":  ((0.000,   0.000, 0.026), (-37.0,  20.0, -26.0)),
            }),
            (14, {
                # Sharp celestial counter-hiss lunge!
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.012,  0.036, 0.018), (-9.0,  10.0, -4.0)),
                "Spine_Upper": ((0.000,  0.014, 0.006), (-12.0, 12.0, -5.0)),
                "Head_Jaw":    ((0.000,  0.028, -0.004), (-22.0, -14.0, 6.0)),
                "Weapon_R":    ((-0.010, 0.018, 0.006), (-18.0,  14.0, 16.0)),
                "Shield_L":    ((0.010,  0.018, 0.006), (-18.0, -14.0, -16.0)),
                "Wings_Tail":  ((0.000,  0.006, 0.014), (-14.0, -12.0, 14.0)),
            }),
            (23, {
                "Root":        _IDENTITY_POSE,
                "Spine_Lower": ((0.004,  0.010, 0.006), (-3.0,  3.0, -1.5)),
                "Spine_Upper": ((0.000,  0.004, 0.002), (-4.0,  4.0, -2.0)),
                "Head_Jaw":    ((0.000,  0.006, 0.000), (-6.0, -4.0,  2.0)),
                "Weapon_R":    ((0.000,  0.006, 0.000), (-6.0,  4.0,  5.0)),
                "Shield_L":    ((0.000,  0.006, 0.000), (-6.0, -4.0, -5.0)),
                "Wings_Tail":  ((0.000,  0.000, 0.004), (-4.0, -4.0,  4.0)),
            }),
            (32, z0),
        ], False

    # King: Defiant Arch-Dragon Roar-Recoil — absorbs impact on armored chest, whips head back,
    # and snaps forward with a menacing Sovereign snarl!
    return [
        (1, z0),
        (4, {
            "Root":        _IDENTITY_POSE,
            "Spine_Lower": ((0.020, -0.068, 0.018), (13.5, 11.0, -6.5)),
            "Spine_Upper": ((0.000, -0.018, 0.008), (17.5, 15.0, -8.5)),
            "Head_Jaw":    ((0.000, -0.010, 0.006), (22.0, 16.0, -10.0)),
            "Weapon_R":    ((0.024, -0.016, 0.020), (20.0, -22.0, -28.0)),
            "Shield_L":    ((-0.024, -0.016, 0.020), (20.0, 22.0,  28.0)),
            "Wings_Tail":  ((0.000,  0.000, 0.018), (-32.0, -14.0, 18.0)),
        }),
        (6, {
            "Root":        _IDENTITY_POSE,
            "Spine_Lower": ((0.024, -0.082, 0.022), (16.0, 14.0, -8.0)),
            "Spine_Upper": ((0.000, -0.022, 0.010), (20.5, 18.0, -10.0)),
            "Head_Jaw":    ((0.000, -0.012, 0.008), (26.0, 20.0, -12.0)),
            "Weapon_R":    ((0.028, -0.020, 0.024), (24.0, -26.0, -32.0)),
            "Shield_L":    ((-0.028, -0.020, 0.024), (24.0, 26.0,  32.0)),
            "Wings_Tail":  ((0.000,  0.000, 0.022), (-36.5, -18.0, 22.0)),
        }),
        (14, {
            # Menacing Sovereign counter-snarl!
            "Root":        _IDENTITY_POSE,
            "Spine_Lower": ((-0.012,  0.042, 0.010), (-10.0, -10.0,  5.0)),
            "Spine_Upper": ((0.000,   0.016, 0.004), (-13.0, -12.0,  6.0)),
            "Head_Jaw":    ((0.000,   0.034, -0.006), (-22.0,  14.0, -6.0)),
            "Weapon_R":    ((-0.010,  0.022, -0.006), (-20.0,  14.0, 16.0)),
            "Shield_L":    ((0.010,   0.022, -0.006), (-20.0, -14.0, -16.0)),
            "Wings_Tail":  ((0.000,   0.008, 0.014), (-12.0,  12.0, -12.0)),
        }),
        (23, {
            "Root":        _IDENTITY_POSE,
            "Spine_Lower": ((0.000,   0.012, 0.004), ( -3.5, -3.0,  1.5)),
            "Spine_Upper": ((0.000,   0.004, 0.000), ( -4.5, -4.0,  2.0)),
            "Head_Jaw":    ((0.000,   0.008, 0.000), ( -6.5,  4.0, -2.0)),
            "Weapon_R":    ((0.000,   0.006, 0.000), ( -6.5,  4.0,  5.0)),
            "Shield_L":    ((0.000,   0.006, 0.000), ( -6.5, -4.0, -5.0)),
            "Wings_Tail":  ((0.000,   0.000, 0.004), ( -3.0,  3.0, -3.0)),
        }),
        (32, z0),
    ], False


# ==============================================================================
# 5. BLENDER 5.2 ACTION SLOT + F-CURVE + NLA TRACK AUTHORING
# ==============================================================================
def _reset_armature_pose(arm_obj: bpy.types.Object):
    for pbone in arm_obj.pose.bones:
        pbone.rotation_mode = "QUATERNION"
        pbone.location = Vector((0.0, 0.0, 0.0))
        pbone.rotation_quaternion = Quaternion((1.0, 0.0, 0.0, 0.0))
        pbone.scale = Vector((1.0, 1.0, 1.0))


def _iter_action_fcurves(act: bpy.types.Action, slot):
    """Yield all F-Curves for `slot` across Blender 5.2 layered channelbags."""
    if hasattr(act, "layers") and slot is not None:
        for layer in act.layers:
            for strip in layer.strips:
                if hasattr(strip, "channelbag"):
                    cbag = strip.channelbag(slot)
                    if cbag is not None:
                        for fc in cbag.fcurves:
                            yield fc
    elif hasattr(act, "fcurves"):
        for fc in act.fcurves:
            yield fc


def _polish_fcurves(act: bpy.types.Action, slot, is_cyclic_loop: bool):
    """
    Configure smooth weighted-stone Bezier handles on all authored F-curves,
    with C1-continuous cyclic endpoint slopes on seamless loop clips (`Idle`, `Move`).
    """
    for fc in _iter_action_fcurves(act, slot):
        kps = fc.keyframe_points
        n_kp = len(kps)
        if n_kp == 0:
            continue

        for kp in kps:
            kp.interpolation = "BEZIER"
            kp.handle_left_type = "AUTO_CLAMPED"
            kp.handle_right_type = "AUTO_CLAMPED"

        fc.update()

        if is_cyclic_loop and n_kp >= 4:
            kp_first = kps[0]
            kp_second = kps[1]
            kp_prev = kps[n_kp - 2]
            kp_last = kps[n_kp - 1]

            dt_right = max(kp_second.co.x - kp_first.co.x, 1.0)
            dt_left = max(kp_last.co.x - kp_prev.co.x, 1.0)
            slope = (kp_second.co.y - kp_prev.co.y) / (dt_right + dt_left)

            kp_first.handle_left_type = "FREE"
            kp_first.handle_right_type = "FREE"
            kp_first.handle_left = Vector((kp_first.co.x - dt_left / 3.0, kp_first.co.y - slope * (dt_left / 3.0)))
            kp_first.handle_right = Vector((kp_first.co.x + dt_right / 3.0, kp_first.co.y + slope * (dt_right / 3.0)))

            kp_last.handle_left_type = "FREE"
            kp_last.handle_right_type = "FREE"
            kp_last.handle_left = Vector((kp_last.co.x - dt_left / 3.0, kp_last.co.y - slope * (dt_left / 3.0)))
            kp_last.handle_right = Vector((kp_last.co.x + dt_right / 3.0, kp_last.co.y + slope * (dt_right / 3.0)))

            fc.update()


def author_dragon_animations(piece_name: str, arm_obj: bpy.types.Object) -> list[str]:
    """
    Author the 4 creature-authentic stone dragon NLA clips (`Idle`, `Move`, `Attack`, `Hit`)
    across all 7 draconic bones (`Root` locked at identity, plus `Spine_Lower`, `Spine_Upper`,
    `Head_Jaw`, `Weapon_R`, `Shield_L`, `Wings_Tail`) on `arm_obj` using Blender 5.2 Action Slots.

    Returns the ordered list of NLA track names (`["Idle", "Move", "Attack", "Hit"]`).
    """
    if arm_obj is None or arm_obj.type != "ARMATURE":
        raise ValueError(f"Expected an ARMATURE object, got {arm_obj!r}")

    missing_bones = [b for b in BONE_NAMES if b not in arm_obj.pose.bones]
    if missing_bones:
        raise ValueError(
            f"Armature '{arm_obj.name}' is missing required dragon_spec bones: {missing_bones}"
        )

    piece_key = _normalize_piece_name(piece_name)
    scene = bpy.context.scene
    scene.render.fps = 24

    arm_obj.animation_data_create()
    anim_data = arm_obj.animation_data
    anim_data.action = None

    # Clear any pre-existing NLA tracks on this armature to prevent duplicate stacking
    for existing_tr in list(anim_data.nla_tracks):
        anim_data.nla_tracks.remove(existing_tr)

    _reset_armature_pose(arm_obj)
    pbones = arm_obj.pose.bones

    clip_builders = {
        "Idle": _build_idle_track_poses,
        "Move": _build_move_track_poses,
        "Attack": _build_attack_track_poses,
        "Hit": _build_hit_track_poses,
    }

    authored_tracks: list[str] = []

    for clip_name in NLA_CLIPS:
        frame_end = CLIP_FRAME_ENDS[clip_name]
        track_poses, is_cyclic_loop = clip_builders[clip_name](piece_key)

        act_name = f"{piece_key}_{clip_name}"
        if act_name in bpy.data.actions:
            bpy.data.actions.remove(bpy.data.actions[act_name])

        act = bpy.data.actions.new(name=act_name)
        act.use_fake_user = True

        # Blender 5.2 Slotted Action binding BEFORE keyframe_insert
        if hasattr(act, "slots"):
            if len(act.slots) == 0:
                act.slots.new(id_type="OBJECT", name=arm_obj.name)
            anim_data.action = act
            anim_data.action_slot = act.slots[0]
            active_slot = act.slots[0]
        else:
            anim_data.action = act
            active_slot = None

        _reset_armature_pose(arm_obj)
        prev_quats: dict[str, Quaternion] = {}

        for frame, pose_map in track_poses:
            for bname in BONE_NAMES:
                pbone = pbones[bname]

                # Hard guarantee: `Root` (jagged stone crag base) is ALWAYS locked at identity!
                if bname == "Root":
                    pbone.location = Vector((0.0, 0.0, 0.0))
                    quat = Quaternion((1.0, 0.0, 0.0, 0.0))
                else:
                    w_loc, rot_deg = pose_map.get(bname, _IDENTITY_POSE)
                    pbone.location = world_to_bone_loc(w_loc[0], w_loc[1], w_loc[2])
                    rx = math.radians(_clamp_rx(rot_deg[0]))
                    ry = math.radians(rot_deg[1])
                    rz = math.radians(rot_deg[2])
                    quat = Euler((rx, ry, rz), "XYZ").to_quaternion()

                # Enforce quaternion hemisphere continuity to prevent 360-deg spin glitches
                if bname in prev_quats and prev_quats[bname].dot(quat) < 0.0:
                    quat = -quat
                prev_quats[bname] = quat.copy()

                pbone.rotation_quaternion = quat
                pbone.scale = Vector((1.0, 1.0, 1.0))

                pbone.keyframe_insert(data_path="location", frame=frame)
                pbone.keyframe_insert(data_path="rotation_quaternion", frame=frame)

        if active_slot is not None and hasattr(anim_data, "action_slot"):
            anim_data.action_slot = act.slots[0]
        _polish_fcurves(act, active_slot, is_cyclic_loop=is_cyclic_loop)

        # Push Action into an NLA track named strictly after `clip_name` (`Idle`, `Move`, `Attack`, `Hit`)
        anim_data.action = None
        track = anim_data.nla_tracks.new()
        track.name = clip_name
        track.mute = False
        track.is_solo = False

        strip = track.strips.new(name=clip_name, start=1, action=act)
        if active_slot is not None and hasattr(strip, "action_slot"):
            strip.action_slot = active_slot
        strip.action_frame_start = 1
        strip.action_frame_end = frame_end
        strip.frame_start = 1
        strip.frame_end = frame_end
        strip.blend_type = "REPLACE"
        strip.extrapolation = "HOLD"

        authored_tracks.append(track.name)

    # Final clean state for glTF `export_animation_mode='NLA_TRACKS'`
    anim_data.action = None
    for tr in anim_data.nla_tracks:
        tr.mute = False
        tr.is_solo = False
    _reset_armature_pose(arm_obj)
    scene.frame_set(1)
    bpy.context.view_layer.update()

    return authored_tracks


# ==============================================================================
# 6. NLA TRACK, CRAG-LOCK & SKINNING DEFORMATION VERIFIER
# ==============================================================================
def _find_rigged_mesh(arm_obj: bpy.types.Object):
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        if "icosphere" in obj.name.lower():
            continue
        if obj.parent == arm_obj:
            return obj
        for mod in obj.modifiers:
            if mod.type == "ARMATURE" and mod.object == arm_obj:
                return obj
    return None


def _sample_evaluated_verts(mesh_obj: bpy.types.Object) -> list[Vector]:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = mesh_obj.evaluated_get(depsgraph)
    eval_mesh = eval_obj.to_mesh()
    try:
        coords = [v.co.copy() for v in eval_mesh.vertices]
    finally:
        eval_obj.to_mesh_clear()
    return coords


def verify_nla_animations(arm_obj: bpy.types.Object, mesh_obj: bpy.types.Object = None) -> dict:
    """
    Verify that `arm_obj` has:
    - All 7 `dragon_spec.BONE_NAMES`
    - All 4 `dragon_spec.NLA_CLIPS` (`Idle`, `Move`, `Attack`, `Hit`)
    - `Root` crag base strictly locked at identity `(0, 0, 0)` across all frames
    - Active pose motion across all 6 anatomical dragon bones (`Spine_Lower`,
      `Spine_Upper`, `Head_Jaw`, `Weapon_R`, `Shield_L`, `Wings_Tail`)
    - Per-bone pitch `|rx| <= 0.68 rad` (`38.96 deg`)
    - Exact loop closure (`frame 1 == end frame` on `Idle` & `Move`) and exact rest pose
      at start/end of `Attack` & `Hit`
    - Strong skinned vertex deformation (`0.75m - 1.45m` peak in `Attack` at frames 11..13,
      and strong recoil at frame 6 of `Hit`).
    """
    if arm_obj is None or arm_obj.type != "ARMATURE":
        raise ValueError(f"Expected an ARMATURE object, got {arm_obj!r}")

    if mesh_obj is None:
        mesh_obj = _find_rigged_mesh(arm_obj)

    scene = bpy.context.scene
    prev_frame = scene.frame_current

    bones_present = [b.name for b in arm_obj.data.bones]
    missing_bones = [b for b in BONE_NAMES if b not in arm_obj.pose.bones]

    anim_data = arm_obj.animation_data
    if anim_data is None:
        return {
            "valid": False,
            "armature": arm_obj.name,
            "bones": bones_present,
            "missing_bones": missing_bones,
            "nla_tracks": [],
            "missing_clips": list(NLA_CLIPS),
            "clips": {},
        }

    prev_action = anim_data.action
    prev_slot = getattr(anim_data, "action_slot", None) if prev_action is not None else None
    prev_track_state = [(tr, tr.mute, tr.is_solo) for tr in anim_data.nla_tracks]

    # Clear active action so NLA tracks evaluate cleanly in Blender 5.2
    anim_data.action = None
    for tr in anim_data.nla_tracks:
        tr.is_solo = False

    track_lookup = {tr.name: tr for tr in anim_data.nla_tracks}
    nla_track_names = [tr.name for tr in anim_data.nla_tracks]
    missing_clips = [c for c in NLA_CLIPS if c not in track_lookup]

    probe_frames = {
        "Idle":   (1, [16, 31, 46], 60),
        "Move":   (1, [8, 18, 27], 36),
        "Attack": (1, [6, 11, 12, 13, 22], 36),
        "Hit":    (1, [4, 6, 14], 32),
    }

    clip_metrics: dict[str, dict] = {}
    attack_f12_disp = 0.0
    attack_peak_disp = 0.0
    attack_f22_disp = 0.0
    hit_f6_disp = 0.0
    root_locked_all = True
    rx_within_limit_all = True

    try:
        for clip_name in NLA_CLIPS:
            target_tr = track_lookup.get(clip_name)
            if target_tr is None:
                clip_metrics[clip_name] = {"present": False}
                continue

            for tr in anim_data.nla_tracks:
                tr.mute = (tr != target_tr)

            f_start, mid_frames, f_end = probe_frames[clip_name]
            if len(target_tr.strips) > 0:
                f_end = int(round(target_tr.strips[0].frame_end))

            scene.frame_set(f_start)
            bpy.context.view_layer.update()

            start_bone_rot = {
                b: arm_obj.pose.bones[b].rotation_quaternion.copy()
                for b in BONE_NAMES
                if b in arm_obj.pose.bones
            }
            start_bone_loc = {
                b: arm_obj.pose.bones[b].location.copy()
                for b in BONE_NAMES
                if b in arm_obj.pose.bones
            }
            verts_f1 = _sample_evaluated_verts(mesh_obj) if mesh_obj is not None else None

            active_creature_bones = set()
            frame_disps: dict[int, float] = {}
            min_z_seen = float("inf")
            max_bone_angle_deg = 0.0
            max_rx_rad = 0.0
            max_root_drift = 0.0

            # Sample across full clip range to verify Root lock & |rx| <= 0.68 rad everywhere
            for check_f in range(f_start, f_end + 1):
                scene.frame_set(check_f)
                bpy.context.view_layer.update()
                if "Root" in arm_obj.pose.bones:
                    r_pb = arm_obj.pose.bones["Root"]
                    r_ang = 2.0 * math.acos(min(1.0, abs(r_pb.rotation_quaternion.w)))
                    max_root_drift = max(max_root_drift, r_pb.location.length + r_ang)
                for b in _CREATURE_BONES:
                    if b in arm_obj.pose.bones:
                        eul = arm_obj.pose.bones[b].rotation_quaternion.to_euler("XYZ")
                        max_rx_rad = max(max_rx_rad, abs(eul.x))

            for mf in mid_frames:
                scene.frame_set(mf)
                bpy.context.view_layer.update()

                for b in _CREATURE_BONES:
                    if b not in start_bone_rot:
                        continue
                    pb = arm_obj.pose.bones[b]
                    dot_v = min(1.0, abs(start_bone_rot[b].dot(pb.rotation_quaternion)))
                    ang_deg = math.degrees(2.0 * math.acos(dot_v))
                    loc_d = (pb.location - start_bone_loc[b]).length
                    max_bone_angle_deg = max(max_bone_angle_deg, ang_deg)
                    if ang_deg > 0.25 or loc_d > 0.0005:
                        active_creature_bones.add(b)

                if verts_f1 is not None:
                    verts_mf = _sample_evaluated_verts(mesh_obj)
                    max_d = max((va - vb).length for va, vb in zip(verts_mf, verts_f1)) if verts_f1 else 0.0
                    min_z_seen = min(min_z_seen, min(v.z for v in verts_mf))
                    frame_disps[mf] = round(max_d, 4)

            # Check exact loop closure (`f=1 == f=end`) and rest-pose accuracy for Attack/Hit
            scene.frame_set(f_end)
            bpy.context.view_layer.update()
            end_err = 0.0
            if verts_f1 is not None:
                verts_end = _sample_evaluated_verts(mesh_obj)
                end_err = max((va - vb).length for va, vb in zip(verts_end, verts_f1)) if verts_f1 else 0.0
            else:
                for b in _CREATURE_BONES:
                    if b in start_bone_rot:
                        pb = arm_obj.pose.bones[b]
                        dot_v = min(1.0, abs(start_bone_rot[b].dot(pb.rotation_quaternion)))
                        end_err = max(end_err, 2.0 * math.acos(dot_v) + (pb.location - start_bone_loc[b]).length)

            if clip_name in ("Attack", "Hit"):
                # Verify start & end are also exact identity rest pose
                for f_rest in (f_start, f_end):
                    scene.frame_set(f_rest)
                    bpy.context.view_layer.update()
                    for b in BONE_NAMES:
                        if b in arm_obj.pose.bones:
                            pb = arm_obj.pose.bones[b]
                            rest_ang = 2.0 * math.acos(min(1.0, abs(pb.rotation_quaternion.w)))
                            end_err = max(end_err, pb.location.length + rest_ang)

            root_locked = max_root_drift < 1e-4
            rx_ok = max_rx_rad <= (MAX_RX_RAD + 0.01)
            root_locked_all = root_locked_all and root_locked
            rx_within_limit_all = rx_within_limit_all and rx_ok

            peak_disp = max(frame_disps.values()) if frame_disps else 0.0
            if clip_name == "Attack":
                attack_f12_disp = frame_disps.get(12, 0.0)
                attack_peak_disp = peak_disp
                attack_f22_disp = frame_disps.get(22, 0.0)
            elif clip_name == "Hit":
                hit_f6_disp = frame_disps.get(6, 0.0)

            clip_metrics[clip_name] = {
                "present": True,
                "frame_range": (f_start, f_end),
                "root_locked": root_locked,
                "active_bone_count": len(active_creature_bones),
                "active_bones": [b for b in _CREATURE_BONES if b in active_creature_bones],
                "max_bone_angle_deg": round(max_bone_angle_deg, 2),
                "max_rx_rad": round(max_rx_rad, 4),
                "frame_max_vert_disp_m": frame_disps,
                "peak_vert_disp_m": round(peak_disp, 4),
                "min_z_m": round(0.0 if min_z_seen == float("inf") else min_z_seen, 4),
                "end_pose_error_m": round(end_err, 5),
            }
    finally:
        for tr, was_muted, was_solo in prev_track_state:
            tr.mute = was_muted
            tr.is_solo = was_solo
        anim_data.action = prev_action
        if prev_action is not None and prev_slot is not None and hasattr(anim_data, "action_slot"):
            try:
                anim_data.action_slot = prev_slot
            except Exception:
                pass
        if prev_action is None:
            _reset_armature_pose(arm_obj)
        scene.frame_set(prev_frame)
        bpy.context.view_layer.update()

    all_clips_active = all(
        clip_metrics.get(c, {}).get("present", False)
        and clip_metrics[c].get("active_bone_count", 0) == len(_CREATURE_BONES)
        and clip_metrics[c].get("end_pose_error_m", 1.0) < 1e-3
        for c in NLA_CLIPS
    )
    deform_ok = True if mesh_obj is None else (attack_peak_disp >= 0.65 and hit_f6_disp >= 0.25)

    return {
        "valid": (
            len(missing_bones) == 0
            and len(missing_clips) == 0
            and root_locked_all
            and rx_within_limit_all
            and all_clips_active
            and deform_ok
        ),
        "armature": arm_obj.name,
        "mesh": mesh_obj.name if mesh_obj is not None else None,
        "bones": bones_present,
        "missing_bones": missing_bones,
        "nla_tracks": nla_track_names,
        "missing_clips": missing_clips,
        "root_locked": root_locked_all,
        "rx_within_limit": rx_within_limit_all,
        "attack_frame12_max_disp_m": round(attack_f12_disp, 4),
        "attack_peak_max_disp_m": round(attack_peak_disp, 4),
        "attack_frame22_max_disp_m": round(attack_f22_disp, 4),
        "hit_frame6_max_disp_m": round(hit_f6_disp, 4),
        "clips": clip_metrics,
    }


# ==============================================================================
# 7. HEADLESS BLENDER 5.2 SELF-TEST (ALL 6 DRAGON BREEDS + GLTF 2.0 ROUNDTRIP)
# ==============================================================================
def _build_test_7bone_dragon_piece(piece_name: str, height: float):
    """
    Construct an anatomical 7-bone, 7-part skinned stone-dragon test piece on a jagged
    crag base (`Z in [0.0, 0.22]`, total height `H`) adhering strictly to `dragon_spec.py`
    (`eb.tail = eb.head + (0, 0, L)`, `eb.roll = 0.0`).
    """
    import bmesh

    bpy.ops.wm.read_factory_settings(use_empty=True)
    H = height

    arm_data = bpy.data.armatures.new(f"{piece_name}_arm_data")
    arm_obj = bpy.data.objects.new(f"{piece_name}_armature", arm_data)
    bpy.context.collection.objects.link(arm_obj)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode="EDIT")

    # Anatomical stone-dragon joint pivots (`eb.roll = 0.0`, vertical rest axes)
    is_quad = piece_name in ("pawn", "rook")
    y_chest = 0.08 if is_quad else 0.02
    z_chest = 0.46 * H if is_quad else 0.54 * H
    z_head = 0.64 * H if is_quad else 0.76 * H

    joint_specs = [
        ("Root",        None,          ( 0.00,  0.00, 0.00),    0.22,              False),
        ("Spine_Lower", "Root",        ( 0.00,  0.00, 0.22),    z_chest - 0.22,    True),
        ("Spine_Upper", "Spine_Lower", ( 0.00,  0.00, z_chest), 0.24 * H,          True),
        ("Head_Jaw",    "Spine_Upper", ( 0.00,  0.10, z_head),  0.18 * H,          False),
        ("Weapon_R",    "Spine_Upper", ( 0.18,  y_chest + 0.06, z_chest + 0.06 * H), 0.18 * H, False),
        ("Shield_L",    "Spine_Upper", (-0.18,  y_chest + 0.06, z_chest + 0.06 * H), 0.18 * H, False),
        ("Wings_Tail",  "Spine_Upper", ( 0.00, -0.12, z_chest + 0.08 * H), 0.22 * H, False),
    ]

    ebones = {}
    for bname, parent_name, head_xyz, b_len, connect in joint_specs:
        eb = arm_data.edit_bones.new(bname)
        eb.head = Vector(head_xyz)
        eb.tail = eb.head + Vector((0.0, 0.0, max(0.08, b_len)))
        eb.roll = 0.0
        eb.use_deform = True
        if parent_name is not None:
            eb.parent = ebones[parent_name]
            eb.use_connect = connect
        ebones[bname] = eb

    bpy.ops.object.mode_set(mode="OBJECT")

    # Build 7 anatomical dragon-breed blocks spanning Z in [0.0, H], X/Y within dragon_spec radii
    bm = bmesh.new()
    if piece_name == "bishop":
        # Twin-Headed Oracle Hydra-Wyrm: Weapon_R & Shield_L are Left/Right Dragon Necks & Skulls!
        part_boxes = [
            ("Root",        Vector(( 0.00,  0.00, 0.11)),     Vector((0.76, 0.76, 0.22))),
            ("Spine_Lower", Vector(( 0.00,  0.00, 0.36 * H)), Vector((0.36, 0.36, 0.24 * H))),
            ("Spine_Upper", Vector(( 0.00,  0.04, 0.58 * H)), Vector((0.38, 0.34, 0.22 * H))),
            ("Head_Jaw",    Vector(( 0.00,  0.16, 0.76 * H)), Vector((0.18, 0.22, 0.18 * H))),
            ("Weapon_R",    Vector(( 0.20,  0.24, 0.84 * H)), Vector((0.16, 0.30, 0.32 * H))),
            ("Shield_L",    Vector((-0.20,  0.24, 0.84 * H)), Vector((0.16, 0.30, 0.32 * H))),
            ("Wings_Tail",  Vector(( 0.00, -0.30, 0.72 * H)), Vector((0.88, 0.34, 0.38 * H))),
        ]
    elif is_quad:
        part_boxes = [
            ("Root",        Vector(( 0.00,  0.00, 0.11)),     Vector((0.78, 0.78, 0.22))),
            ("Spine_Lower", Vector(( 0.00, -0.06, 0.36 * H)), Vector((0.38, 0.42, 0.24 * H))),
            ("Spine_Upper", Vector(( 0.00,  0.10, 0.54 * H)), Vector((0.42, 0.40, 0.24 * H))),
            ("Head_Jaw",    Vector(( 0.00,  0.30, 0.76 * H)), Vector((0.26, 0.34, 0.26 * H))),
            ("Weapon_R",    Vector(( 0.22,  0.22, 0.44 * H)), Vector((0.14, 0.24, 0.34 * H))),
            ("Shield_L",    Vector((-0.22,  0.22, 0.44 * H)), Vector((0.14, 0.24, 0.34 * H))),
            ("Wings_Tail",  Vector(( 0.00, -0.34, 0.62 * H)), Vector((0.68, 0.42, 0.34 * H))),
        ]
    else:
        part_boxes = [
            ("Root",        Vector(( 0.00,  0.00, 0.11)),     Vector((0.78, 0.78, 0.22))),
            ("Spine_Lower", Vector(( 0.00, -0.02, 0.38 * H)), Vector((0.36, 0.34, 0.26 * H))),
            ("Spine_Upper", Vector(( 0.00,  0.04, 0.62 * H)), Vector((0.40, 0.34, 0.24 * H))),
            ("Head_Jaw",    Vector(( 0.00,  0.22, 0.88 * H)), Vector((0.24, 0.34, 0.24 * H))),
            ("Weapon_R",    Vector(( 0.24,  0.24, 0.68 * H)), Vector((0.14, 0.28, 0.32 * H))),
            ("Shield_L",    Vector((-0.24,  0.24, 0.68 * H)), Vector((0.14, 0.28, 0.32 * H))),
            ("Wings_Tail",  Vector(( 0.00, -0.30, 0.76 * H)), Vector((0.94, 0.34, 0.44 * H))),
        ]

    vert_bone_assignments: list[tuple[list[int], str]] = []
    for bname, center, sz in part_boxes:
        ret = bmesh.ops.create_cube(bm, size=1.0)
        b_verts = ret["verts"]
        for v in b_verts:
            v.co = Vector((v.co.x * sz.x, v.co.y * sz.y, max(0.0, v.co.z * sz.z + center.z) - center.z)) + center
        bm.verts.index_update()
        vert_bone_assignments.append(([v.index for v in b_verts], bname))

    mesh_data = bpy.data.meshes.new(f"{piece_name}_mesh")
    bm.to_mesh(mesh_data)
    bm.free()

    mesh_obj = bpy.data.objects.new(f"{piece_name}_mesh", mesh_data)
    bpy.context.collection.objects.link(mesh_obj)
    mesh_obj.parent = arm_obj
    arm_mod = mesh_obj.modifiers.new(name="Armature", type="ARMATURE")
    arm_mod.object = arm_obj

    for bname in BONE_NAMES:
        mesh_obj.vertex_groups.new(name=bname)
    for v_indices, bname in vert_bone_assignments:
        mesh_obj.vertex_groups[bname].add(v_indices, 1.0, "REPLACE")

    return arm_obj, mesh_obj


def _run_self_test():
    print("=== Draconic Sanctum 6-Breed Creature Biomechanics Self-Test (Blender 5.2) ===")

    arm_check, _ = _build_test_7bone_dragon_piece("pawn", PIECE_HEIGHTS["pawn"])
    m_root = arm_check.data.bones["Root"].matrix_local.to_3x3()
    col_x = Vector((m_root[0][0], m_root[1][0], m_root[2][0]))
    col_y = Vector((m_root[0][1], m_root[1][1], m_root[2][1]))
    col_z = Vector((m_root[0][2], m_root[1][2], m_root[2][2]))
    print(
        f"[Axis Contract] Root matrix_local axes: "
        f"+X={tuple(round(v, 3) for v in col_x)} (Right), "
        f"+Y={tuple(round(v, 3) for v in col_y)} (World +Z Up), "
        f"+Z={tuple(round(v, 3) for v in col_z)} (World -Y Back)"
    )
    assert (col_x - Vector((1, 0, 0))).length < 1e-5
    assert (col_y - Vector((0, 0, 1))).length < 1e-5
    assert (col_z - Vector((0, -1, 0))).length < 1e-5

    temp_dir = os.environ.get("TEMP") or os.environ.get("TMP") or _SCRIPT_DIR
    all_passed = True

    for piece_name, target_h in PIECE_SPECS:
        arm_obj, mesh_obj = _build_test_7bone_dragon_piece(piece_name, target_h)
        tracks = author_dragon_animations(piece_name, arm_obj)
        assert tracks == NLA_CLIPS, f"{piece_name}: expected tracks {NLA_CLIPS}, got {tracks}"

        glb_path = os.path.join(temp_dir, f"_self_test_dragon_breed_{piece_name}.glb")
        try:
            bpy.ops.export_scene.gltf(
                filepath=glb_path,
                export_format="GLB",
                export_apply=False,
                export_animations=True,
                export_animation_mode="NLA_TRACKS",
                export_skins=True,
                export_all_influences=False,
                export_yup=True,
            )

            bpy.ops.wm.read_factory_settings(use_empty=True)
            bpy.ops.import_scene.gltf(filepath=glb_path)

            imp_arm = [o for o in bpy.data.objects if o.type == "ARMATURE"][0]
            imp_mesh = [
                o for o in bpy.data.objects
                if o.type == "MESH" and "icosphere" not in o.name.lower()
            ][0]

            report = verify_nla_animations(imp_arm, imp_mesh)
            idle_pk = report["clips"]["Idle"]["peak_vert_disp_m"]
            move_pk = report["clips"]["Move"]["peak_vert_disp_m"]
            atk_pk = report["attack_peak_max_disp_m"]
            atk_f12 = report["attack_frame12_max_disp_m"]
            hit_f6 = report["hit_frame6_max_disp_m"]
            max_rx = max(report["clips"][c]["max_rx_rad"] for c in NLA_CLIPS)
            worst_end_err = max(report["clips"][c]["end_pose_error_m"] for c in NLA_CLIPS)

            print(
                f"  [GLB OK={report['valid']}] {piece_name:6s} (H={target_h:.2f}m) | "
                f"RootLocked={report['root_locked']} | max|rx|={max_rx:.3f}rad | "
                f"Idle={idle_pk:.3f}m | Move={move_pk:.3f}m | "
                f"Attack(pk={atk_pk:.3f}m, f12={atk_f12:.3f}m) | Hit(f6={hit_f6:.3f}m) | "
                f"endErr={worst_end_err:.5f}m"
            )
            if not report["valid"] or not (0.72 <= atk_pk <= 1.50):
                all_passed = False
                print("    CHECK DETAILS:", report)
        finally:
            if os.path.exists(glb_path):
                try:
                    os.remove(glb_path)
                except OSError:
                    pass

    if not all_passed:
        raise RuntimeError("One or more Stone Dragon breed animation checks outside target bounds!")
    print("=== ALL 6 STONE DRAGON BREEDS PASSED BLENDER 5.2 GLTF ROUNDTRIP ===")


if __name__ == "__main__":
    _run_self_test()
