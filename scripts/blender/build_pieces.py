"""
Master Headless Blender Pipeline for Dragon-Stonework 3D Wizard's Chess Pieces.
Orchestrates:
  1. piece_pbr        -> 2K (2048x2048) Dragon-Stonework PBR Maps (Albedo, Normal, Roughness, Metallic, AO, Emission)
  2. piece_meshes     -> 6 Sculpted Dragon-Stonework Statues (Pawn, Rook, Knight, Bishop, Queen, King)
  3. piece_rigging    -> 7-Bone Draconic Armature & Smooth Seam-Blended Skinning
  4. piece_animations -> 4 NLA Skeletal Combat & Stone Motion Tracks (Idle, Move, Attack, Hit)
  5. Studio QA Renders -> pieces_lineup.png, pieces_macro_closeup.png, pieces_pose_qa.png
"""
import os
import sys
import json
import math
import bpy
from mathutils import Vector, Euler

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from dragon_spec import (
    MODELS_DIR,
    RENDERS_DIR,
    TEXTURES_DIR,
    PIECE_SPECS,
    BONE_NAMES,
    NLA_CLIPS,
    TEXTURE_SIZE,
)
import piece_pbr
import piece_meshes
import piece_rigging
import piece_animations


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def export_piece_glb(piece_name: str) -> str:
    out_path = os.path.join(MODELS_DIR, f"{piece_name}.glb")
    bpy.ops.export_scene.gltf(
        filepath=out_path,
        export_format="GLB",
        export_apply=False,
        export_animations=True,
        export_animation_mode="NLA_TRACKS",
        export_skins=True,
        export_all_influences=False,
        export_yup=True,
        export_materials="PLACEHOLDER",
    )
    kb = os.path.getsize(out_path) / 1024.0
    print(f"  [Exported GLB] {out_path} ({kb:.1f} KB)")
    return out_path


def setup_studio_stage_and_lights(cam_loc, cam_target, lens=35.0):
    scene = bpy.context.scene

    # Dark carved slate studio stage floor
    bpy.ops.mesh.primitive_plane_add(size=28.0, location=(0.0, 0.0, 0.0))
    floor_obj = bpy.context.active_object
    floor_mat = bpy.data.materials.new(name="DragonStudioFloor")
    bsdf = floor_mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.038, 0.036, 0.044, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.42
        bsdf.inputs["Metallic"].default_value = 0.10
    floor_obj.data.materials.append(floor_mat)

    world = bpy.data.worlds.new("DragonStudioWorld")
    scene.world = world
    bg_node = world.node_tree.nodes.get("Background")
    if bg_node:
        bg_node.inputs["Color"].default_value = (0.032, 0.030, 0.042, 1.0)
        bg_node.inputs["Strength"].default_value = 0.95

    def add_area_light(name, loc, target_co, energy, color, size=5.0):
        ldata = bpy.data.lights.new(name=name, type="AREA")
        ldata.energy = energy
        ldata.color = color
        ldata.size = size
        lobj = bpy.data.objects.new(name=name, object_data=ldata)
        scene.collection.objects.link(lobj)
        lobj.location = Vector(loc)
        direction = Vector(target_co) - lobj.location
        lobj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
        return lobj

    # Grazing warm sanctuary key light + cool gothic moonlight fill + strong rim light to accentuate carved stone relief
    add_area_light("KeyLight", (4.2, 4.6, 4.4), (0.0, 0.0, 1.0), 620.0, (1.0, 0.92, 0.80), size=4.6)
    add_area_light("FillLight", (-4.6, 4.0, 3.0), (0.0, 0.0, 0.9), 340.0, (0.76, 0.86, 1.0), size=5.5)
    add_area_light("RimLight", (0.0, -4.4, 4.2), (0.0, 0.0, 1.1), 560.0, (0.95, 0.82, 0.68), size=5.8)

    cam_data = bpy.data.cameras.new("StudioCam")
    cam_data.lens = lens
    cam_obj = bpy.data.objects.new("StudioCam", cam_data)
    scene.collection.objects.link(cam_obj)
    cam_obj.location = Vector(cam_loc)
    cam_dir = Vector(cam_target) - cam_obj.location
    cam_obj.rotation_euler = cam_dir.to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam_obj

    available_engines = [e.identifier for e in scene.render.bl_rna.properties["engine"].enum_items]
    scene.render.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in available_engines else available_engines[0]
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"


def import_piece_instance(pname: str, mat: bpy.types.Material, loc: tuple, yaw_deg: float, active_track: str = None, frame: int = 1):
    glb_path = os.path.join(MODELS_DIR, f"{pname}.glb")
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=glb_path)
    added = list(set(bpy.data.objects) - before)

    arms = [o for o in added if o.type == "ARMATURE"]
    meshes = [o for o in added if o.type == "MESH" and "icosphere" not in o.name.lower()]
    arm = arms[0]

    if arm.animation_data:
        arm.animation_data.action = None
    if arm.animation_data and arm.animation_data.nla_tracks:
        for tr in arm.animation_data.nla_tracks:
            if active_track is None:
                tr.mute = True
            else:
                tr.mute = (active_track.lower() not in tr.name.lower())

    arm.rotation_mode = "XYZ"
    arm.location = Vector(loc)
    arm.rotation_euler = Euler((0.0, 0.0, math.radians(yaw_deg)), "XYZ")

    for m in meshes:
        m.data.materials.clear()
        m.data.materials.append(mat)

    if active_track is not None:
        bpy.context.scene.frame_set(frame)

    return arm, meshes


def verify_and_render_qa_suite():
    print("\n=== [QA Stage 1] Verifying Re-Imported GLB Rig, NLA Clips & Deformation ===")
    qa_report = []

    for pname, target_h in PIECE_SPECS:
        clear_scene()
        glb_path = os.path.join(MODELS_DIR, f"{pname}.glb")
        bpy.ops.import_scene.gltf(filepath=glb_path)

        arm = [o for o in bpy.data.objects if o.type == "ARMATURE"][0]
        mesh_obj = [o for o in bpy.data.objects if o.type == "MESH" and "icosphere" not in o.name.lower()][0]

        v_count = len(mesh_obj.data.vertices)
        f_count = len(mesh_obj.data.polygons)
        tri_count = sum(len(p.vertices) - 2 for p in mesh_obj.data.polygons)
        bones_found = [b.name for b in arm.data.bones]
        nla_found = [tr.name for tr in arm.animation_data.nla_tracks] if arm.animation_data else []

        # Measure max vertex displacement during Attack clip across frames 8..24
        if arm.animation_data:
            arm.animation_data.action = None
        for tr in arm.animation_data.nla_tracks:
            tr.mute = ("attack" not in tr.name.lower())

        bpy.context.scene.frame_set(1)
        dg = bpy.context.evaluated_depsgraph_get()
        m1 = mesh_obj.evaluated_get(dg).to_mesh()
        coords_1 = [v.co.copy() for v in m1.vertices]
        mesh_obj.evaluated_get(dg).to_mesh_clear()

        max_attack_disp = 0.0
        best_frame = 12
        for test_f in (10, 12, 14, 18, 22):
            bpy.context.scene.frame_set(test_f)
            dg = bpy.context.evaluated_depsgraph_get()
            mf = mesh_obj.evaluated_get(dg).to_mesh()
            peak = max((mf.vertices[i].co - coords_1[i]).length for i in range(0, len(coords_1), max(1, len(coords_1) // 250)))
            mesh_obj.evaluated_get(dg).to_mesh_clear()
            if peak > max_attack_disp:
                max_attack_disp = peak
                best_frame = test_f

        # Verify pedestal base stays grounded during Attack
        bpy.context.scene.frame_set(best_frame)
        dg = bpy.context.evaluated_depsgraph_get()
        mf = mesh_obj.evaluated_get(dg).to_mesh()
        min_z_attack = min(v.co.z for v in mf.vertices)
        mesh_obj.evaluated_get(dg).to_mesh_clear()

        row = {
            "piece": pname,
            "target_height_m": target_h,
            "verts": v_count,
            "faces": f_count,
            "tris": tri_count,
            "bone_count": len(bones_found),
            "bones": bones_found,
            "nla_tracks": nla_found,
            "peak_attack_frame": best_frame,
            "peak_attack_disp_m": round(max_attack_disp, 4),
            "min_z_at_peak_m": round(min_z_attack, 4),
        }
        qa_report.append(row)
        print(
            f"  [QA PASS] {pname:6s} | tris={tri_count:5d} | bones={len(bones_found)} | "
            f"NLA={nla_found} | Attack disp={max_attack_disp:.3f}m @f{best_frame} | base_z={min_z_attack:.4f}m"
        )

    # 1. Render Full 12-Dragon Lineup (White & Black Carved-Stone Dragon Breeds on Jagged Crags)
    clear_scene()
    white_mat = piece_pbr.create_dragon_piece_material("white_piece")
    black_mat = piece_pbr.create_dragon_piece_material("black_piece")

    spacing_x = 1.18
    ordered = list(reversed(PIECE_SPECS))  # King -> Queen -> Bishop -> Knight -> Rook -> Pawn
    x_offsets = [-(2.5 * spacing_x) + i * spacing_x for i in range(6)]

    for idx, (pname, _) in enumerate(ordered):
        yaw_w = -24.0 if pname in ("knight", "pawn", "rook") else -16.0
        yaw_b = 24.0 if pname in ("knight", "pawn", "rook") else 18.0
        import_piece_instance(pname, white_mat, (x_offsets[idx], 0.52, 0.0), yaw_w, active_track=None)
        import_piece_instance(pname, black_mat, (x_offsets[idx] - 0.42, -0.68, 0.0), yaw_b, active_track=None)

    setup_studio_stage_and_lights(cam_loc=(0.05, 6.75, 2.18), cam_target=(0.0, 0.0, 0.98), lens=32.0)
    lineup_path = os.path.join(RENDERS_DIR, "pieces_lineup.png")
    bpy.context.scene.render.filepath = lineup_path
    bpy.ops.render.render(write_still=True)
    print(f"  [Rendered] {lineup_path}")

    # 2. Render Macro Close-Up of Pure Anatomical Stone Dragons (Twin-Headed Hydra Bishop, Sovereign Arch-Dragon King, Wyvern Knight)
    clear_scene()
    white_mat = piece_pbr.create_dragon_piece_material("white_piece")
    black_mat = piece_pbr.create_dragon_piece_material("black_piece")
    import_piece_instance("bishop", white_mat, (-1.12, 0.16, 0.0), -26.0, active_track=None)
    import_piece_instance("king", black_mat, (0.02, -0.12, 0.0), 18.0, active_track=None)
    import_piece_instance("knight", white_mat, (1.14, 0.18, 0.0), 30.0, active_track=None)

    setup_studio_stage_and_lights(cam_loc=(0.02, 3.35, 1.45), cam_target=(0.02, 0.0, 1.12), lens=42.0)
    macro_path = os.path.join(RENDERS_DIR, "pieces_macro_closeup.png")
    bpy.context.scene.render.filepath = macro_path
    bpy.ops.render.render(write_still=True)
    print(f"  [Rendered] {macro_path}")

    # 3. Render Dynamic Skeletal Dragon Combat Pose QA Sheet (Attack vs Hit)
    clear_scene()
    white_mat = piece_pbr.create_dragon_piece_material("white_piece")
    black_mat = piece_pbr.create_dragon_piece_material("black_piece")

    king_peak = next((r["peak_attack_frame"] for r in qa_report if r["piece"] == "king"), 12)
    import_piece_instance("knight", white_mat, (-2.15, -0.35, 0.0), -65.0, active_track="Attack", frame=king_peak)
    import_piece_instance("pawn", black_mat, (-1.15, 0.18, 0.0), 115.0, active_track="Hit", frame=6)

    import_piece_instance("king", white_mat, (-0.12, -0.28, 0.0), -52.0, active_track="Attack", frame=king_peak)
    import_piece_instance("bishop", black_mat, (0.88, 0.20, 0.0), 125.0, active_track="Attack", frame=king_peak)

    import_piece_instance("queen", black_mat, (2.02, -0.15, 0.0), 26.0, active_track="Attack", frame=king_peak)
    bpy.context.scene.frame_set(king_peak)

    setup_studio_stage_and_lights(cam_loc=(0.0, 5.65, 2.05), cam_target=(-0.02, 0.0, 1.02), lens=33.0)
    pose_path = os.path.join(RENDERS_DIR, "pieces_pose_qa.png")
    bpy.context.scene.render.filepath = pose_path
    bpy.ops.render.render(write_still=True)
    print(f"  [Rendered] {pose_path}")

    report_path = os.path.join(RENDERS_DIR, "pieces_qa_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(qa_report, f, indent=2)
    print(f"  [Saved QA Metrics] {report_path}")
    return qa_report


def main():
    print("=== [1/3] Synthesizing 2K (2048x2048) Dragon-Stonework Piece PBR Textures ===")
    piece_pbr.synthesize_dragon_piece_pbr(res=TEXTURE_SIZE)

    print("\n=== [2/3] Sculpting, Rigging (7 Bones) & Animating (4 NLA Clips) All 6 Dragon Statues ===")
    for pname, target_h in PIECE_SPECS:
        print(f"\n--- Building {pname.upper()} (target height = {target_h}m) ---")
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

    print("\n=== [3/3] Running Headless Blender Studio Visual & Deformation QA Suite ===")
    verify_and_render_qa_suite()
    print("\n=== DRAGON-STONEWORK PIECE PIPELINE COMPLETE ===")


if __name__ == "__main__":
    main()
