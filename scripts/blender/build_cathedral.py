"""
3D Gothic Dragon-Sanctum Cathedral & Ritual Altar Builder (Headless Blender 5.2).
Builds gothic_cathedral.glb and renders cathedral_preview.png using dragon_spec.py paths.
"""
import os
import sys
import math
import bpy
import bmesh
from mathutils import Vector, Matrix

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dragon_spec import TEXTURES_DIR, MODELS_DIR, RENDERS_DIR

TEX_DIR = TEXTURES_DIR
MODEL_DIR = MODELS_DIR
RENDER_DIR = RENDERS_DIR

os.makedirs(MODEL_DIR, exist_ok=True)
os.makedirs(RENDER_DIR, exist_ok=True)

# 1. Ensure all 20 deterministic 2048x2048 PBR maps exist
REQUIRED_TEXTURES = [
    "cathedral_stone_albedo.png", "cathedral_stone_normal.png", "cathedral_stone_roughness.png", "cathedral_stone_ao.png",
    "cathedral_floor_albedo.png", "cathedral_floor_normal.png", "cathedral_floor_roughness.png", "cathedral_floor_ao.png",
    "stained_glass_albedo.png", "stained_glass_emission.png", "stained_glass_roughness.png",
    "board_frame_albedo.png", "board_frame_normal.png", "board_frame_roughness.png", "board_frame_metallic.png",
    "board_tiles_albedo.png", "board_tiles_normal.png", "board_tiles_roughness.png", "board_tiles_metallic.png", "board_tiles_ao.png",
]

if not all(os.path.exists(os.path.join(TEX_DIR, t)) for t in REQUIRED_TEXTURES):
    import generate_textures
    generate_textures.generate_all_textures()


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def load_image(filename, is_data=False):
    path = os.path.join(TEX_DIR, filename)
    img = bpy.data.images.load(path, check_existing=True)
    img.colorspace_settings.name = 'Non-Color' if is_data else 'sRGB'
    return img


def get_gltf_occlusion_group():
    """Official Blender glTF 2.0 node group for exporting occlusionTexture cleanly into GLB."""
    group_name = "glTF Material Output"
    if group_name in bpy.data.node_groups:
        return bpy.data.node_groups[group_name]
    ng = bpy.data.node_groups.new(group_name, 'ShaderNodeTree')
    if hasattr(ng, 'interface'):
        ng.interface.new_socket(name="Occlusion", in_out='INPUT', socket_type='NodeSocketFloat')
    else:
        ng.inputs.new('NodeSocketFloat', "Occlusion")
    return ng


def create_pbr_material(
    name,
    albedo_file=None,
    normal_file=None,
    rough_file=None,
    metallic_file=None,
    emission_file=None,
    ao_file=None,
    base_color=(0.5, 0.5, 0.5, 1.0),
    metallic_val=0.0,
    roughness_val=0.65,
    normal_strength=1.2,
    emission_color=None,
    emission_strength=0.0,
):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    out = nodes.new('ShaderNodeOutputMaterial')
    out.location = (650, 0)

    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (260, 0)
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])

    bsdf.inputs['Base Color'].default_value = base_color
    bsdf.inputs['Metallic'].default_value = metallic_val
    bsdf.inputs['Roughness'].default_value = roughness_val
    if 'Specular IOR Level' in bsdf.inputs:
        bsdf.inputs['Specular IOR Level'].default_value = 0.38

    uv_node = nodes.new('ShaderNodeUVMap')
    uv_node.uv_map = "UVMap"
    uv_node.location = (-750, 0)

    if albedo_file:
        tex_alb = nodes.new('ShaderNodeTexImage')
        tex_alb.location = (-320, 320)
        tex_alb.image = load_image(albedo_file, is_data=False)
        links.new(uv_node.outputs['UV'], tex_alb.inputs['Vector'])
        # Direct link to Base Color guarantees 100% glTF baseColorTexture export
        links.new(tex_alb.outputs['Color'], bsdf.inputs['Base Color'])

    if ao_file:
        tex_ao = nodes.new('ShaderNodeTexImage')
        tex_ao.location = (-320, 60)
        tex_ao.image = load_image(ao_file, is_data=True)
        links.new(uv_node.outputs['UV'], tex_ao.inputs['Vector'])
        gltf_grp = nodes.new('ShaderNodeGroup')
        gltf_grp.node_tree = get_gltf_occlusion_group()
        gltf_grp.location = (260, 260)
        links.new(tex_ao.outputs['Color'], gltf_grp.inputs['Occlusion'])

    if rough_file:
        tex_rough = nodes.new('ShaderNodeTexImage')
        tex_rough.location = (-320, -180)
        tex_rough.image = load_image(rough_file, is_data=True)
        links.new(uv_node.outputs['UV'], tex_rough.inputs['Vector'])
        links.new(tex_rough.outputs['Color'], bsdf.inputs['Roughness'])

    if metallic_file:
        tex_met = nodes.new('ShaderNodeTexImage')
        tex_met.location = (-320, -400)
        tex_met.image = load_image(metallic_file, is_data=True)
        links.new(uv_node.outputs['UV'], tex_met.inputs['Vector'])
        links.new(tex_met.outputs['Color'], bsdf.inputs['Metallic'])

    if normal_file:
        tex_norm = nodes.new('ShaderNodeTexImage')
        tex_norm.location = (-320, -640)
        tex_norm.image = load_image(normal_file, is_data=True)
        links.new(uv_node.outputs['UV'], tex_norm.inputs['Vector'])
        norm_node = nodes.new('ShaderNodeNormalMap')
        norm_node.location = (-20, -520)
        norm_node.inputs['Strength'].default_value = normal_strength
        links.new(tex_norm.outputs['Color'], norm_node.inputs['Color'])
        links.new(norm_node.outputs['Normal'], bsdf.inputs['Normal'])

    if emission_file:
        tex_em = nodes.new('ShaderNodeTexImage')
        tex_em.location = (-320, 580)
        tex_em.image = load_image(emission_file, is_data=False)
        links.new(uv_node.outputs['UV'], tex_em.inputs['Vector'])
        if 'Emission Color' in bsdf.inputs:
            links.new(tex_em.outputs['Color'], bsdf.inputs['Emission Color'])
            bsdf.inputs['Emission Strength'].default_value = emission_strength if emission_strength > 0 else 2.4
        elif 'Emission' in bsdf.inputs:
            links.new(tex_em.outputs['Color'], bsdf.inputs['Emission'])
    elif emission_color is not None and emission_strength > 0:
        if 'Emission Color' in bsdf.inputs:
            bsdf.inputs['Emission Color'].default_value = emission_color
            bsdf.inputs['Emission Strength'].default_value = emission_strength
        elif 'Emission' in bsdf.inputs:
            bsdf.inputs['Emission'].default_value = emission_color

    return mat


# ==============================================================================
# GEOMETRY & UV HELPERS
# ==============================================================================
def apply_box_uvs(obj, scale=0.25):
    """Assign clean world-space triplanar box UVs so masonry & moldings tile seamlessly."""
    mesh = obj.data
    if not mesh.uv_layers:
        mesh.uv_layers.new(name="UVMap")
    uv_layer = mesh.uv_layers.active.data
    mat_world = obj.matrix_world
    rot_world = mat_world.to_3x3()
    for poly in mesh.polygons:
        n = (rot_world @ poly.normal).normalized()
        ax, ay, az = abs(n.x), abs(n.y), abs(n.z)
        for loop_idx in poly.loop_indices:
            v_idx = mesh.loops[loop_idx].vertex_index
            co = mat_world @ mesh.vertices[v_idx].co
            if az >= ax and az >= ay:
                uv_layer[loop_idx].uv = (co.x * scale, co.y * scale)
            elif ax >= ay and ax >= az:
                uv_layer[loop_idx].uv = (co.y * scale, co.z * scale)
            else:
                uv_layer[loop_idx].uv = (co.x * scale, co.z * scale)


def apply_beam_uvs(obj, along_axis='X', u_scale=0.22, v_span=0.92):
    """
    Map longitudinal border beams so U runs along the beam length and V spans [0, 0.5] across its width/height,
    aligning dragon scales, wyrm-interlace moldings, runic channels, and bronze hairlines parallel to all 4 board edges!
    """
    mesh = obj.data
    if not mesh.uv_layers:
        mesh.uv_layers.new(name="UVMap")
    uv_layer = mesh.uv_layers.active.data
    mat_world = obj.matrix_world
    rot_world = mat_world.to_3x3()
    center = obj.location
    for poly in mesh.polygons:
        n = (rot_world @ poly.normal).normalized()
        az = abs(n.z)
        for loop_idx in poly.loop_indices:
            co = mat_world @ mesh.vertices[mesh.loops[loop_idx].vertex_index].co
            if along_axis == 'X':
                u = co.x * u_scale
                across = (co.y - center.y) / (v_span + 1e-6) + 0.5 if az > 0.5 else (co.z - center.z) / 0.45 + 0.5
            else:
                u = co.y * u_scale
                across = (co.x - center.x) / (v_span + 1e-6) + 0.5 if az > 0.5 else (co.z - center.z) / 0.45 + 0.5
            uv_layer[loop_idx].uv = (u, across * 0.5)


def finalize_bmesh_object(bm, name, mat, uv_scale=0.30, location=(0, 0, 0), rot=(0, 0, 0)):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = location
    obj.rotation_euler = rot
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    bpy.context.view_layer.update()
    apply_box_uvs(obj, scale=uv_scale)
    return obj


def add_box(name, center, size, mat, uv_scale=0.25, bevel_width=0.0, rot=(0, 0, 0)):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=size, verts=bm.verts)
    if bevel_width > 0.0:
        bmesh.ops.bevel(bm, geom=bm.edges, offset=bevel_width, segments=2, profile=0.5, affect='EDGES')
    return finalize_bmesh_object(bm, name, mat, uv_scale=uv_scale, location=center, rot=rot)


def add_cylinder(name, center, radius, depth, vertices, mat, uv_scale=0.25, rot=(0, 0, 0)):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=vertices, radius1=radius, radius2=radius, depth=depth)
    return finalize_bmesh_object(bm, name, mat, uv_scale=uv_scale, location=center, rot=rot)


def add_cone(name, center, radius1, radius2, depth, vertices, mat, uv_scale=0.25, rot=(0, 0, 0)):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=vertices, radius1=radius1, radius2=radius2, depth=depth)
    return finalize_bmesh_object(bm, name, mat, uv_scale=uv_scale, location=center, rot=rot)


def create_pointed_arch_rib(name, p_start, p_end, z_base, z_peak, thickness, depth, mat, segments=18, uv_scale=0.25):
    """Creates a Gothic pointed arch rib between two XY points rising from z_base to z_peak."""
    p0 = Vector((p_start[0], p_start[1], z_base))
    p1 = Vector((p_end[0], p_end[1], z_base))
    span_vec = p1 - p0
    dir_vec = span_vec.normalized()
    perp_vec = Vector((-dir_vec.y, dir_vec.x, 0.0))

    bm = bmesh.new()
    half_w = thickness * 0.5
    half_d = depth * 0.5

    rings = []
    for i in range(segments + 1):
        t = i / segments
        if t <= 0.5:
            u = t * 2.0
            horiz = u * 0.5
        else:
            u = (1.0 - t) * 2.0
            horiz = 1.0 - u * 0.5
        z_h = z_base + (z_peak - z_base) * math.sin(u * math.pi * 0.5)

        center_pt = p0.lerp(p1, horiz)
        center_pt.z = z_h

        # Moulded Gothic rib profile (6-sided chamfered rib)
        v0 = bm.verts.new(center_pt + perp_vec * half_w + Vector((0, 0, half_d)))
        v1 = bm.verts.new(center_pt - perp_vec * half_w + Vector((0, 0, half_d)))
        v2 = bm.verts.new(center_pt - perp_vec * (half_w * 0.88) - Vector((0, 0, half_d * 0.35)))
        v3 = bm.verts.new(center_pt - perp_vec * (half_w * 0.48) - Vector((0, 0, half_d)))
        v4 = bm.verts.new(center_pt + perp_vec * (half_w * 0.48) - Vector((0, 0, half_d)))
        v5 = bm.verts.new(center_pt + perp_vec * (half_w * 0.88) - Vector((0, 0, half_d * 0.35)))
        rings.append((v0, v1, v2, v3, v4, v5))

    n_prof = len(rings[0])
    for i in range(len(rings) - 1):
        rA, rB = rings[i], rings[i + 1]
        for k in range(n_prof):
            kn = (k + 1) % n_prof
            bm.faces.new((rA[k], rA[kn], rB[kn], rB[k]))

    bm.faces.new(rings[0][::-1])
    bm.faces.new(rings[-1])
    return finalize_bmesh_object(bm, name, mat, uv_scale=uv_scale)


# ==============================================================================
# SCULPTURAL BMESH DRAGON GARGOYLE & WING BUILDERS
# ==============================================================================
def _loft_rings(bm, ring_pts_list, cap_start=True, cap_end=True):
    """Lofts a sequence of equal-length 3D point loops into watertight BMesh quad tubes + triangle-fan caps."""
    vert_rings = [[bm.verts.new(pt) for pt in ring] for ring in ring_pts_list]
    n = len(vert_rings[0])
    for i in range(len(vert_rings) - 1):
        rA, rB = vert_rings[i], vert_rings[i + 1]
        for k in range(n):
            kn = (k + 1) % n
            bm.faces.new((rA[k], rA[kn], rB[kn], rB[k]))

    if cap_start:
        c0 = sum((v.co for v in vert_rings[0]), Vector((0, 0, 0))) / n
        vc0 = bm.verts.new(c0)
        for k in range(n):
            kn = (k + 1) % n
            bm.faces.new((vert_rings[0][kn], vert_rings[0][k], vc0))

    if cap_end:
        c1 = sum((v.co for v in vert_rings[-1]), Vector((0, 0, 0))) / n
        vc1 = bm.verts.new(c1)
        for k in range(n):
            kn = (k + 1) % n
            bm.faces.new((vert_rings[-1][k], vert_rings[-1][kn], vc1))


def _chiselled_dragon_ring(center, right, local_up, rx, rz, brow_flare=0.0, jaw_taper=0.0):
    """8-vertex faceted Gothic stone cross-section with dorsal ridge, brow ridges, cheekbones & ventral keel."""
    profile = [
        (0.0, rz * 1.15),                                               # Dorsal keel crest
        (rx * (0.78 + brow_flare), rz * (0.72 + brow_flare * 0.45)),    # Right supraorbital brow
        (rx * (1.0 - jaw_taper * 0.35), rz * 0.05),                     # Right zygomatic cheek
        (rx * (0.66 - jaw_taper * 0.30), -rz * 0.72),                   # Right lower margin
        (0.0, -rz * 0.92),                                              # Ventral keel
        (-rx * (0.66 - jaw_taper * 0.30), -rz * 0.72),                  # Left lower margin
        (-rx * (1.0 - jaw_taper * 0.35), rz * 0.05),                    # Left zygomatic cheek
        (-rx * (0.78 + brow_flare), rz * (0.72 + brow_flare * 0.45)),   # Left supraorbital brow
    ]
    return [center + right * px + local_up * pz for (px, pz) in profile]


def _oct_ring(center, right, local_up, r):
    pts = []
    for k in range(6):
        a = (k / 6.0) * 2.0 * math.pi
        pts.append(center + right * (r * math.cos(a)) + local_up * (r * math.sin(a)))
    return pts


def _add_dorsal_spine(bm, base_pt, fwd, right, up, length=0.14, height=0.16, half_w=0.035):
    """Adds a chiselled triangular stone dorsal spine plate."""
    p_back = base_pt - fwd * (length * 0.5)
    p_front = base_pt + fwd * (length * 0.5)
    p_tip = base_pt - fwd * (length * 0.22) + up * height
    v_bl = bm.verts.new(p_back - right * half_w)
    v_br = bm.verts.new(p_back + right * half_w)
    v_fl = bm.verts.new(p_front - right * (half_w * 0.7))
    v_fr = bm.verts.new(p_front + right * (half_w * 0.7))
    v_top = bm.verts.new(p_tip)
    bm.faces.new((v_bl, v_br, v_fr, v_fl))
    bm.faces.new((v_bl, v_fl, v_top))
    bm.faces.new((v_fr, v_br, v_top))
    bm.faces.new((v_fl, v_fr, v_top))
    bm.faces.new((v_br, v_bl, v_top))


def _add_bat_wing_geometry(bm, p_shoulder, p_wrist, p_thumb_tip, finger_tips, right_normal, thickness=0.055):
    """
    Builds a sculpted Gothic stone dragon wing with thick arm spar, wrist thumb-claw,
    raised finger ribs, and scalloped stone wing membranes between finger tips.
    """
    up_w = (p_wrist - p_shoulder).normalized()
    perp_arm = up_w.cross(right_normal).normalized()
    # 1. Wing arm spar (shoulder -> wrist)
    arm_rings = [
        _oct_ring(p_shoulder.lerp(p_wrist, t), right_normal, perp_arm, 0.085 * (1.0 - 0.32 * t))
        for t in (0.0, 0.35, 0.70, 1.0)
    ]
    _loft_rings(bm, arm_rings)

    # 2. Sharp stone wing-thumb claw at wrist apex
    u_th = (p_thumb_tip - p_wrist).normalized()
    p_th = u_th.cross(right_normal).normalized()
    thumb_rings = [
        _oct_ring(p_wrist.lerp(p_thumb_tip, t), right_normal, p_th, 0.052 * (1.0 - 0.82 * t))
        for t in (0.0, 0.5, 1.0)
    ]
    _loft_rings(bm, thumb_rings)

    # 3. Wing finger ribs radiating from wrist to finger_tips[:-1] (last point is inner trailing root)
    for f_pt in finger_tips[:-1]:
        uf = (f_pt - p_wrist).normalized()
        pf = uf.cross(right_normal).normalized()
        f_rings = [
            _oct_ring(p_wrist.lerp(f_pt, t), right_normal, pf, 0.046 * (1.0 - 0.68 * t))
            for t in (0.0, 0.5, 1.0)
        ]
        _loft_rings(bm, f_rings)

    # 4. Scalloped double-sided stone membrane webs between adjacent spars
    # Web panels: (p_wrist, finger_tips[k], mid_scallop, finger_tips[k+1]) plus inner panel (p_shoulder, p_wrist, finger_tips[-2], finger_tips[-1])
    half_t = right_normal * (thickness * 0.5)
    for k in range(len(finger_tips) - 1):
        fa = finger_tips[k]
        fb = finger_tips[k + 1]
        hub = p_wrist if k < len(finger_tips) - 2 else p_shoulder
        # Concave Gothic scallop midpoint pulled 22% inward toward hub
        f_mid = (fa + fb) * 0.5
        scallop = f_mid.lerp(hub, 0.22)
        for sub_a, sub_b in ((fa, scallop), (scallop, fb)):
            pts_pos = [hub + half_t, sub_a + half_t, sub_b + half_t]
            pts_neg = [hub - half_t, sub_a - half_t, sub_b - half_t]
            vp = [bm.verts.new(p) for p in pts_pos]
            vn = [bm.verts.new(p) for p in pts_neg]
            bm.faces.new((vp[0], vp[1], vp[2]))
            bm.faces.new((vn[2], vn[1], vn[0]))
            # Seal scalloped trailing edge
            bm.faces.new((vp[1], vn[1], vn[2], vp[2]))


def create_corner_dragon_turret_head(name, bx, by, mat):
    """
    Sculpts a Stone Dragon-Head Gargoyle emerging outward diagonally from corner turret (bx, by)
    at (±4.6, ±4.6), framing the wrought-iron fire brazier without intruding on the chessboard!
    """
    bm = bmesh.new()
    fwd = Vector((bx, by, 0.0)).normalized()
    right = Vector((-fwd.y, fwd.x, 0.0))
    up = Vector((0.0, 0.0, 1.0))
    org = Vector((bx, by, 0.0))

    # 1. Muscular arched scaly neck -> heavy horned skull -> hooked reptilian upper snout
    # Stations: (s_outward, z_height, pitch_deg, rx, rz, brow_flare, jaw_taper)
    upper_stations = [
        (0.24, -0.20,  38.0, 0.28, 0.26, 0.00, 0.00),  # Deep root inside octagonal turret
        (0.42, -0.02,  32.0, 0.25, 0.23, 0.05, 0.00),  # Arched lower neck
        (0.58,  0.16,  18.0, 0.23, 0.21, 0.12, 0.00),  # Upper neck crest
        (0.72,  0.27,   2.0, 0.26, 0.21, 0.32, 0.00),  # Heavy temporal dragon skull
        (0.86,  0.26,  -8.0, 0.21, 0.17, 0.38, 0.08),  # Fierce supraorbital brow ridges
        (1.02,  0.22, -12.0, 0.15, 0.13, 0.08, 0.18),  # Chiselled nasal bridge
        (1.16,  0.19, -10.0, 0.14, 0.12, 0.20, 0.15),  # Flared dragon nostrils
        (1.26,  0.12, -28.0, 0.05, 0.07, 0.00, 0.30),  # Hooked premaxilla beak tip
    ]
    upper_rings = []
    for s, z, pitch, rx, rz, bf, jt in upper_stations:
        pr = math.radians(pitch)
        loc_up = (up * math.cos(pr) - fwd * math.sin(pr)).normalized()
        upper_rings.append(_chiselled_dragon_ring(org + fwd * s + up * z, right, loc_up, rx, rz, bf, jt))
    _loft_rings(bm, upper_rings)

    # 2. Articulated open lower stone jaw with chin spike
    jaw_stations = [
        (0.68,  0.17, -24.0, 0.18, 0.11, 0.0, 0.10),
        (0.84,  0.10, -26.0, 0.14, 0.09, 0.0, 0.18),
        (1.00,  0.03, -26.0, 0.10, 0.07, 0.0, 0.25),
        (1.13, -0.03, -32.0, 0.04, 0.05, 0.0, 0.35),
    ]
    jaw_rings = []
    for s, z, pitch, rx, rz, bf, jt in jaw_stations:
        pr = math.radians(pitch)
        loc_up = (up * math.cos(pr) - fwd * math.sin(pr)).normalized()
        jaw_rings.append(_chiselled_dragon_ring(org + fwd * s + up * z, right, loc_up, rx, rz, bf, jt))
    _loft_rings(bm, jaw_rings)

    # 3. Stone dragon fangs inside the open maw (2 upper canines + 2 lower tusks)
    for side in (-1.0, 1.0):
        u_root = org + fwd * 1.08 + right * (side * 0.09) + up * 0.17
        u_tip = org + fwd * 1.09 + right * (side * 0.08) + up * 0.06
        _loft_rings(bm, [_oct_ring(u_root, right, fwd, 0.026), _oct_ring(u_tip, right, fwd, 0.005)])

        l_root = org + fwd * 1.01 + right * (side * 0.07) + up * 0.03
        l_tip = org + fwd * 1.02 + right * (side * 0.07) + up * 0.12
        _loft_rings(bm, [_oct_ring(l_root, right, fwd, 0.022), _oct_ring(l_tip, right, fwd, 0.005)])

    # 4. Swept-back curved stone dragon horns cradling the brazier bowl!
    for side in (-1.0, 1.0):
        horn_pts = [
            (0.74, side * 0.16, 0.33, 0.072),
            (0.60, side * 0.24, 0.42, 0.058),
            (0.44, side * 0.31, 0.50, 0.044),
            (0.28, side * 0.36, 0.56, 0.028),
            (0.14, side * 0.38, 0.60, 0.010),
        ]
        horn_rings = []
        for idx_h, (hs, hr, hz, hrad) in enumerate(horn_pts):
            pt = org + fwd * hs + right * hr + up * hz
            if idx_h < len(horn_pts) - 1:
                nxt = org + fwd * horn_pts[idx_h + 1][0] + right * horn_pts[idx_h + 1][1] + up * horn_pts[idx_h + 1][2]
                t_dir = (nxt - pt).normalized()
            p_a = t_dir.cross(up).normalized()
            p_b = p_a.cross(t_dir).normalized()
            horn_rings.append(_oct_ring(pt, p_a, p_b, hrad))
        _loft_rings(bm, horn_rings)

        # Flared jugal cheek spike
        c_root = org + fwd * 0.72 + right * (side * 0.22) + up * 0.22
        c_tip = org + fwd * 0.60 + right * (side * 0.36) + up * 0.18
        _loft_rings(bm, [_oct_ring(c_root, fwd, up, 0.048), _oct_ring(c_tip, fwd, up, 0.008)])

    # 5. Dorsal neck spine plates
    for s_sp, z_sp in ((0.44, 0.20), (0.56, 0.34), (0.68, 0.44)):
        _add_dorsal_spine(bm, org + fwd * s_sp + up * z_sp, fwd, right, up, length=0.11, height=0.11, half_w=0.028)

    return finalize_bmesh_object(bm, name, mat, uv_scale=0.35)


def create_perched_pier_dragon_gargoyle(name, cx, cy, z_perch, mat):
    """
    Sculpts a full Perched Stone Dragon Gargoyle at Z = 8.6 on each of the 12 clustered nave piers,
    jutting inward toward the nave with crouched haunches, clawed forelimbs, S-curved neck,
    horned fanged skull, coiled tail, and folded Gothic stone bat-wings!
    """
    bm = bmesh.new()
    inward_x = -1.0 if cx > 0 else 1.0
    gaze_y = -0.15 * (cy / 20.0)
    fwd = Vector((inward_x, gaze_y, 0.0)).normalized()
    right = Vector((-fwd.y, fwd.x, 0.0))
    up = Vector((0.0, 0.0, 1.0))
    org = Vector((cx, cy, z_perch))  # z_perch = 8.6

    # 1. Stepped Gothic Stone Corbel Bracket jutting from the pier (z = 8.05..8.60)
    corbel_tiers = [
        (1.02, 0.62, 0.16, -0.08),  # Top ledge (z = 8.44..8.60, s up to 1.53)
        (0.90, 0.50, 0.18, -0.25),  # Middle moulded console
        (0.76, 0.38, 0.20, -0.44),  # Lower tapered bracket into pier
    ]
    for s_mid, w_cor, h_cor, z_off in corbel_tiers:
        c_pt = org + fwd * s_mid + up * z_off
        dx_c = s_mid * 0.52
        verts_c = [
            bm.verts.new(c_pt + fwd * dx_c + right * (w_cor * 0.5) + up * (h_cor * 0.5)),
            bm.verts.new(c_pt + fwd * dx_c - right * (w_cor * 0.5) + up * (h_cor * 0.5)),
            bm.verts.new(c_pt - fwd * dx_c - right * (w_cor * 0.5) + up * (h_cor * 0.5)),
            bm.verts.new(c_pt - fwd * dx_c + right * (w_cor * 0.5) + up * (h_cor * 0.5)),
            bm.verts.new(c_pt + fwd * (dx_c * 0.82) + right * (w_cor * 0.42) - up * (h_cor * 0.5)),
            bm.verts.new(c_pt + fwd * (dx_c * 0.82) - right * (w_cor * 0.42) - up * (h_cor * 0.5)),
            bm.verts.new(c_pt - fwd * dx_c - right * (w_cor * 0.5) - up * (h_cor * 0.5)),
            bm.verts.new(c_pt - fwd * dx_c + right * (w_cor * 0.5) - up * (h_cor * 0.5)),
        ]
        bm.faces.new((verts_c[0], verts_c[1], verts_c[2], verts_c[3]))
        bm.faces.new((verts_c[7], verts_c[6], verts_c[5], verts_c[4]))
        for k in range(4):
            kn = (k + 1) % 4
            bm.faces.new((verts_c[k], verts_c[4 + k], verts_c[4 + kn], verts_c[kn]))

    # 2. Continuous Crouched Gargoyle Haunches -> Winged Chest -> S-Curved Neck -> Horned Skull -> Snout
    body_stations = [
        (0.72, 0.14,  18.0, 0.30, 0.24, 0.00, 0.00),  # Hunched rear pelvis on corbel
        (0.98, 0.30,  26.0, 0.34, 0.30, 0.05, 0.00),  # Muscular abdomen
        (1.26, 0.52,  32.0, 0.36, 0.32, 0.14, 0.00),  # Broad winged dragon chest
        (1.48, 0.78,  42.0, 0.23, 0.22, 0.06, 0.00),  # Lower S-curved neck
        (1.66, 0.98,  16.0, 0.20, 0.19, 0.10, 0.00),  # Arched upper neck
        (1.82, 1.02, -14.0, 0.24, 0.20, 0.34, 0.00),  # Horned dragon cranium (watching downward!)
        (1.98, 0.95, -24.0, 0.19, 0.16, 0.36, 0.10),  # Heavy brow ridges
        (2.16, 0.84, -26.0, 0.13, 0.12, 0.12, 0.18),  # Snout bridge
        (2.32, 0.74, -30.0, 0.05, 0.07, 0.00, 0.32),  # Hooked dragon beak watching the duel
    ]
    body_rings = []
    for s, z, pitch, rx, rz, bf, jt in body_stations:
        pr = math.radians(pitch)
        loc_up = (up * math.cos(pr) - fwd * math.sin(pr)).normalized()
        body_rings.append(_chiselled_dragon_ring(org + fwd * s + up * z, right, loc_up, rx, rz, bf, jt))
    _loft_rings(bm, body_rings)

    # 3. Open lower dragon jaw
    jaw_stations = [
        (1.80, 0.88, -42.0, 0.16, 0.10, 0.0, 0.12),
        (1.98, 0.74, -44.0, 0.12, 0.08, 0.0, 0.22),
        (2.16, 0.60, -46.0, 0.04, 0.05, 0.0, 0.35),
    ]
    jaw_rings = []
    for s, z, pitch, rx, rz, bf, jt in jaw_stations:
        pr = math.radians(pitch)
        loc_up = (up * math.cos(pr) - fwd * math.sin(pr)).normalized()
        jaw_rings.append(_chiselled_dragon_ring(org + fwd * s + up * z, right, loc_up, rx, rz, bf, jt))
    _loft_rings(bm, jaw_rings)

    # 4. Swept-back stone horns & dorsal spine crest
    for side in (-1.0, 1.0):
        h_pts = [
            (1.82, side * 0.15, 1.10, 0.062),
            (1.62, side * 0.25, 1.24, 0.046),
            (1.38, side * 0.34, 1.36, 0.028),
            (1.16, side * 0.40, 1.44, 0.010),
        ]
        h_rings = [_oct_ring(org + fwd * hs + right * hr + up * hz, right, up, hrad) for (hs, hr, hz, hrad) in h_pts]
        _loft_rings(bm, h_rings)

        # Muscular clawed forelimb gripping the corbel lip
        leg_pts = [
            (1.26, side * 0.28, 0.46, 0.115),  # Shoulder
            (1.20, side * 0.34, 0.22, 0.090),  # Bent elbow
            (1.42, side * 0.26, 0.03, 0.075),  # Forepaw on corbel lip
            (1.54, side * 0.26, -0.04, 0.035), # Stone talons gripping over edge
        ]
        leg_rings = [_oct_ring(org + fwd * ls + right * lr + up * lz, right, fwd, lrad) for (ls, lr, lz, lrad) in leg_pts]
        _loft_rings(bm, leg_rings)

    for s_sp, z_sp in ((0.96, 0.56), (1.18, 0.78), (1.42, 0.98), (1.60, 1.14)):
        _add_dorsal_spine(bm, org + fwd * s_sp + up * z_sp, fwd, right, up, length=0.13, height=0.13, half_w=0.028)

    # 5. Coiled scaly dragon tail wrapping around the corbel base
    tail_pts = [
        (0.72,  0.00, 0.12, 0.13),
        (0.66,  0.26, 0.06, 0.095),
        (0.84,  0.38, 0.03, 0.068),
        (1.12,  0.36, 0.02, 0.042),
        (1.32,  0.28, 0.01, 0.016),
    ]
    tail_rings = [_oct_ring(org + fwd * ts + right * tr + up * tz, right, up, trad) for (ts, tr, tz, trad) in tail_pts]
    _loft_rings(bm, tail_rings)

    # 6. Folded Gothic Stone Bat-Wings swept upward behind the gargoyle's shoulders!
    for side in (-1.0, 1.0):
        p_sh = org + fwd * 1.22 + right * (side * 0.22) + up * 0.56
        p_wr = org + fwd * 0.78 + right * (side * 0.68) + up * 1.48
        p_th = org + fwd * 0.94 + right * (side * 0.74) + up * 1.68
        f_tips = [
            org + fwd * 0.46 + right * (side * 0.86) + up * 1.62,  # Primary upper wingtip
            org + fwd * 0.42 + right * (side * 0.78) + up * 1.10,  # Mid-upper finger tip
            org + fwd * 0.52 + right * (side * 0.64) + up * 0.58,  # Lower finger tip
            org + fwd * 0.80 + right * (side * 0.34) + up * 0.22,  # Inner trailing root
        ]
        _add_bat_wing_geometry(bm, p_sh, p_wr, p_th, f_tips, right * side, thickness=0.055)

    return finalize_bmesh_object(bm, name, mat, uv_scale=0.28)


# ==============================================================================
# PART 0: RUINED DRAGON-SANCTUM ALTAR MESA (NO CHESSBOARD)
# ==============================================================================
SANCTUM_R = 6.3        # Superellipse half-extent on the cardinal axes (m)
SANCTUM_N = 6.0        # Superellipse exponent (rounded-square mesa, covers dragon loci ±4.69m)
SANCTUM_TOP_Z = -0.012 # Top surface just below the dragon crag bases at Z = 0
SANCTUM_UV_SPAN = 6.0  # Summoning-circle texture spans [-6.0, +6.0]m


def _superellipse_radius(theta, R=SANCTUM_R, n=SANCTUM_N):
    c = abs(math.cos(theta)) ** n
    s = abs(math.sin(theta)) ** n
    return R / ((c + s) ** (1.0 / n))


def _make_jagged_rock(name, center, radius, height, mat, rng, subdiv=1):
    """Flat-shaded weathered rock crag: displaced icosphere squashed into a jagged boulder."""
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0)
    for v in bm.verts:
        k = 1.0 + rng.uniform(-0.28, 0.22)
        v.co.x *= radius * k * rng.uniform(0.85, 1.15)
        v.co.y *= radius * k * rng.uniform(0.85, 1.15)
        v.co.z *= height * k
        if v.co.z < -height * 0.35:
            v.co.z = -height * 0.35  # flat-bottomed so it sits on the mesa
    obj = finalize_bmesh_object(bm, name, mat, uv_scale=0.45, location=center,
                                rot=(rng.uniform(-0.12, 0.12), rng.uniform(-0.12, 0.12), rng.uniform(0, math.pi * 2)))
    for poly in obj.data.polygons:
        poly.use_smooth = False
    return obj


def build_dragon_sanctum_altar(mats):
    """
    Builds the ruined-stone Dragon Sanctum mesa:
    - Continuous cracked-flagstone top carrying the Elder Draconic Summoning Circle (board_tiles_*),
      with ZERO square tiles / checkerboard seams.
    - Jagged, irregular rock rim + rough rock skirt.
    - Weathered boulders, fallen Gothic column stubs and rubble around the outer rim
      (always outside the ±4.69m dragon locus envelope).
    """
    import random
    rng = random.Random(1187)
    objs = []
    seg = 144

    rim_top, rim_mid, rim_bot = [], [], []
    for i in range(seg):
        th = (i / seg) * math.pi * 2.0
        r = _superellipse_radius(th)
        jag = 1.0 + 0.022 * math.sin(th * 17.0) + 0.015 * math.sin(th * 41.0 + 1.3) + rng.uniform(-0.012, 0.012)
        rt = r * jag
        rim_top.append((rt * math.cos(th), rt * math.sin(th), SANCTUM_TOP_Z))
        rm = rt + 0.10 + rng.uniform(-0.04, 0.06)
        rim_mid.append((rm * math.cos(th), rm * math.sin(th), -0.16 + rng.uniform(-0.04, 0.03)))
        rb = rt * (0.80 + rng.uniform(-0.04, 0.04))
        rim_bot.append((rb * math.cos(th), rb * math.sin(th), -0.78 + rng.uniform(-0.10, 0.08)))

    # --- Top cap (summoning-circle stone, planar UVs) ---
    bm = bmesh.new()
    c_v = bm.verts.new((0.0, 0.0, SANCTUM_TOP_Z))
    ring = [bm.verts.new(p) for p in rim_top]
    # Two interior rings so the large cap shades & receives shadows smoothly
    inner_rings = []
    for frac in (0.36, 0.70):
        inner_rings.append([bm.verts.new((p[0] * frac, p[1] * frac, SANCTUM_TOP_Z)) for p in rim_top])
    for i in range(seg):
        j = (i + 1) % seg
        bm.faces.new((c_v, inner_rings[0][i], inner_rings[0][j]))
        bm.faces.new((inner_rings[0][i], inner_rings[1][i], inner_rings[1][j], inner_rings[0][j]))
        bm.faces.new((inner_rings[1][i], ring[i], ring[j], inner_rings[1][j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for f in bm.faces:
        if f.normal.z < 0:
            f.normal_flip()
    mesh = bpy.data.meshes.new("Sanctum_Summoning_Floor")
    bm.to_mesh(mesh)
    bm.free()
    cap = bpy.data.objects.new("Sanctum_Summoning_Floor", mesh)
    bpy.context.collection.objects.link(cap)
    cap.data.materials.append(mats['tiles'])
    mesh.uv_layers.new(name="UVMap")
    uv_layer = mesh.uv_layers.active.data
    span = SANCTUM_UV_SPAN
    for poly in mesh.polygons:
        for loop_idx in poly.loop_indices:
            co = mesh.vertices[mesh.loops[loop_idx].vertex_index].co
            # Matches export_yup=True + cathedral scene.rotation.y = PI in Three.js
            uv_layer[loop_idx].uv = ((-co.x + span) / (2.0 * span), (span - co.y) / (2.0 * span))
    objs.append(cap)

    # --- Jagged rock skirt (rough outer cliff face of the mesa) ---
    bm = bmesh.new()
    vt = [bm.verts.new(p) for p in rim_top]
    vm = [bm.verts.new(p) for p in rim_mid]
    vb = [bm.verts.new(p) for p in rim_bot]
    for i in range(seg):
        j = (i + 1) % seg
        bm.faces.new((vt[i], vm[i], vm[j], vt[j]))
        bm.faces.new((vm[i], vb[i], vb[j], vm[j]))
    bm.faces.new(list(reversed(vb)))
    skirt = finalize_bmesh_object(bm, "Sanctum_Rock_Skirt", mats['stone'], uv_scale=0.32)
    for poly in skirt.data.polygons:
        poly.use_smooth = False
    objs.append(skirt)

    # --- Weathered boulders & rubble on the rim (outside the ±4.69m dragon envelope) ---
    n_rocks = 40
    for k in range(n_rocks):
        th = (k / n_rocks) * math.pi * 2.0 + rng.uniform(-0.03, 0.03)
        # Keep diagonals free for the 4 corner dragon-head braziers
        diag = abs(((th % (math.pi / 2.0)) - math.pi / 4.0))
        if diag < math.radians(13.0):
            continue
        r_edge = _superellipse_radius(th)
        r = r_edge - rng.uniform(0.30, 0.55)
        x, y = r * math.cos(th), r * math.sin(th)
        if max(abs(x), abs(y)) < 5.05:
            continue
        rad = rng.uniform(0.22, 0.44)
        hgt = rng.uniform(0.18, 0.52)
        mat = mats['frame'] if k % 3 == 0 else mats['stone']
        objs.append(_make_jagged_rock(f"Sanctum_Rim_Crag_{k}", (x, y, SANCTUM_TOP_Z + hgt * 0.30), rad, hgt, mat, rng))
        # Small rubble chips beside larger crags
        if k % 2 == 0:
            ox, oy = x + rng.uniform(-0.35, 0.35), y + rng.uniform(-0.35, 0.35)
            if max(abs(ox), abs(oy)) > 5.0:
                objs.append(_make_jagged_rock(f"Sanctum_Rubble_{k}", (ox, oy, SANCTUM_TOP_Z + 0.03), rng.uniform(0.08, 0.14),
                                              rng.uniform(0.06, 0.11), mats['stone'], rng, subdiv=1))

    # --- Fallen / broken Gothic column stubs on the east & west flanks (never blocking N/S cameras) ---
    stubs = [(-5.75, -2.35, 1.55), (-5.75, 2.35, 0.95), (5.75, -2.35, 1.05), (5.75, 2.35, 1.85)]
    for s_idx, (sx, sy, sh) in enumerate(stubs):
        objs.append(add_cylinder(f"Sanctum_Column_Base_{s_idx}", (sx, sy, SANCTUM_TOP_Z + 0.09), 0.40, 0.18, 8, mats['frame'], uv_scale=0.35))
        objs.append(add_cylinder(f"Sanctum_Column_Shaft_{s_idx}", (sx, sy, SANCTUM_TOP_Z + 0.18 + sh * 0.5), 0.28, sh, 12, mats['stone'], uv_scale=0.30))
        # Jagged broken-off top
        objs.append(_make_jagged_rock(f"Sanctum_Column_Break_{s_idx}", (sx, sy, SANCTUM_TOP_Z + 0.18 + sh), 0.30, 0.16, mats['stone'], rng))
    # One toppled drum lying on the rim
    objs.append(add_cylinder("Sanctum_Fallen_Drum", (5.55, 0.0, SANCTUM_TOP_Z + 0.26), 0.26, 0.85, 12, mats['stone'], uv_scale=0.30,
                             rot=(math.pi / 2.0, 0.0, 0.35)))

    return objs


# ==============================================================================
# PART 1: DRAGON SANCTUM PEDESTAL & 4 CORNER DRAGON BRAZIERS
# ==============================================================================
def build_chess_table_and_pedestal(mats):
    print("Building Dragon-Carved Chess Altar Table, Octagonal Dais, Ribbed Buttress Pedestal & 4 Dragon-Head Braziers...")
    objs = []

    # 1. Stepped Octagonal Gothic Stone Dais (Z = -3.80 to -3.05)
    # Rotated by pi/8 so the 8 flat faces align cleanly with N, S, E, W and the 4 diagonals!
    oct_rot = (0.0, 0.0, math.pi / 8.0)
    dais_steps = [
        ("Dais_Oct_Step_1", -3.675, 0.25, 6.25),
        ("Dais_Oct_Step_2", -3.425, 0.25, 5.35),
        ("Dais_Oct_Step_3", -3.175, 0.25, 4.45),
    ]
    for s_name, z_c, h, rad in dais_steps:
        objs.append(add_cylinder(s_name, (0, 0, z_c), rad, h, 8, mats['floor'], uv_scale=0.18, rot=oct_rot))
        # Carved dark volcanic dragon-stone nosing trim molding
        objs.append(add_cylinder(s_name + "_Nosing", (0, 0, z_c + h * 0.40), rad + 0.08, 0.06, 8, mats['frame'], uv_scale=0.25, rot=oct_rot))

    # 8 Low Gothic Stone Plinth Bosses at the outer octagonal corners of Step 1
    for k in range(8):
        ang = (k + 0.5) * (math.pi / 4.0)
        px = 5.95 * math.cos(ang)
        py = 5.95 * math.sin(ang)
        objs.append(add_cylinder(f"Dais_Corner_Boss_{k}", (px, py, -3.48), 0.30, 0.16, 8, mats['frame'], uv_scale=0.35))

    # 2. Heavy Ribbed Octagonal Dragon-Pedestal with 4 Flying Buttress Arches (Z = -3.05 to -0.35)
    objs.append(add_cylinder("Pedestal_Base_Plinth", (0, 0, -2.85), 3.45, 0.40, 8, mats['stone'], uv_scale=0.25, rot=oct_rot))
    objs.append(add_cylinder("Pedestal_Plinth_Molding", (0, 0, -2.60), 3.10, 0.14, 8, mats['frame'], uv_scale=0.28, rot=oct_rot))
    objs.append(add_cylinder("Pedestal_Core_Column", (0, 0, -1.62), 2.12, 2.00, 8, mats['stone'], uv_scale=0.25, rot=oct_rot))
    objs.append(add_cylinder("Pedestal_Shaft_Collar", (0, 0, -1.62), 2.34, 0.22, 8, mats['frame'], uv_scale=0.30, rot=oct_rot))
    objs.append(add_cone("Pedestal_Capital_Flare", (0, 0, -0.52), 2.28, 3.65, 0.34, 8, mats['frame'], uv_scale=0.25, rot=oct_rot))

    # 8 Engaged Rib Colonnettes around the octagonal central dragon-pillar
    for k in range(8):
        ang = (k + 0.5) * (math.pi / 4.0)
        objs.append(add_cylinder(f"Pedestal_RibShaft_{k}", (2.06 * math.cos(ang), 2.06 * math.sin(ang), -1.62), 0.20, 1.96, 8, mats['frame'], uv_scale=0.3))

    # 4 Cardinal Pointed Blind-Arcade Reliefs on N/S/E/W faces of the pedestal
    for c_idx, (nx, ny) in enumerate([(0, -1), (0, 1), (-1, 0), (1, 0)]):
        perp_x, perp_y = -ny, nx
        objs.append(create_pointed_arch_rib(
            f"Pedestal_BlindArch_{c_idx}",
            (nx * 2.02 - perp_x * 0.68, ny * 2.02 - perp_y * 0.68),
            (nx * 2.02 + perp_x * 0.68, ny * 2.02 + perp_y * 0.68),
            z_base=-2.45, z_peak=-0.82,
            thickness=0.18, depth=0.18,
            mat=mats['frame'], segments=10
        ))

    # 4 Diagonal Flying Buttress Piers & Pointed Gothic Arches bracing the corners
    for idx, (dx, dy) in enumerate([(-1, -1), (1, -1), (1, 1), (-1, 1)]):
        angle = math.atan2(dy, dx)
        # Outer Gothic buttress pier standing on Dais Step 3
        bx_p, by_p = dx * 2.55, dy * 2.55
        objs.append(add_box(f"Pedestal_Buttress_Pier_{idx}", (bx_p, by_p, -1.85), (0.85, 0.62, 2.35), mats['stone'], uv_scale=0.25, bevel_width=0.03, rot=(0, 0, angle)))
        objs.append(add_cone(f"Pedestal_Buttress_Pinnacle_{idx}", (dx * 2.72, dy * 2.72, -0.52), 0.34, 0.06, 0.34, 6, mats['frame'], uv_scale=0.3))
        # Flying buttress pointed arch connecting central dragon-column to outer buttress & corner turret
        objs.append(create_pointed_arch_rib(
            f"Pedestal_FlyingArch_{idx}",
            (dx * 1.25, dy * 1.25),
            (dx * 3.15, dy * 3.15),
            z_base=-2.50,
            z_peak=-0.44,
            thickness=0.40,
            depth=0.30,
            mat=mats['frame'],
            segments=14,
        ))

    # 3. NON-CHECKERBOARD Ruined Dragon-Sanctum Altar Mesa (replaces the square chessboard table entirely)
    objs.extend(build_dragon_sanctum_altar(mats))

    # 5. Four Sculpted Stone Dragon-Head Gargoyle Turrets & Glowing Fire Braziers at (±5.35, ±5.35)
    for idx, (bx, by) in enumerate([(-5.35, -5.35), (5.35, -5.35), (5.35, 5.35), (-5.35, 5.35)]):
        # Natural rock crag column carrying each brazier turret down onto the octagonal dais
        objs.append(add_cone(f"Corner_Crag_Column_{idx}", (bx, by, -2.08), 0.95, 0.66, 3.44, 7, mats['stone'], uv_scale=0.28))
        # Octagonal carved dragon-stone turret base & cornice crown (Z = -0.42 to +0.44)
        objs.append(add_cylinder(f"Corner_Turret_Plinth_{idx}", (bx, by, -0.35), 0.68, 0.16, 8, mats['stone'], uv_scale=0.30, rot=oct_rot))
        objs.append(add_cylinder(f"Corner_Turret_Base_{idx}", (bx, by, 0.03), 0.58, 0.62, 8, mats['frame'], uv_scale=0.30, rot=oct_rot))
        objs.append(add_cylinder(f"Corner_Turret_Cap_{idx}", (bx, by, 0.39), 0.68, 0.11, 8, mats['stone'], uv_scale=0.30, rot=oct_rot))
        objs.append(add_cylinder(f"Corner_Turret_Ring_{idx}", (bx, by, 0.455), 0.62, 0.03, 8, mats['gold'], uv_scale=0.40, rot=oct_rot))

        # Sculpted Horned Stone Dragon-Head Gargoyle in dark carved volcanic dragon-stone facing outward diagonally!
        objs.append(create_corner_dragon_turret_head(f"Corner_Dragon_Head_{idx}", bx, by, mats['frame']))

        # Wrought-iron clawed tripod struts + fire-basket bowl (Z = +0.46 to +0.78)
        for leg_i in range(4):
            la = (leg_i + 0.5) * (math.pi * 0.5)
            objs.append(add_box(
                f"Corner_Brazier_Leg_{idx}_{leg_i}",
                (bx + 0.36 * math.cos(la), by + 0.36 * math.sin(la), 0.53),
                (0.08, 0.06, 0.18),
                mats['iron'],
                uv_scale=0.5,
                rot=(0, -0.25 * math.cos(la), la),
            ))
        objs.append(add_cone(f"Corner_Brazier_Bowl_{idx}", (bx, by, 0.63), 0.32, 0.58, 0.32, 12, mats['iron'], uv_scale=0.4))
        objs.append(add_cylinder(f"Corner_Brazier_Rim_{idx}", (bx, by, 0.78), 0.60, 0.04, 12, mats['iron'], uv_scale=0.4))

        # Glowing coal mound & flickering ember tongues around Z = 0.80..0.95
        objs.append(add_cone(f"Corner_Brazier_Coals_{idx}", (bx, by, 0.81), 0.48, 0.20, 0.16, 10, mats['ember'], uv_scale=0.5))
        objs.append(add_cone(f"Corner_Brazier_FlameMain_{idx}", (bx, by, 0.88), 0.24, 0.03, 0.16, 8, mats['ember'], uv_scale=0.5))

    return objs


# ==============================================================================
# PART 2: NORTH DRAGON-SANCTUM HIGH ALTAR, CHOIR PEWS & POINTED LANCET GLASS
# ==============================================================================
def create_pointed_lancet_glass(name, wx, by, width, z_bot, z_spring, z_peak, mat):
    """
    Creates a true Gothic pointed-arch stained glass lancet panel at (wx, by)
    with distortion-free UVs: isotropic circular rose/medallion UVs in the pointed arch head,
    and clean 1:1 jewel-toned lancet medallions in the vertical lights (zero diagonal stripe distortion!).
    """
    bm = bmesh.new()
    half_w = width * 0.5
    half_th = 0.08

    # Build closed 2D profile in (y_local, z_world)
    prof_yz = [(-half_w, z_bot), (half_w, z_bot), (half_w, z_spring)]
    arch_segs = 14
    for i in range(1, arch_segs):
        t = i / arch_segs
        if t <= 0.5:
            u = t * 2.0
            yl = half_w * (1.0 - u)
        else:
            u = (1.0 - t) * 2.0
            yl = -half_w * (1.0 - u)
        zl = z_spring + (z_peak - z_spring) * math.sin(u * math.pi * 0.5)
        prof_yz.append((yl, zl))
    prof_yz.append((-half_w, z_spring))

    v_front = [bm.verts.new((wx - half_th, by + yl, zl)) for (yl, zl) in prof_yz]
    v_back = [bm.verts.new((wx + half_th, by + yl, zl)) for (yl, zl) in prof_yz]

    bm.faces.new(v_front)
    bm.faces.new(v_back[::-1])
    n = len(prof_yz)
    for k in range(n):
        kn = (k + 1) % n
        bm.faces.new((v_front[k], v_back[k], v_back[kn], v_front[kn]))

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)

    mesh.uv_layers.new(name="UVMap")
    uv_layer = mesh.uv_layers.active.data
    # Map UVs isotropically centered on the upper oculus (by, z_center=10.3) with radius 2.45m!
    # Because stained_glass_*.png is tileable/radial, isotropic (1:1) scaling keeps every medallion circular!
    for poly in mesh.polygons:
        for loop_idx in poly.loop_indices:
            co = mesh.vertices[mesh.loops[loop_idx].vertex_index].co
            u = ((co.y - by) / 2.45) * 0.46 + 0.5
            vv = ((co.z - 10.2) / 2.45) * 0.46 + 0.5
            uv_layer[loop_idx].uv = (u, vv)

    return obj


def build_gothic_choir_pew(objs, tag, cx, cy, z_floor, length_y, face_dir_x, mats):
    """Builds a carved Gothic choir/aisle pew with stone plinths, oak seat, backrest, kneeler, and pointed poppyhead finials."""
    # Stone floor plinth sleepers
    for y_off in (-length_y * 0.44, 0.0, length_y * 0.44):
        objs.append(add_box(f"{tag}_Plinth_{y_off:.1f}", (cx, cy + y_off, z_floor + 0.06), (0.72, 0.16, 0.12), mats['stone'], uv_scale=0.35))

    # Oak plank seat (height 0.48m above floor)
    objs.append(add_box(f"{tag}_Seat", (cx + face_dir_x * 0.06, cy, z_floor + 0.48), (0.54, length_y, 0.07), mats['wood'], uv_scale=0.35, bevel_width=0.01))
    # Moulded Gothic backrest + top rail
    bx_back = cx - face_dir_x * 0.20
    objs.append(add_box(f"{tag}_Back", (bx_back, cy, z_floor + 0.78), (0.07, length_y, 0.62), mats['wood'], uv_scale=0.35))
    objs.append(add_box(f"{tag}_TopRail", (bx_back, cy, z_floor + 1.11), (0.11, length_y + 0.06, 0.07), mats['frame'], uv_scale=0.35))
    # Low prayer kneeler step in front
    objs.append(add_box(f"{tag}_Kneeler", (cx + face_dir_x * 0.34, cy, z_floor + 0.16), (0.20, length_y - 0.12, 0.08), mats['wood'], uv_scale=0.4))

    # Carved Gothic bench-end standards with pointed gables & trefoil poppyhead finials
    for s_idx, y_end in enumerate((-length_y * 0.5, length_y * 0.5)):
        objs.append(add_box(f"{tag}_End_{s_idx}", (cx, cy + y_end, z_floor + 0.66), (0.66, 0.09, 1.12), mats['wood'], uv_scale=0.35, bevel_width=0.012))
        objs.append(add_cone(f"{tag}_Gable_{s_idx}", (cx, cy + y_end, z_floor + 1.32), 0.32, 0.04, 0.24, 4, mats['frame'], uv_scale=0.4, rot=(0, 0, math.pi * 0.25)))
        objs.append(add_cylinder(f"{tag}_Poppyhead_{s_idx}", (cx, cy + y_end, z_floor + 1.48), 0.09, 0.14, 6, mats['gold'], uv_scale=0.5))


def build_north_dragon_high_altar(objs, mats):
    """
    Builds the Gothic High Altar & Pointed Reliquary Arch with Carved Stone Dragon Wings
    at Y = -20.5, Z = -3.80..+1.95 beneath the Grand North Rose Window.
    """
    print("Building North Dragon-Sanctum High Altar & Winged Reliquary Arch...")
    # 1. 3-Step Sanctuary Platform (Z = -3.80 to -3.08, centered around Y = -20.5)
    altar_steps = [
        ("Sanctuary_Step_1", -20.4, -3.68, 9.2, 3.8, 0.24),
        ("Sanctuary_Step_2", -20.6, -3.44, 7.8, 3.1, 0.24),
        ("Sanctuary_Step_3", -20.8, -3.20, 6.4, 2.4, 0.24),
    ]
    for s_name, sy, sz, sw, sd, sh in altar_steps:
        objs.append(add_box(s_name, (0.0, sy, sz), (sw, sd, sh), mats['floor'], uv_scale=0.20, bevel_width=0.03))
        objs.append(add_box(s_name + "_Trim", (0.0, sy, sz + sh * 0.40), (sw + 0.10, sd + 0.10, 0.05), mats['frame'], uv_scale=0.28))

    # 2. Carved Gothic Stone High Altar Table (Z = -3.08 to -1.92, Y = -20.55)
    objs.append(add_box("HighAltar_Plinth", (0.0, -20.55, -2.98), (4.50, 1.48, 0.20), mats['frame'], uv_scale=0.28, bevel_width=0.02))
    objs.append(add_box("HighAltar_Body", (0.0, -20.55, -2.45), (4.20, 1.26, 0.88), mats['stone'], uv_scale=0.25))
    objs.append(add_box("HighAltar_Mensa", (0.0, -20.55, -1.96), (4.62, 1.56, 0.14), mats['frame'], uv_scale=0.25, bevel_width=0.02))
    objs.append(add_box("HighAltar_BronzeTrim", (0.0, -20.55, -2.04), (4.54, 1.50, 0.04), mats['gold'], uv_scale=0.4))

    # 5 Pointed Trefoil Blind-Arcade Niches across the front antipendium of the High Altar
    for n_idx, ax in enumerate([-1.56, -0.78, 0.0, 0.78, 1.56]):
        objs.append(add_cylinder(f"HighAltar_Shaft_{n_idx}", (ax - 0.36, -19.90, -2.45), 0.06, 0.84, 8, mats['frame'], uv_scale=0.4))
        objs.append(create_pointed_arch_rib(
            f"HighAltar_NicheArch_{n_idx}",
            (ax - 0.34, -19.90), (ax + 0.34, -19.90),
            z_base=-2.32, z_peak=-2.06,
            thickness=0.08, depth=0.08,
            mat=mats['gold'] if n_idx == 2 else mats['frame'],
            segments=8,
        ))
    objs.append(add_cylinder("HighAltar_Shaft_End", (1.92, -19.90, -2.45), 0.06, 0.84, 8, mats['frame'], uv_scale=0.4))

    # 3. Pointed Gothic Reliquary Reredos Arch (Y = -21.25, rising from Z = -1.90 to +1.85)
    for rx_s in (-1.55, -1.28, 1.28, 1.55):
        objs.append(add_cylinder(f"Reliquary_Pier_{rx_s}", (rx_s, -21.25, -0.85), 0.14, 2.20, 8, mats['frame'], uv_scale=0.3))
        objs.append(add_cone(f"Reliquary_Pinnacle_{rx_s}", (rx_s, -21.25, 0.55), 0.18, 0.03, 0.65, 6, mats['stone'], uv_scale=0.35))

    objs.append(create_pointed_arch_rib(
        "Reliquary_Main_Arch",
        (-1.42, -21.25), (1.42, -21.25),
        z_base=0.15, z_peak=1.75,
        thickness=0.34, depth=0.32,
        mat=mats['frame'], segments=16,
    ))
    objs.append(create_pointed_arch_rib(
        "Reliquary_Inner_Arch",
        (-1.12, -21.20), (1.12, -21.20),
        z_base=0.10, z_peak=1.38,
        thickness=0.18, depth=0.18,
        mat=mats['gold'], segments=14,
    ))
    # Recessed stained-glass & glowing draconic reliquary monstrance inside the arch
    objs.append(add_box("Reliquary_BackPanel", (0.0, -21.35, -0.45), (2.40, 0.16, 2.60), mats['stone'], uv_scale=0.25))
    objs.append(add_cylinder("Reliquary_Pedestal", (0.0, -20.85, -1.55), 0.28, 0.68, 8, mats['gold'], uv_scale=0.4))
    objs.append(add_cylinder("Reliquary_HaloRing", (0.0, -20.85, -0.82), 0.46, 0.10, 16, mats['gold'], uv_scale=0.4, rot=(math.pi * 0.5, 0, 0)))
    objs.append(add_cone("Reliquary_SacredFlame", (0.0, -20.85, -0.82), 0.24, 0.04, 0.42, 10, mats['ember'], uv_scale=0.5))

    # 4. Sculpted Stone Dragon Wings & Elder-Wyrm Crest flanking the High Altar Reliquary!
    bm_wings = bmesh.new()
    # Central stone dragon bust at top of reliquary arch (0, -21.10, 1.55) facing South (+Y) into the nave
    fwd_altar = Vector((0.0, 1.0, 0.0))
    right_altar = Vector((-1.0, 0.0, 0.0))
    up_vec = Vector((0.0, 0.0, 1.0))
    crest_org = Vector((0.0, -21.20, 1.48))
    crest_stations = [
        (0.00, 0.00,  15.0, 0.26, 0.24, 0.10, 0.00),
        (0.24, 0.14,   0.0, 0.24, 0.20, 0.34, 0.00),
        (0.46, 0.08, -18.0, 0.16, 0.14, 0.22, 0.15),
        (0.66, -0.02, -26.0, 0.06, 0.08, 0.00, 0.30),
    ]
    crest_rings = []
    for s, z, pitch, rx, rz, bf, jt in crest_stations:
        pr = math.radians(pitch)
        loc_up = (up_vec * math.cos(pr) - fwd_altar * math.sin(pr)).normalized()
        crest_rings.append(_chiselled_dragon_ring(crest_org + fwd_altar * s + up_vec * z, right_altar, loc_up, rx, rz, bf, jt))
    _loft_rings(bm_wings, crest_rings)

    for side in (-1.0, 1.0):
        # Sweeping carved stone Dragon Wings (total span ~5.8m, Z in [-1.45, +1.72])
        p_sh = Vector((side * 1.35, -21.22, -0.55))
        p_wr = Vector((side * 2.35, -21.05,  1.28))
        p_th = Vector((side * 2.48, -20.92,  1.68))
        f_tips = [
            Vector((side * 3.05, -21.15,  1.52)),
            Vector((side * 2.88, -21.18,  0.62)),
            Vector((side * 2.45, -21.20, -0.35)),
            Vector((side * 1.55, -21.22, -1.35)),
        ]
        _add_bat_wing_geometry(bm_wings, p_sh, p_wr, p_th, f_tips, Vector((0.0, 1.0 * side, 0.0)), thickness=0.09)

    objs.append(finalize_bmesh_object(bm_wings, "HighAltar_Stone_Dragon_Wings", mats['frame'], uv_scale=0.25))

    # 5. Flanking Sanctuary Brazier Candlesticks on Step 2
    for sx in (-2.95, 2.95):
        objs.append(add_cylinder(f"Sanctuary_Candelabra_Base_{sx}", (sx, -19.85, -3.15), 0.36, 0.34, 8, mats['frame'], uv_scale=0.35))
        objs.append(add_cylinder(f"Sanctuary_Candelabra_Stem_{sx}", (sx, -19.85, -2.35), 0.10, 1.30, 8, mats['iron'], uv_scale=0.4))
        objs.append(add_cone(f"Sanctuary_Candelabra_Bowl_{sx}", (sx, -19.85, -1.60), 0.16, 0.38, 0.24, 10, mats['gold'], uv_scale=0.4))
        objs.append(add_cone(f"Sanctuary_Candelabra_Flame_{sx}", (sx, -19.85, -1.38), 0.24, 0.03, 0.28, 8, mats['ember'], uv_scale=0.5))


# ==============================================================================
# PART 3: HIGH GOTHIC CATHEDRAL HALL, GARGOYLE PIERS, TRIFORIUM, VAULTS & ROSE WINDOW
# ==============================================================================
def build_cathedral_hall(mats):
    print("Building High Gothic Dragon-Sanctum Hall, Gargoyle Piers, Triforium, Vaults, Pews & Chandeliers...")
    objs = []

    # 1. Cathedral Floor (EXACT ALIGNMENT: top at Z = -3.80, X in [-16, +16], Y in [-24, +24])
    objs.append(add_box("Cathedral_Floor", (0, 0, -3.95), (32.0, 48.0, 0.30), mats['floor'], uv_scale=0.125))

    # 2. 12 Clustered Gothic Nave Piers at X = ±9.5, Y = [-20, -12, -4, 4, 12, 20]
    col_ys = [-20.0, -12.0, -4.0, 4.0, 12.0, 20.0]
    col_xs = [-9.5, 9.5]
    col_height = 13.8  # Z = -3.8 to +10.0 (center Z = +3.1)
    col_z_center = 3.1
    oct_rot = (0.0, 0.0, math.pi / 8.0)

    for ix, cx in enumerate(col_xs):
        inward = -1.0 if cx > 0 else 1.0
        for iy, cy in enumerate(col_ys):
            tag = f"Pier_{ix}_{iy}"
            # Stepped octagonal plinths (Z = -3.80 to -2.55)
            objs.append(add_cylinder(f"{tag}_Plinth1", (cx, cy, -3.50), 1.48, 0.60, 8, mats['stone'], uv_scale=0.25, rot=oct_rot))
            objs.append(add_cylinder(f"{tag}_Plinth2", (cx, cy, -2.92), 1.22, 0.56, 8, mats['frame'], uv_scale=0.25, rot=oct_rot))
            # Central clustered pier core
            objs.append(add_cylinder(f"{tag}_Core", (cx, cy, col_z_center), 0.84, col_height, 12, mats['stone'], uv_scale=0.20))

            # 4 Major Cardinal Bundled Shafts + 4 Minor Diagonal Colonnettes
            for c_idx, (ox, oy) in enumerate([(0.76, 0), (-0.76, 0), (0, 0.76), (0, -0.76)]):
                objs.append(add_cylinder(f"{tag}_MajorShaft_{c_idx}", (cx + ox, cy + oy, col_z_center), 0.27, col_height, 10, mats['stone'], uv_scale=0.25))
            for d_idx, (ox, oy) in enumerate([(0.56, 0.56), (-0.56, 0.56), (0.56, -0.56), (-0.56, -0.56)]):
                objs.append(add_cylinder(f"{tag}_MinorShaft_{d_idx}", (cx + ox, cy + oy, col_z_center), 0.16, col_height, 8, mats['frame'], uv_scale=0.28))

            # Shaft-ring annulet bands (Z = +1.8 and Z = +5.65 supporting lower nave arcade)
            objs.append(add_cylinder(f"{tag}_BandLower", (cx, cy, 1.80), 1.14, 0.24, 8, mats['frame'], uv_scale=0.30, rot=oct_rot))
            objs.append(add_cylinder(f"{tag}_ArcadeImpost", (cx, cy, 5.65), 1.24, 0.30, 8, mats['frame'], uv_scale=0.28, rot=oct_rot))

            # Foliate Flared Gothic Capital & Moulded Abacus (Z = +9.45 to +10.25)
            objs.append(add_cone(f"{tag}_CapitalBell", (cx, cy, 9.75), 0.96, 1.48, 0.68, 8, mats['frame'], uv_scale=0.25, rot=oct_rot))
            objs.append(add_box(f"{tag}_Abacus", (cx, cy, 10.16), (2.45, 2.45, 0.24), mats['stone'], uv_scale=0.25, bevel_width=0.02))

            # Upper Vaulting Responder Shafts rising through Triforium level (Z = +10.25 to +12.25)
            objs.append(add_cylinder(f"{tag}_VaultResponder", (cx + inward * 0.55, cy, 11.25), 0.32, 2.0, 8, mats['frame'], uv_scale=0.28))

            # Wrought-Iron Torch Sconce on inner nave face at Z = +4.50
            sx = cx + inward * 1.10
            objs.append(add_box(f"{tag}_Sconce_Plate", (cx + inward * 0.96, cy, 4.42), (0.10, 0.22, 0.62), mats['iron'], uv_scale=0.5))
            objs.append(add_box(f"{tag}_Sconce_Bracket", (sx, cy, 4.35), (0.44, 0.12, 0.16), mats['iron'], uv_scale=0.5))
            objs.append(add_cone(f"{tag}_Torch_Cup", (sx + inward * 0.18, cy, 4.65), 0.08, 0.22, 0.45, 8, mats['iron'], uv_scale=0.5))
            objs.append(add_cone(f"{tag}_Torch_Flame", (sx + inward * 0.18, cy, 5.02), 0.18, 0.03, 0.38, 8, mats['ember'], uv_scale=0.5))

            # Perched Sculpted Stone Dragon Gargoyle at Z = +8.60 in dark volcanic dragon-stone watching over the duel!
            objs.append(create_perched_pier_dragon_gargoyle(f"{tag}_Dragon_Gargoyle", cx, cy, 8.60, mats['frame']))

    # 3. Three-Story High Gothic Nave Elevation:
    #    - Lower Pointed Main Arcade (Z = 5.75 to 9.15)
    #    - Pointed Triforium Gallery Arcade (Z = 9.35 to 12.15)
    #    - Upper Clerestory Formeret Arches (Z = 12.20 to 16.60)
    all_nave_ys = [-24.0] + col_ys + [24.0]
    for s_idx, cx in enumerate(col_xs):
        inward = -1.0 if cx > 0 else 1.0
        # Continuous Horizontal Triforium String-Course Moldings & Open Gallery Walkway
        objs.append(add_box(f"Triforium_LowerString_{s_idx}", (cx, 0.0, 9.35), (0.95, 48.0, 0.24), mats['frame'], uv_scale=0.22))
        objs.append(add_box(f"Triforium_UpperString_{s_idx}", (cx, 0.0, 12.15), (0.95, 48.0, 0.26), mats['frame'], uv_scale=0.22))
        objs.append(add_box(f"Triforium_Walkway_{s_idx}", (cx - inward * 0.65, 0.0, 9.30), (1.35, 48.0, 0.18), mats['stone'], uv_scale=0.20))

        # Main 5 Nave Bays + 2 End Bays
        for i in range(len(all_nave_ys) - 1):
            yA, yB = all_nave_ys[i], all_nave_ys[i + 1]
            span = yB - yA
            # Story 1: Lower Main Nave Pointed Arcade Arch
            objs.append(create_pointed_arch_rib(
                f"Nave_MainArcade_{s_idx}_{i}",
                (cx, yA + 0.55), (cx, yB - 0.55),
                z_base=5.75, z_peak=9.12,
                thickness=0.68, depth=0.52,
                mat=mats['stone'], segments=14,
            ))
            objs.append(create_pointed_arch_rib(
                f"Nave_SubArcade_{s_idx}_{i}",
                (cx, yA + 0.72), (cx, yB - 0.72),
                z_base=5.70, z_peak=8.82,
                thickness=0.40, depth=0.34,
                mat=mats['frame'], segments=12,
            ))

            # Story 2: Pointed Triforium Arcade Gallery (4 pointed archlets in 8m bays, 2 in 4m end bays)
            n_trif = 4 if span > 6.0 else 2
            y_start = yA + 0.85
            y_end = yB - 0.85
            sub_span = (y_end - y_start) / n_trif
            for t_i in range(n_trif + 1):
                ty = y_start + t_i * sub_span
                # Slender twin Triforium colonnettes
                for x_off in (-0.18, 0.18):
                    objs.append(add_cylinder(f"Trif_Shaft_{s_idx}_{i}_{t_i}_{x_off}", (cx + x_off, ty, 10.42), 0.09, 1.92, 8, mats['frame'], uv_scale=0.35))
                objs.append(add_box(f"Trif_Cap_{s_idx}_{i}_{t_i}", (cx, ty, 11.42), (0.58, 0.28, 0.14), mats['stone'], uv_scale=0.35))
                if t_i < n_trif:
                    ty_next = y_start + (t_i + 1) * sub_span
                    objs.append(create_pointed_arch_rib(
                        f"Trif_Archlet_{s_idx}_{i}_{t_i}",
                        (cx, ty), (cx, ty_next),
                        z_base=11.45, z_peak=12.04,
                        thickness=0.42, depth=0.20,
                        mat=mats['frame'], segments=8,
                    ))

            # Story 3: Upper Clerestory Formeret Arch
            objs.append(create_pointed_arch_rib(
                f"Clerestory_Arch_{s_idx}_{i}",
                (cx, yA), (cx, yB),
                z_base=12.22, z_peak=16.50,
                thickness=0.55, depth=0.46,
                mat=mats['stone'], segments=14,
            ))

    # 4. Quadripartite Ribbed Groin Vaults across Nave & Side Aisles (Z = +10.2 up to +18.6)
    vault_ys = [-23.8] + col_ys + [23.8]
    for iy, cy in enumerate(vault_ys):
        # Nave transverse pointed arch
        objs.append(create_pointed_arch_rib(
            f"Vault_Transverse_{iy}",
            (-9.5, cy), (9.5, cy),
            z_base=11.8, z_peak=18.5,
            thickness=0.56, depth=0.48,
            mat=mats['stone'], segments=18,
        ))
        # Side aisle transverse ribs
        for s_idx, (wx, px) in enumerate([(-14.8, -9.5), (14.8, 9.5)]):
            objs.append(create_pointed_arch_rib(
                f"Aisle_Transverse_{iy}_{s_idx}",
                (px, cy), (wx, cy),
                z_base=10.2, z_peak=14.6,
                thickness=0.44, depth=0.38,
                mat=mats['stone'], segments=10,
            ))

    # Quadripartite diagonal groin ribs + Dragon-Boss Keystones in all Nave & Aisle bays
    for i in range(len(vault_ys) - 1):
        yA, yB = vault_ys[i], vault_ys[i + 1]
        yMid = 0.5 * (yA + yB)
        objs.append(create_pointed_arch_rib(
            f"Vault_Diag1_{i}",
            (-9.5, yA), (9.5, yB),
            z_base=11.8, z_peak=18.5,
            thickness=0.42, depth=0.38,
            mat=mats['frame'], segments=18,
        ))
        objs.append(create_pointed_arch_rib(
            f"Vault_Diag2_{i}",
            (9.5, yA), (-9.5, yB),
            z_base=11.8, z_peak=18.5,
            thickness=0.42, depth=0.38,
            mat=mats['frame'], segments=18,
        ))
        # Carved Stone Keystone Boss + Aged-Bronze Rosette at apex
        objs.append(add_cylinder(f"Vault_Keystone_Stone_{i}", (0, yMid, 18.48), 0.72, 0.42, 8, mats['frame'], uv_scale=0.30, rot=oct_rot))
        objs.append(add_cylinder(f"Vault_Keystone_Boss_{i}", (0, yMid, 18.24), 0.44, 0.14, 8, mats['gold'], uv_scale=0.35, rot=oct_rot))

        # Side aisle quadripartite diagonal ribs
        for s_idx, (x0, x1) in enumerate([(-14.8, -9.5), (9.5, 14.8)]):
            objs.append(create_pointed_arch_rib(f"Aisle_Diag1_{i}_{s_idx}", (x0, yA), (x1, yB), 10.2, 14.6, 0.30, 0.28, mats['frame'], segments=10))
            objs.append(create_pointed_arch_rib(f"Aisle_Diag2_{i}_{s_idx}", (x1, yA), (x0, yB), 10.2, 14.6, 0.30, 0.28, mats['frame'], segments=10))

    # Longitudinal Ridge Rib along nave ceiling centerline
    objs.append(add_box("Vault_Ridge_Rib", (0, 0, 18.56), (0.44, 48.0, 0.40), mats['frame'], uv_scale=0.20))

    # Multi-tier Gothic Vaulted Ceiling Shell (curved barrel-vaulted slopes rather than flat boards)
    vault_panels = [
        (-3.9, 18.65, 8.2, -0.14),
        (-11.4, 16.95, 8.2, -0.30),
        (3.9, 18.65, 8.2, 0.14),
        (11.4, 16.95, 8.2, 0.30),
    ]
    for p_idx, (vx, vz, vw, v_ang) in enumerate(vault_panels):
        objs.append(add_box(f"Cathedral_Vault_Shell_{p_idx}", (vx, 0.0, vz), (vw, 48.6, 0.42), mats['stone'], uv_scale=0.15, rot=(0.0, v_ang, 0.0)))

    # 5. Perimeter Side Walls & Tall Pointed Lancet Stained Glass Windows with Trefoil/Oculus Tracery
    for side_idx, wx in enumerate([-15.2, 15.2]):
        inward = 1.0 if wx < 0 else -1.0
        # Lower dado wall (Z = -3.8 to +1.8) + moulded sill ledge
        objs.append(add_box(f"SideWall_Dado_{side_idx}", (wx, 0, -1.0), (0.95, 48.4, 5.6), mats['stone'], uv_scale=0.15))
        objs.append(add_box(f"SideWall_Sill_{side_idx}", (wx + inward * 0.22, 0, 1.78), (0.55, 48.4, 0.22), mats['frame'], uv_scale=0.25))
        # Upper cornice wall (Z = +12.5 to +16.8)
        objs.append(add_box(f"SideWall_Cornice_{side_idx}", (wx, 0, 14.65), (0.95, 48.4, 4.3), mats['stone'], uv_scale=0.15))

        # Wall pilasters & spandrel piers framing the 5 pointed lancet windows
        pilaster_ys = [-23.5, -20.0, -12.0, -4.0, 4.0, 12.0, 20.0, 23.5]
        for p_idx, py in enumerate(pilaster_ys):
            objs.append(add_box(f"SideWall_Pier_{side_idx}_{p_idx}", (wx, py, 6.4), (1.35, 3.2, 20.4), mats['stone'], uv_scale=0.18))
            objs.append(add_cylinder(f"SideWall_Shaft_{side_idx}_{p_idx}", (wx + inward * 0.68, py, 3.2), 0.24, 14.0, 8, mats['frame'], uv_scale=0.25))

        # 5 Tall Pointed Lancet Stained Glass Windows (Y = -16, -8, 0, +8, +16)
        bay_ys = [-16.0, -8.0, 0.0, 8.0, 16.0]
        for b_idx, by in enumerate(bay_ys):
            # True pointed-arch stained glass panel (Z = 1.8 to 9.5 straight + 9.5 to 12.55 pointed arch!)
            objs.append(create_pointed_lancet_glass(f"Lancet_Glass_{side_idx}_{b_idx}", wx, by, 4.6, 1.8, 9.5, 12.55, mats['glass']))

            # Spandrel wall fill corners outside the pointed arch head (Z = 9.5 to 12.6)
            for s_cor in (-1.0, 1.0):
                objs.append(add_box(f"Lancet_Spandrel_{side_idx}_{b_idx}_{s_cor}", (wx, by + s_cor * 2.12, 11.75), (0.85, 0.68, 1.75), mats['stone'], uv_scale=0.20))

            # 3 Stone Gothic Mullions + 2 Horizontal Transoms
            for m_idx, (m_off, m_top) in enumerate([(-1.15, 10.6), (0.0, 9.9), (1.15, 10.6)]):
                m_h = m_top - 1.8
                objs.append(add_box(f"Lancet_Mullion_{side_idx}_{b_idx}_{m_idx}", (wx + inward * 0.18, by + m_off, 1.8 + m_h * 0.5), (0.34, 0.17, m_h), mats['frame'], uv_scale=0.30))
            for t_z in (4.6, 7.2):
                objs.append(add_box(f"Lancet_Transom_{side_idx}_{b_idx}_{t_z}", (wx + inward * 0.16, by, t_z), (0.30, 4.6, 0.16), mats['frame'], uv_scale=0.30))

            # Twin Pointed Sub-Arches (Trefoil/Lancet Lights) + Tympanum Stone Oculus Ring!
            for sub_y0, sub_y1 in ((by - 2.25, by), (by, by + 2.25)):
                objs.append(create_pointed_arch_rib(
                    f"Lancet_SubArch_{side_idx}_{b_idx}_{sub_y0:.1f}",
                    (wx + inward * 0.20, sub_y0), (wx + inward * 0.20, sub_y1),
                    z_base=8.5, z_peak=10.2,
                    thickness=0.32, depth=0.18,
                    mat=mats['frame'], segments=10,
                ))
            # Stone Oculus Tracery Ring in the upper lancet tympanum (centered at Z = 11.15, radius = 0.88)
            oc_segs = 16
            oc_rad = 0.88
            for os_i in range(oc_segs):
                am = (os_i + 0.5) * (2.0 * math.pi / oc_segs)
                seg_l = 2.0 * oc_rad * math.sin(math.pi / oc_segs) * 1.12
                objs.append(add_box(
                    f"Lancet_Oculus_{side_idx}_{b_idx}_{os_i}",
                    (wx + inward * 0.20, by + oc_rad * math.cos(am), 11.15 + oc_rad * math.sin(am)),
                    (0.32, 0.15, seg_l),
                    mats['frame'],
                    uv_scale=0.35,
                    rot=(am, 0.0, 0.0),
                ))

            # Grand Outer Pointed Hood Arch framing the Lancet Window
            objs.append(create_pointed_arch_rib(
                f"Lancet_HoodArch_{side_idx}_{b_idx}",
                (wx + inward * 0.26, by - 2.32),
                (wx + inward * 0.26, by + 2.32),
                z_base=9.5, z_peak=12.65,
                thickness=0.46, depth=0.34,
                mat=mats['frame'], segments=14,
            ))

    # 6. North End Wall (Y = -24.2) & Refined 36-Segment Grand Rose Window (Y = -23.65, Z = +10.0)
    objs.append(add_box("North_End_Wall", (0, -24.2, 8.2), (31.4, 0.95, 24.4), mats['stone'], uv_scale=0.15))

    rose_glass = add_cylinder(
        "Grand_Rose_Window_Glass",
        (0, -23.65, 10.0),
        4.95,
        0.16,
        36,
        mats['glass'],
        uv_scale=0.1,
        rot=(math.pi * 0.5, 0, 0),
    )
    # Exact world-space circular UVs in [0, 1] so concentric Chartres Rose tracery aligns 100% upright & radial!
    rg_mesh = rose_glass.data
    rg_uv = rg_mesh.uv_layers.active.data
    rg_mat = rose_glass.matrix_world
    for poly in rg_mesh.polygons:
        for loop_idx in poly.loop_indices:
            wco = rg_mat @ rg_mesh.vertices[rg_mesh.loops[loop_idx].vertex_index].co
            u = (wco.x / 4.95) * 0.5 + 0.5
            vv = ((wco.z - 10.0) / 4.95) * 0.5 + 0.5
            rg_uv[loop_idx].uv = (u, vv)
    objs.append(rose_glass)

    # 36-Segment Concentric Carved Stone Rings around the Grand Rose Window
    for r_idx, (rad, thick_r) in enumerate([(5.08, 0.34), (3.68, 0.24), (2.22, 0.22), (0.82, 0.18)]):
        segs = 36 if rad > 2.0 else 24
        for s in range(segs):
            am = (s + 0.5) * (2.0 * math.pi / segs)
            seg_len = 2.0 * rad * math.sin(math.pi / segs) * 1.08
            rx = rad * math.cos(am)
            rz = 10.0 + rad * math.sin(am)
            objs.append(add_box(
                f"Rose_Ring_{r_idx}_{s}",
                (rx, -23.48, rz),
                (thick_r, 0.38, seg_len),
                mats['frame'],
                uv_scale=0.30,
                rot=(0.0, -am, 0.0),
            ))

    # 12 Full Primary Radial Wheel Spokes + 12 Outer Secondary Spokes
    for sp in range(12):
        ang = (sp / 12.0) * math.pi
        objs.append(add_box(f"Rose_PrimarySpoke_{sp}", (0, -23.48, 10.0), (0.17, 0.32, 9.95), mats['frame'], uv_scale=0.30, rot=(0.0, ang, 0.0)))
    for sp24 in range(24):
        if sp24 % 2 == 1:
            ang24 = (sp24 / 24.0) * 2.0 * math.pi
            mid_r = 4.38
            objs.append(add_box(
                f"Rose_OuterSpoke_{sp24}",
                (mid_r * math.cos(ang24), -23.50, 10.0 + mid_r * math.sin(ang24)),
                (1.42, 0.24, 0.13),
                mats['frame'],
                uv_scale=0.35,
                rot=(0.0, -ang24, 0.0),
            ))

    # Grand Pointed Gothic Arch Hood Framing the Entire Rose Window (Z = 8.0 to 16.6)
    objs.append(create_pointed_arch_rib(
        "Rose_Grand_HoodArch",
        (-5.55, -23.35), (5.55, -23.35),
        z_base=8.8, z_peak=16.6,
        thickness=0.62, depth=0.48,
        mat=mats['stone'], segments=18,
    ))

    # Flanking Pointed Stained-Glass Lancets on North Wall (X = ±5.8, leaving center clear for High Altar!)
    for nx in (-5.8, 5.8):
        bm_nl = bmesh.new()
        hw_nl = 1.35
        prof_xz = [(-hw_nl, -2.0), (hw_nl, -2.0), (hw_nl, 1.8)]
        for i_a in range(1, 12):
            t_a = i_a / 12.0
            u_a = t_a * 2.0 if t_a <= 0.5 else (1.0 - t_a) * 2.0
            xl_a = hw_nl * (1.0 - u_a) if t_a <= 0.5 else -hw_nl * (1.0 - u_a)
            zl_a = 1.8 + (3.55 - 1.8) * math.sin(u_a * math.pi * 0.5)
            prof_xz.append((xl_a, zl_a))
        prof_xz.append((-hw_nl, 1.8))
        vf_nl = [bm_nl.verts.new((nx + xl_a, -23.60, zl_a)) for (xl_a, zl_a) in prof_xz]
        vb_nl = [bm_nl.verts.new((nx + xl_a, -23.74, zl_a)) for (xl_a, zl_a) in prof_xz]
        bm_nl.faces.new(vf_nl)
        bm_nl.faces.new(vb_nl[::-1])
        for k_a in range(len(prof_xz)):
            kn_a = (k_a + 1) % len(prof_xz)
            bm_nl.faces.new((vf_nl[k_a], vb_nl[k_a], vb_nl[kn_a], vf_nl[kn_a]))
        bmesh.ops.recalc_face_normals(bm_nl, faces=bm_nl.faces)
        nl_m = bpy.data.meshes.new(f"North_Lancet_Glass_{nx}")
        bm_nl.to_mesh(nl_m)
        bm_nl.free()
        nl_glass = bpy.data.objects.new(f"North_Lancet_Glass_{nx}", nl_m)
        bpy.context.collection.objects.link(nl_glass)
        nl_glass.data.materials.append(mats['glass'])
        nl_m.uv_layers.new(name="UVMap")
        nl_uv = nl_m.uv_layers.active.data
        for poly in nl_m.polygons:
            for loop_idx in poly.loop_indices:
                v = nl_m.vertices[nl_m.loops[loop_idx].vertex_index].co
                nl_uv[loop_idx].uv = (((v.x - nx) / 1.42) * 0.46 + 0.5, ((v.z - 1.95) / 1.42) * 0.46 + 0.5)
        objs.append(nl_glass)
        objs.append(add_box(f"North_Lancet_Mullion_{nx}", (nx, -23.54, 0.65), (0.15, 0.28, 5.3), mats['frame'], uv_scale=0.3))
        objs.append(add_box(f"North_Lancet_Sill_{nx}", (nx, -23.50, -2.05), (3.10, 0.36, 0.18), mats['frame'], uv_scale=0.3))
        objs.append(create_pointed_arch_rib(
            f"North_Lancet_Arch_{nx}",
            (nx - 1.42, -23.48), (nx + 1.42, -23.48),
            z_base=1.8, z_peak=3.65,
            thickness=0.40, depth=0.34,
            mat=mats['frame'], segments=12,
        ))

    # Build the North Dragon-Sanctum High Altar & Winged Reliquary Arch (Y = -20.5, Z = -3.8..+1.95)
    build_north_dragon_high_altar(objs, mats)

    # 7. South End Wall (Y = +24.2) with Grand Gothic Portal Doors & Tympanum Relief
    objs.append(add_box("South_End_Wall", (0, 24.2, 8.2), (31.4, 0.95, 24.4), mats['stone'], uv_scale=0.15))
    objs.append(add_box("South_Portal_Doors", (0, 23.65, 1.2), (5.6, 0.35, 10.0), mats['wood'], uv_scale=0.25))
    objs.append(add_box("South_Portal_Trumeau", (0, 23.42, 0.6), (0.42, 0.45, 8.8), mats['frame'], uv_scale=0.30))
    for arch_order, (span_w, pk_z, mat_a) in enumerate([(3.0, 8.2, mats['frame']), (3.5, 8.9, mats['stone']), (4.0, 9.6, mats['frame'])]):
        objs.append(create_pointed_arch_rib(
            f"South_Portal_Arch_{arch_order}",
            (-span_w, 23.38 - arch_order * 0.14), (span_w, 23.38 - arch_order * 0.14),
            z_base=4.0, z_peak=pk_z,
            thickness=0.48, depth=0.42,
            mat=mat_a, segments=14,
        ))

    # 8. Carved Gothic Choir & Side-Aisle Pews (well clear of the central dais!)
    for side_x, face_dir in ((-12.2, 1.0), (12.2, -1.0)):
        for pew_y in (-16.0, -8.2, 8.2, 16.0):
            build_gothic_choir_pew(objs, f"AislePew_{side_x}_{pew_y}", side_x, pew_y, -3.80, 3.8, face_dir, mats)

    # Flanking Choir Stalls in North & South outer nave bays (X = ±6.8, |Y| >= 13.8, >7.5m away from central dais!)
    for choir_x, face_dir in ((-6.8, 1.0), (6.8, -1.0)):
        for choir_y in (-15.0, 14.2, 17.5):
            build_gothic_choir_pew(objs, f"ChoirStall_{choir_x}_{choir_y}", choir_x, choir_y, -3.80, 2.6, face_dir, mats)

    # 9. Three Wrought-Iron Dragon-Crest Ring Chandeliers suspended at Z = +11.5 (Y = -12, 0, +12)
    chandelier_ys = [-12.0, 0.0, 12.0]
    for c_idx, cy in enumerate(chandelier_ys):
        # Heavy suspension chain & central forged hub
        objs.append(add_cylinder(f"Chandelier_Chain_{c_idx}", (0, cy, 14.95), 0.08, 6.9, 8, mats['iron'], uv_scale=0.5))
        objs.append(add_cylinder(f"Chandelier_CentralHub_{c_idx}", (0, cy, 11.65), 0.34, 0.55, 8, mats['iron'], uv_scale=0.4))
        objs.append(add_cone(f"Chandelier_DropFinial_{c_idx}", (0, cy, 11.18), 0.22, 0.03, 0.42, 8, mats['gold'], uv_scale=0.4))

        # Outer (r = 2.45) and Inner (r = 1.22) wrought-iron corona rings
        for r_tag, rad, ring_h in (("Outer", 2.45, 0.28), ("Inner", 1.22, 0.18)):
            segs = 16 if rad > 2.0 else 12
            for s in range(segs):
                am = (s + 0.5) * (2.0 * math.pi / segs)
                seg_len = 2.0 * rad * math.sin(math.pi / segs) * 1.06
                rx = rad * math.cos(am)
                ry = cy + rad * math.sin(am)
                objs.append(add_box(
                    f"Chandelier_{r_tag}Ring_{c_idx}_{s}",
                    (rx, ry, 11.5),
                    (0.16, seg_len, ring_h),
                    mats['iron'],
                    uv_scale=0.5,
                    rot=(0.0, 0.0, am),
                ))

        # 8 Radial Spokes + 8 Wrought-Iron Silhouetted Dragon-Crest Finials + 8 Glowing Candles
        for sp in range(8):
            ang = sp * (math.pi * 0.25)
            ux, uy = math.cos(ang), math.sin(ang)
            # Radial iron spoke connecting central hub to outer ring
            objs.append(add_box(
                f"Chandelier_Spoke_{c_idx}_{sp}",
                (1.22 * ux, cy + 1.22 * uy, 11.5),
                (2.40, 0.07, 0.10),
                mats['iron'],
                uv_scale=0.5,
                rot=(0.0, 0.0, ang),
            ))
            # Silhouetted wrought-iron Dragon-Wing Crest jutting outward from the corona ring!
            objs.append(add_cone(
                f"Chandelier_DragonCrest_{c_idx}_{sp}",
                (2.68 * ux, cy + 2.68 * uy, 11.68),
                0.22, 0.03, 0.48, 4,
                mats['iron'],
                uv_scale=0.5,
                rot=(uy * 0.55, -ux * 0.55, ang),
            ))
            # Bronze candle pricket dish + wax candle + glowing flame
            cx_c, cy_c = 2.45 * ux, cy + 2.45 * uy
            objs.append(add_cylinder(f"Chandelier_Dish_{c_idx}_{sp}", (cx_c, cy_c, 11.68), 0.14, 0.05, 8, mats['gold'], uv_scale=0.5))
            objs.append(add_cylinder(f"Chandelier_Candle_{c_idx}_{sp}", (cx_c, cy_c, 11.90), 0.065, 0.38, 8, mats['stone'], uv_scale=0.5))
            objs.append(add_cone(f"Chandelier_Flame_{c_idx}_{sp}", (cx_c, cy_c, 12.18), 0.075, 0.01, 0.22, 8, mats['ember'], uv_scale=0.5))

        # 4 Diagonal suspension rods from upper chain collar (Z = +13.8) to outer ring (Z = +11.5)
        for sp4 in range(4):
            ang4 = (sp4 + 0.5) * (math.pi * 0.5)
            sx = 1.22 * math.cos(ang4)
            sy = cy + 1.22 * math.sin(ang4)
            objs.append(add_cylinder(
                f"Chandelier_Strut_{c_idx}_{sp4}",
                (sx, sy, 12.65),
                0.04, 3.35, 6,
                mats['iron'],
                uv_scale=0.5,
                rot=(math.sin(ang4) * 0.82, -math.cos(ang4) * 0.82, 0.0),
            ))

    return objs


def join_by_material():
    """Join meshes sharing the same material into clean architectural groups for minimal GLB draw calls."""
    groups = {}
    for obj in list(bpy.context.scene.objects):
        if obj.type == 'MESH' and obj.data.materials:
            mat_name = obj.data.materials[0].name
            groups.setdefault(mat_name, []).append(obj)

    for mat_name, obj_list in groups.items():
        if len(obj_list) <= 1:
            continue
        bpy.ops.object.select_all(action='DESELECT')
        for o in obj_list:
            o.select_set(True)
        bpy.context.view_layer.objects.active = obj_list[0]
        bpy.ops.object.join()
        joined = bpy.context.view_layer.objects.active
        joined.name = f"Cathedral_{mat_name}"


def setup_lighting_and_render(output_path):
    print("Setting up atmospheric Gothic sanctuary lighting and rendering 1920x1080 preview...")
    scene = bpy.context.scene

    # Deep twilight cathedral ambience
    world = bpy.data.worlds.new("CathedralWorld")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get('Background')
    if bg:
        bg.inputs['Color'].default_value = (0.05, 0.06, 0.11, 1.0)
        bg.inputs['Strength'].default_value = 0.95

    # Warm Spotlight illuminating the Dragon-Carved Chess Altar Table (soft radius = zero harsh glare)
    key_data = bpy.data.lights.new(name="ChessTable_KeyLight", type='SPOT')
    key_data.energy = 2600.0
    key_data.color = (1.0, 0.86, 0.66)
    key_data.spot_size = math.radians(72)
    key_data.spot_blend = 0.55
    key_data.shadow_soft_size = 1.6
    key_obj = bpy.data.objects.new(name="ChessTable_KeyLight", object_data=key_data)
    key_obj.location = (1.5, 3.0, 10.2)
    key_obj.rotation_euler = (math.radians(-14), math.radians(6), 0.0)
    scene.collection.objects.link(key_obj)

    # 4 Warm Fire Point Lights above the 4 Sculpted Dragon-Head Corner Braziers
    for idx, (bx, by) in enumerate([(-5.35, -5.35), (5.35, -5.35), (5.35, 5.35), (-5.35, 5.35)]):
        pt = bpy.data.lights.new(name=f"Brazier_Light_{idx}", type='POINT')
        pt.energy = 380.0
        pt.color = (1.0, 0.54, 0.18)
        pt.use_shadow = False
        pt_obj = bpy.data.objects.new(name=f"Brazier_Light_{idx}", object_data=pt)
        pt_obj.location = (bx, by, 1.35)
        scene.collection.objects.link(pt_obj)

    # Cool Moonlit Rim / Stained Glass Sun streaming from the North Rose Window
    sun = bpy.data.lights.new(name="RoseWindow_Light", type='SUN')
    sun.energy = 2.2
    sun.color = (0.60, 0.76, 1.0)
    sun.use_shadow = True
    sun_obj = bpy.data.objects.new(name="RoseWindow_Light", object_data=sun)
    sun_obj.location = (0, -18, 12)
    sun_obj.rotation_euler = (math.radians(52), math.radians(10), math.radians(12))
    scene.collection.objects.link(sun_obj)

    # High Altar Sanctuary Warm Accent Light showcasing the Carved Stone Dragon Wings!
    altar_light = bpy.data.lights.new(name="HighAltar_Light", type='POINT')
    altar_light.energy = 950.0
    altar_light.color = (1.0, 0.66, 0.30)
    altar_light.use_shadow = False
    altar_obj = bpy.data.objects.new(name="HighAltar_Light", object_data=altar_light)
    altar_obj.location = (0.0, -18.2, 1.8)
    scene.collection.objects.link(altar_obj)

    # Nave Chandelier & Gargoyle Upper Fill Lights (illuminating the perched Z=8.6 Dragon Gargoyles & Triforium!)
    for cy in [-12.0, 0.0, 12.0]:
        ch_light = bpy.data.lights.new(name=f"Chandelier_Light_{cy}", type='POINT')
        ch_light.energy = 1650.0
        ch_light.color = (1.0, 0.79, 0.52)
        ch_light.use_shadow = (cy == 0.0)
        ch_light.shadow_soft_size = 1.0
        ch_obj = bpy.data.objects.new(name=f"Chandelier_Light_{cy}", object_data=ch_light)
        ch_obj.location = (0.0, cy, 10.8)
        scene.collection.objects.link(ch_obj)

    # Dramatic Architectural Hero Camera framing:
    # - Foreground: Dragon-Head Corner Braziers, Carved Board & Tiles, Octagonal Dais & Buttress Pedestal
    # - Midground: Clustered Nave Piers, Perched Z=8.6 Stone Dragon Gargoyles, Triforium Arcade, Pews & Chandeliers
    # - Background: Winged High Altar & 36-segment Grand Rose Window + Ribbed Vaults!
    cam_data = bpy.data.cameras.new(name="PreviewCamera")
    cam_data.lens = 20.0
    cam_data.clip_end = 200.0
    cam_obj = bpy.data.objects.new(name="PreviewCamera", object_data=cam_data)
    cam_obj.location = (7.6, 12.2, 5.6)
    target = Vector((-0.3, -4.2, 1.4))
    direction = target - cam_obj.location
    rot_quat = direction.to_track_quat('-Z', 'Y')
    cam_obj.rotation_euler = rot_quat.to_euler()
    scene.collection.objects.link(cam_obj)
    scene.camera = cam_obj

    # Configure EEVEE in Blender 5.2
    available_engines = [e.identifier for e in scene.render.bl_rna.properties['engine'].enum_items]
    if 'BLENDER_EEVEE' in available_engines:
        scene.render.engine = 'BLENDER_EEVEE'
    elif 'BLENDER_EEVEE_NEXT' in available_engines:
        scene.render.engine = 'BLENDER_EEVEE_NEXT'

    if hasattr(scene, 'view_settings'):
        scene.view_settings.exposure = 0.15

    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = output_path

    bpy.ops.render.render(write_still=True)
    print(f"[Rendered] {output_path}")

    # Remove helper lights and camera before GLB export
    for obj in list(scene.objects):
        if obj.type in ('LIGHT', 'CAMERA'):
            bpy.data.objects.remove(obj, do_unlink=True)


def main():
    clear_scene()

    mats = {
        'stone': create_pbr_material(
            "Gothic_Stone_Mat",
            albedo_file="cathedral_stone_albedo.png",
            normal_file="cathedral_stone_normal.png",
            rough_file="cathedral_stone_roughness.png",
            ao_file="cathedral_stone_ao.png",
            normal_strength=1.25,
        ),
        'floor': create_pbr_material(
            "Cathedral_Floor_Mat",
            albedo_file="cathedral_floor_albedo.png",
            normal_file="cathedral_floor_normal.png",
            rough_file="cathedral_floor_roughness.png",
            ao_file="cathedral_floor_ao.png",
            normal_strength=1.15,
        ),
        'glass': create_pbr_material(
            "Stained_Glass_Mat",
            albedo_file="stained_glass_albedo.png",
            emission_file="stained_glass_emission.png",
            rough_file="stained_glass_roughness.png",
            emission_strength=2.6,
        ),
        'frame': create_pbr_material(
            "Board_Frame_Mat",
            albedo_file="board_frame_albedo.png",
            normal_file="board_frame_normal.png",
            rough_file="board_frame_roughness.png",
            metallic_file="board_frame_metallic.png",
            normal_strength=1.35,
        ),
        'tiles': create_pbr_material(
            "Board_Tiles_Mat",
            albedo_file="board_tiles_albedo.png",
            normal_file="board_tiles_normal.png",
            rough_file="board_tiles_roughness.png",
            metallic_file="board_tiles_metallic.png",
            ao_file="board_tiles_ao.png",
            normal_strength=1.10,
        ),
        'gold': create_pbr_material(
            "Gilded_Bronze_Mat",
            base_color=(0.54, 0.41, 0.20, 1.0),
            metallic_val=0.76,
            roughness_val=0.54,
        ),
        'iron': create_pbr_material(
            "Wrought_Iron_Mat",
            base_color=(0.10, 0.10, 0.12, 1.0),
            metallic_val=0.78,
            roughness_val=0.56,
        ),
        'wood': create_pbr_material(
            "Dark_Gothic_Oak_Mat",
            normal_file="cathedral_stone_normal.png",
            base_color=(0.12, 0.08, 0.055, 1.0),
            metallic_val=0.0,
            roughness_val=0.72,
            normal_strength=0.35,
        ),
        'ember': create_pbr_material(
            "Fire_Ember_Mat",
            base_color=(0.18, 0.03, 0.005, 1.0),
            metallic_val=0.0,
            roughness_val=0.55,
            emission_color=(1.0, 0.18, 0.01, 1.0),
            emission_strength=4.5,
        ),
    }

    build_chess_table_and_pedestal(mats)
    build_cathedral_hall(mats)
    join_by_material()

    # Calculate scene geometry statistics
    total_verts = 0
    total_faces = 0
    total_tris = 0
    for obj in bpy.context.scene.objects:
        if obj.type == 'MESH':
            m = obj.data
            total_verts += len(m.vertices)
            total_faces += len(m.polygons)
            total_tris += sum(len(p.vertices) - 2 for p in m.polygons)

    print("=== Cathedral Scene Stats ===")
    print(f"Mesh Objects: {len([o for o in bpy.context.scene.objects if o.type == 'MESH'])}")
    print(f"Total Vertices: {total_verts}")
    print(f"Total Polygons: {total_faces}")
    print(f"Total Triangles: {total_tris}")

    # Render 1920x1080 preview
    preview_path = os.path.join(RENDER_DIR, "cathedral_preview.png")
    setup_lighting_and_render(preview_path)

    # Export GLB with embedded 2K PBR textures and +Y up
    glb_path = os.path.join(MODEL_DIR, "gothic_cathedral.glb")
    bpy.ops.export_scene.gltf(
        filepath=glb_path,
        export_format='GLB',
        export_yup=True,
        export_apply=True,
        export_materials='EXPORT',
    )
    print(f"[Exported GLB] {glb_path} ({os.path.getsize(glb_path) / (1024 * 1024):.2f} MB)")


if __name__ == "__main__":
    main()
