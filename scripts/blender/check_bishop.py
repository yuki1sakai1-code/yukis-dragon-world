import sys
import os

SCRIPT_DIR = r"c:\Users\yukis\Downloads\chess - コピー\scripts\blender"
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
import piece_meshes
from dragon_spec import (
    PART_HEAD_JAW,
    PART_WEAPON_R,
    PART_SHIELD_L,
    PART_UPPER_BODY,
    PART_LOWER_BODY,
    PART_WINGS_TAIL,
    PART_PEDESTAL,
)

sc = piece_meshes.DragonSculptor()
piece_meshes._sculpt_bishop(sc)
bm = sc.bm
part_layer = bm.verts.layers.int.get("PartID")

parts = {
    PART_PEDESTAL: "PEDESTAL",
    PART_LOWER_BODY: "LOWER",
    PART_UPPER_BODY: "UPPER",
    PART_HEAD_JAW: "HEAD_JAW (Crest/Core)",
    PART_WEAPON_R: "WEAPON_R (Right Neck/Head)",
    PART_SHIELD_L: "SHIELD_L (Left Neck/Head)",
    PART_WINGS_TAIL: "WINGS_TAIL",
}
for pid, name in parts.items():
    coords = [v.co for v in bm.verts if v[part_layer] == pid]
    if coords:
        min_x = min(c.x for c in coords)
        max_x = max(c.x for c in coords)
        min_y = min(c.y for c in coords)
        max_y = max(c.y for c in coords)
        min_z = min(c.z for c in coords)
        max_z = max(c.z for c in coords)
        print(f"{name}: count={len(coords)} | X=[{min_x:.3f}, {max_x:.3f}] Y=[{min_y:.3f}, {max_y:.3f}] Z=[{min_z:.3f}, {max_z:.3f}]")

