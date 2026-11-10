import os
import sys
import bpy

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from dragon_spec import (
    MODELS_DIR,
    PIECE_SPECS,
    TEXTURE_SIZE,
)
import piece_pbr
import piece_meshes
import piece_rigging
import piece_animations
from build_pieces import clear_scene, export_piece_glb

def build_single(pname="bishop"):
    print(f"\n--- Building Single Piece: {pname.upper()} ---")
    clear_scene()
    mat = piece_pbr.create_dragon_piece_material("white_piece")
    mesh_data, part_ids = piece_meshes.build_piece_mesh_data(pname)
    mesh_obj = bpy.data.objects.new(f"{pname}_mesh", mesh_data)
    bpy.context.collection.objects.link(mesh_obj)
    mesh_obj.data.materials.append(mat)

    arm_obj = piece_rigging.rig_dragon_piece(pname, mesh_obj, part_ids)
    rig_stats = piece_rigging.validate_rig(arm_obj, mesh_obj)
    print(f"  [Rig Validated] {rig_stats}")

    clips = piece_animations.author_dragon_animations(pname, arm_obj)
    print(f"  [NLA Clips Authored] {clips}")

    export_piece_glb(pname)
    print(f"--- Successfully Exported {pname}.glb ---")

if __name__ == "__main__":
    pname = "bishop"
    if len(sys.argv) > 1 and not sys.argv[-1].endswith(".py"):
        pname = sys.argv[-1]
    build_single(pname)

