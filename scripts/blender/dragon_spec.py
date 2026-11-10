"""
Shared Technical Specification Contract for DRACONIC SANCTUM (3D Carved Stone Dragons & Ruined Gothic Altar).
Used by Dragon Modeling, Gothic Cathedral & Sanctum Altar, Skeletal Rigging, and Combat Animation Blender pipelines.
"""
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TEXTURES_DIR = os.path.join(PROJECT_ROOT, "public", "assets", "textures")
MODELS_DIR = os.path.join(PROJECT_ROOT, "public", "assets", "models")
RENDERS_DIR = os.path.join(PROJECT_ROOT, "public", "assets", "renders")

for _d in (TEXTURES_DIR, MODELS_DIR, RENDERS_DIR):
    os.makedirs(_d, exist_ok=True)

TEXTURE_SIZE = 2048

# Tactical Sanctum Altar spacing in meters (replaces 1.0m checkered chessboard!)
# 8x8 ancient rune-loci span [-4.13, +4.13]m on a 12.6m ruined Gothic stone-crag & magic-circle altar.
NODE_SPACING = 1.18
MAX_CRAG_RADIUS = 0.48   # Jagged ruined rock/crag base footprint radius (Z in [0.0, 0.22])
MAX_WING_RADIUS = 0.56   # Generous wingspan/tail envelope for true anatomical dragons

# 6 Pure Anatomical Carved-Stone Dragon Breeds (ZERO human faces, ZERO robes, ZERO round lathe pedestals!)
PIECE_SPECS = [
    ("pawn",   1.08),  # Stone Hatchling Prowler (Quadruped Gargoyle Drake on jagged slate crag)
    ("rook",   1.38),  # Armored Behemoth Earth-Drake (Quadruped Ankylo-Carapace Fortress Dragon + Club Tail)
    ("knight", 1.62),  # Rearing Winged Wyvern (Bipedal Sky-Predator with swept wings & raptorial talons)
    ("bishop", 1.72),  # Twin-Headed Oracle Hydra-Wyrm (Coiled Serpentine Dragon with TWO horned dragon necks/heads!)
    ("queen",  1.94),  # Four-Winged Celestial Elder Dragon (Soaring Quad-Winged Crowned Elder Wyrm)
    ("king",   2.18),  # Sovereign Arch-Dragon (Colossal Rearing Quadrupedal Western Arch-Dragon)
]

PIECE_HEIGHTS = dict(PIECE_SPECS)

# Semantic Part IDs stored on BMesh int vertex layer "PartID":
#   0: PART_PEDESTAL   -> Jagged natural ruined-stone crag / shattered Gothic rock outcrop (grounded Z=0)
#   1: PART_LOWER_BODY -> Haunches, hindlegs, lower coiled serpent/dragon pelvis gripping the crag
#   2: PART_UPPER_BODY -> Armored ribcage, dorsal osteoderm spine, shoulder girdle & base neck
#   3: PART_HEAD_JAW   -> Primary horned dragon skull, roaring fanged jaws & crest (or central arcane crest on bishop)
#   4: PART_WEAPON_R   -> Right clawed dragon forelimb / talon (or Right Dragon Neck & Skull on twin-headed bishop!)
#   5: PART_SHIELD_L   -> Left clawed dragon forelimb / talon (or Left Dragon Neck & Skull on twin-headed bishop!)
#   6: PART_WINGS_TAIL -> Sweeping carved-stone dragon wings (2 or 4 wings) + sinuous spiked/spade dragon tail
PART_PEDESTAL   = 0
PART_LOWER_BODY = 1
PART_UPPER_BODY = 2
PART_HEAD_JAW   = 3
PART_WEAPON_R   = 4
PART_SHIELD_L   = 5
PART_WINGS_TAIL = 6

# 7-Bone Draconic Armature Hierarchy
# CRITICAL RIG/ANIMATION CONTRACT:
# Every EditBone MUST have `eb.tail = eb.head + Vector((0, 0, bone_len))` and `eb.roll = 0.0`
# (`use_connect = False` for branch bones `Head_Jaw`, `Weapon_R`, `Shield_L`, `Wings_Tail`,
# while placing `eb.head` at each part's true 3D anatomical joint pivot!).
# This guarantees identical local PoseBone axes across ALL 7 bones:
#   - Local X (`rx`): Pitch! `rx < 0` pitches FORWARD (+Y, lunge/bite/pounce); `rx > 0` pitches BACKWARD (-Y, rear-up/recoil).
#   - Local Y (`ry`): Yaw/Twist around vertical world Z axis (serpentine weave, head sweep)!
#   - Local Z (`rz`): Roll/Bank in world XZ plane (wing-beat/flare, claw swipe, twin-head snap)!
BONE_NAMES = [
    "Root",
    "Spine_Lower",
    "Spine_Upper",
    "Head_Jaw",
    "Weapon_R",
    "Shield_L",
    "Wings_Tail",
]

# Required NLA Animation Track Names (exported via glTF NLA_TRACKS)
NLA_CLIPS = ["Idle", "Move", "Attack", "Hit"]

# Symmetric UV V-Coordinate Zones (symmetric around v = 0.5 so flipY True/False both align!)
# s = 0.5 - abs(v - 0.5)
# - UV_ZONE_SCALES : v in [0.35, 0.65] (s in [0.35, 0.50]) -> Chiselled imbricated dragon osteoderm scales
# - UV_ZONE_STONE  : v in [0.68, 0.80] (s in [0.20, 0.32]) -> Weathered crag rock, horns, fangs, talons, wing membranes
# - UV_ZONE_RUNES  : v in [0.82, 0.89] (s in [0.11, 0.18]) -> Recessed glowing draconic breath-core, eyes & rune veins
# - UV_ZONE_BRONZE : v in [0.92, 0.98] (s in [0.02, 0.08]) -> Dark weathered obsidian-bronze horn-rings / ancient crag trim
UV_ZONE_SCALES = (0.35, 0.65)
UV_ZONE_STONE  = (0.68, 0.80)
UV_ZONE_RUNES  = (0.82, 0.89)
UV_ZONE_BRONZE = (0.92, 0.98)
