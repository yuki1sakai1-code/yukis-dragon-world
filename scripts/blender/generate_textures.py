"""
Procedural 2K (2048x2048) Gothic Dragon-Sanctum & Arcane Magic-Circle PBR Texture Generator.
Abolishes all chess checkerboards in favor of:
  - Irregular medieval High-Gothic slate & limestone flagstones (cathedral_floor_*)
  - Organic weathered Caen limestone & dark Gothic masonry with soft lime mortar (cathedral_stone_*)
  - Cracked volcanic-basalt & temple-limestone sanctuary floor with a monumental
    Carved Elder Draconic Summoning Magic Circle & glowing cyan/gold ley-lines (board_tiles_*)
  - Monolithic chiselled dark volcanic dragon-stone & wyrm-relief masonry (board_frame_*)
  - Chartres Gothic Rose & Draconic Heraldry stained glass (stained_glass_*)
Generates all 20 deterministic 2048x2048 PNG maps into dragon_spec.TEXTURES_DIR.
"""
import os
import sys
import math
import zlib
import struct
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dragon_spec import TEXTURES_DIR, TEXTURE_SIZE

os.makedirs(TEXTURES_DIR, exist_ok=True)
SIZE = TEXTURE_SIZE  # 2048


def _png_chunk(chunk_type, data):
    chunk = chunk_type + data
    return (
        struct.pack(">I", len(data))
        + chunk
        + struct.pack(">I", zlib.crc32(chunk) & 0xFFFFFFFF)
    )


def save_image(name, rgba_array, is_data=False):
    """
    Deterministic fast 2048x2048 RGBA8 PNG writer using zlib/struct.
    rgba_array: float32 array of shape (H, W, 4) in [0, 1], bottom-to-top row order
                (row 0 -> UV v=0, row H-1 -> UV v=1), matching Blender & OpenGL UVs.
    """
    H, W, C = rgba_array.shape
    assert (W, H) == (SIZE, SIZE) and C == 4, f"Expected ({SIZE},{SIZE},4), got {rgba_array.shape}"

    top_down = np.clip(rgba_array[::-1], 0.0, 1.0)
    u8 = (top_down * 255.0 + 0.5).astype(np.uint8)

    scanlines = np.empty((H, W * 4 + 1), dtype=np.uint8)
    scanlines[:, 0] = 0
    scanlines[:, 1:] = u8.reshape(H, W * 4)

    ihdr = struct.pack(">IIBBBBB", W, H, 8, 6, 0, 0, 0)
    compressed = zlib.compress(scanlines.tobytes(), level=6)

    filepath = os.path.join(TEXTURES_DIR, name)
    with open(filepath, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(_png_chunk(b"IHDR", ihdr))
        f.write(_png_chunk(b"IDAT", compressed))
        f.write(_png_chunk(b"IEND", b""))

    mode_str = "Non-Color" if is_data else "sRGB"
    print(f"[Saved] {filepath} ({W}x{H}, {mode_str})")


def smoothstep(edge0, edge1, x):
    t = np.clip((x - edge0) / (edge1 - edge0 + 1e-8), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def fbm_noise(shape, scales, weights, seed=42):
    """Deterministic tileable multi-scale noise with C2 quintic interpolation."""
    rng = np.random.default_rng(seed)
    H, W = shape
    result = np.zeros((H, W), dtype=np.float32)
    y_idx = np.linspace(0.0, 1.0, H, endpoint=False, dtype=np.float32)
    x_idx = np.linspace(0.0, 1.0, W, endpoint=False, dtype=np.float32)

    for scale, weight in zip(scales, weights):
        gh = max(2, int(scale))
        gw = max(2, int(scale))
        grid = rng.random((gh, gw), dtype=np.float32)

        gy = y_idx * gh
        gx = x_idx * gw
        gy0 = np.floor(gy).astype(np.int32) % gh
        gx0 = np.floor(gx).astype(np.int32) % gw
        gy1 = (gy0 + 1) % gh
        gx1 = (gx0 + 1) % gw

        fy = (gy - np.floor(gy)).astype(np.float32)
        fx = (gx - np.floor(gx)).astype(np.float32)
        uy = fy * fy * fy * (fy * (fy * 6.0 - 15.0) + 10.0)
        ux = fx * fx * fx * (fx * (fx * 6.0 - 15.0) + 10.0)

        v00 = grid[gy0[:, None], gx0[None, :]]
        v10 = grid[gy1[:, None], gx0[None, :]]
        v01 = grid[gy0[:, None], gx1[None, :]]
        v11 = grid[gy1[:, None], gx1[None, :]]

        v0 = v00 + uy[:, None] * (v10 - v00)
        v1 = v01 + uy[:, None] * (v11 - v01)
        result += (v0 + ux[None, :] * (v1 - v0)) * weight

    mn, mx = float(result.min()), float(result.max())
    if mx > mn:
        result = (result - mn) / (mx - mn)
    return result


def voronoi_cracks(x, y, grid_n=10, jitter=0.78, seed=777, tileable=True):
    """
    Fast vectorized 2D Voronoi cellular stone tessellation.
    Returns (edge_dist, cell_hash):
      edge_dist: perpendicular distance to nearest polygon boundary in cell units [0, ~0.5]
      cell_hash: deterministic random value in [0, 1] per stone polygon.
    """
    rng = np.random.default_rng(seed)
    pts_x = rng.uniform(0.5 - 0.5 * jitter, 0.5 + 0.5 * jitter, size=(grid_n, grid_n)).astype(np.float32)
    pts_y = rng.uniform(0.5 - 0.5 * jitter, 0.5 + 0.5 * jitter, size=(grid_n, grid_n)).astype(np.float32)
    hashes = rng.random((grid_n, grid_n)).astype(np.float32)

    gx = x * grid_n
    gy = y * grid_n
    ix = np.floor(gx).astype(np.int32)
    iy = np.floor(gy).astype(np.int32)
    fx = gx - ix
    fy = gy - iy

    # First pass: find closest seed (f1_x, f1_y) and its cell hash
    d1 = np.full(fx.shape, 1e9, dtype=np.float32)
    best_dx = np.zeros_like(fx)
    best_dy = np.zeros_like(fy)
    best_hash = np.zeros_like(fx)

    offsets = [(-1, -1), (0, -1), (1, -1), (-1, 0), (0, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]
    for ox, oy in offsets:
        nx_i = (ix + ox) % grid_n if tileable else np.clip(ix + ox, 0, grid_n - 1)
        ny_i = (iy + oy) % grid_n if tileable else np.clip(iy + oy, 0, grid_n - 1)
        rx = ox + pts_x[ny_i, nx_i] - fx
        ry = oy + pts_y[ny_i, nx_i] - fy
        dist2 = rx * rx + ry * ry
        mask = dist2 < d1
        d1 = np.where(mask, dist2, d1)
        best_dx = np.where(mask, rx, best_dx)
        best_dy = np.where(mask, ry, best_dy)
        best_hash = np.where(mask, hashes[ny_i, nx_i], best_hash)

    # Second pass: true perpendicular distance to Voronoi polygon edge!
    edge_dist = np.full(fx.shape, 1e9, dtype=np.float32)
    for ox, oy in offsets:
        nx_i = (ix + ox) % grid_n if tileable else np.clip(ix + ox, 0, grid_n - 1)
        ny_i = (iy + oy) % grid_n if tileable else np.clip(iy + oy, 0, grid_n - 1)
        rx = ox + pts_x[ny_i, nx_i] - fx
        ry = oy + pts_y[ny_i, nx_i] - fy
        diff_x = rx - best_dx
        diff_y = ry - best_dy
        diff_len = np.sqrt(diff_x * diff_x + diff_y * diff_y)
        valid = diff_len > 1e-4
        # Distance from pixel (0,0) to bisector between best_d and r
        mx = 0.5 * (best_dx + rx)
        my = 0.5 * (best_dy + ry)
        proj = (mx * diff_x + my * diff_y) / np.where(valid, diff_len, 1.0)
        edge_dist = np.where(valid, np.minimum(edge_dist, proj), edge_dist)

    return edge_dist, best_hash


def segment_sdf(px, py, ax, ay, bx, by):
    """Exact 2D unsigned distance from points (px, py) to line segment (ax, ay) -> (bx, by)."""
    vx, vy = bx - ax, by - ay
    wx, wy = px - ax, py - ay
    denom = vx * vx + vy * vy + 1e-12
    t = np.clip((wx * vx + wy * vy) / denom, 0.0, 1.0)
    dx = wx - t * vx
    dy = wy - t * vy
    return np.sqrt(dx * dx + dy * dy)


def height_to_normal(height, strength=4.5):
    """Compute OpenGL tangent-space normal map RGBA from bottom-to-top heightfield in [0, 1]."""
    dy = (np.roll(height, -1, axis=0) - np.roll(height, 1, axis=0)) * 0.5 * strength
    dx = (np.roll(height, -1, axis=1) - np.roll(height, 1, axis=1)) * 0.5 * strength
    nx = -dx
    ny = -dy
    nz = np.ones_like(height, dtype=np.float32)
    inv_norm = 1.0 / np.sqrt(nx * nx + ny * ny + nz * nz + 1e-12)
    rgba = np.ones((height.shape[0], height.shape[1], 4), dtype=np.float32)
    rgba[..., 0] = (nx * inv_norm) * 0.5 + 0.5
    rgba[..., 1] = (ny * inv_norm) * 0.5 + 0.5
    rgba[..., 2] = (nz * inv_norm) * 0.5 + 0.5
    return rgba


def gray_to_rgba(gray):
    g2d = np.broadcast_to(np.clip(gray, 0.0, 1.0), (SIZE, SIZE))
    rgba = np.ones((SIZE, SIZE, 4), dtype=np.float32)
    rgba[..., 0] = g2d
    rgba[..., 1] = g2d
    rgba[..., 2] = g2d
    return rgba


def dragon_scales_field(u, v, cols, rows):
    """Returns (relief_height, crevice_ao) in [0, 1] for imbricated chiselled Gothic dragon scales."""
    ry = v * rows
    r_id = np.floor(ry).astype(np.int32)
    fy = ry - np.floor(ry)

    rx = u * cols + (r_id % 2) * 0.5
    fx = (rx - np.floor(rx)) - 0.5

    ax = np.abs(fx) * 2.0
    margin_y = 0.14 + 0.48 * np.power(ax, 1.55)
    d_lip = fy - margin_y
    inside = smoothstep(-0.02, 0.045, d_lip)
    undercut = 1.0 - 0.55 * np.exp(-((d_lip + 0.045) / 0.055) ** 2) * (1.0 - inside)

    edge_ridge = np.exp(-((d_lip - 0.055) / 0.085) ** 2) * inside
    keel = np.exp(-(fx / 0.095) ** 2) * smoothstep(margin_y, margin_y + 0.35, fy) * (1.0 - smoothstep(0.82, 1.0, fy))
    slope = (1.0 - 0.45 * np.clip((fy - margin_y) / (1.0 - margin_y + 1e-5), 0.0, 1.0)) * inside

    seam = smoothstep(0.0, 0.07, np.abs(d_lip))
    height = np.clip((0.55 * slope + 0.25 * edge_ridge + 0.22 * keel) * seam, 0.0, 1.0)
    ao = np.clip((0.46 + 0.54 * seam) * undercut, 0.24, 1.0)
    return height, ao


# ==============================================================================
# 1. CATHEDRAL STONE (4 maps: Organic Weathered Caen Limestone — Soft Lime Mortar!)
# ==============================================================================
def generate_cathedral_stone():
    print("Generating Cathedral Stone 2K PBR maps (Organic Caen Limestone & Weathered Gothic Masonry)...")
    H, W = SIZE, SIZE
    y = np.linspace(0.0, 1.0, H, endpoint=False, dtype=np.float32)[:, None]
    x = np.linspace(0.0, 1.0, W, endpoint=False, dtype=np.float32)[None, :]

    n_macro = fbm_noise((H, W), [3, 6, 12], [0.55, 0.28, 0.17], seed=101)
    n_med = fbm_noise((H, W), [20, 44, 88], [0.50, 0.30, 0.20], seed=102)
    n_micro = fbm_noise((H, W), [128, 256, 512], [0.45, 0.35, 0.20], seed=103)
    # Vertical rainwater & age streaking
    n_streak = fbm_noise((H, W), [6, 18, 36], [0.55, 0.30, 0.15], seed=109)

    # Non-uniform organic masonry courses (9 courses of varied medieval height!)
    course_edges = np.array([0.0, 0.115, 0.215, 0.335, 0.435, 0.560, 0.675, 0.775, 0.890, 1.0], dtype=np.float32)
    row_id = np.clip(np.searchsorted(course_edges, y, side='right') - 1, 0, 8).astype(np.int32)
    y0 = course_edges[row_id]
    y1 = course_edges[row_id + 1]
    fy = (y - y0) / (y1 - y0 + 1e-6)

    #Varied blocks per row + organic stagger (zero cartoon brick-grid uniformity!)
    cols_per_row = np.array([4.0, 5.0, 3.0, 4.0, 6.0, 4.0, 5.0, 3.0, 4.0], dtype=np.float32)
    row_offsets = np.array([0.00, 0.37, 0.61, 0.19, 0.50, 0.73, 0.29, 0.64, 0.42], dtype=np.float32)
    cols = cols_per_row[row_id]
    rx = x * cols + row_offsets[row_id]
    col_id = np.floor(rx).astype(np.int32)
    fx = rx - np.floor(rx)

    # Subtle weathered dragon-scale string course only on narrow course 4
    is_scale_course = (row_id == 4)

    # Organic hand-dressed edge chipping & narrow mortar joints (NO dark cartoon outlines!)
    wobble_x = (n_med - 0.5) * 0.028 + (n_micro - 0.5) * 0.012
    wobble_y = (np.roll(n_med, 257, axis=0) - 0.5) * 0.042 + (n_micro - 0.5) * 0.016

    dx = np.minimum(fx + wobble_x, 1.0 - (fx + wobble_x)) / (cols / 4.0)
    dy = np.minimum(fy + wobble_y, 1.0 - (fy + wobble_y)) * 0.48
    joint_dist = np.minimum(dx, dy)

    # Narrow, naturally eroded mortar joint (0.003 -> 0.019 instead of thick black bars!)
    bevel = smoothstep(0.0035, 0.020, joint_dist)

    rng = np.random.default_rng(105)
    block_table = rng.uniform(-0.042, 0.042, size=(16, 16)).astype(np.float32)
    block_var = block_table[row_id % 16, col_id % 16]

    # Fine mason chisel marks & limestone fossil pitting
    chisel_dir = np.where(((row_id + col_id) % 2) == 0, 1.0, -1.0)
    chisel = np.sin((x * 210.0 + y * 210.0 * chisel_dir + n_med * 1.8) * math.pi) * 0.014 * bevel
    pitting = np.where(n_micro < 0.19, (n_micro - 0.19) * 1.15, 0.0)
    spall = np.where(n_med < 0.16, (n_med - 0.16) * 0.65, 0.0)

    sc_h, sc_ao = dragon_scales_field(x, fy, cols=26.0, rows=2.0)
    band_inner = smoothstep(0.10, 0.18, fy) * smoothstep(0.90, 0.82, fy)
    scale_h = (0.54 + 0.30 * sc_h) * band_inner + 0.74 * (1.0 - band_inner)

    ashlar_h = 0.74 + 0.12 * n_macro + 0.09 * n_med + 0.05 * n_micro + block_var * 0.35 + chisel + pitting + spall
    stone_h = np.where(is_scale_course, scale_h + pitting * 0.5, ashlar_h)
    height = np.clip(0.28 + 0.72 * bevel * stone_h, 0.0, 1.0)

    carved_ao = np.where(is_scale_course, 0.72 + 0.28 * sc_ao, 1.0)
    ao = np.clip((0.52 + 0.48 * bevel) * carved_ao - 0.10 * (1.0 - n_micro) - 0.08 * (1.0 - n_macro), 0.32, 1.0)

    # Authentic weathered Caen limestone & dark Gothic stone (organic mottled stone, dusty lime mortar!)
    weather_cloud = 0.09 * (n_macro - 0.5) + 0.06 * (n_med - 0.5) + 0.035 * (n_micro - 0.5)
    streak_dark = np.clip((0.52 - n_streak) * 0.30, -0.03, 0.06)
    base_r = 0.39 + block_var + weather_cloud - streak_dark
    base_g = 0.365 + block_var * 0.94 + weather_cloud * 0.95 - streak_dark * 0.95
    base_b = 0.32 + block_var * 0.85 + weather_cloud * 0.88 - streak_dark * 0.85

    # Subtle olive lichen/moss in damp pockets
    moss_mask = np.clip((1.0 - fy) * 0.45 + (1.0 - n_macro) * 0.60 - 0.68, 0.0, 1.0) * bevel
    base_r = base_r * (1.0 - moss_mask * 0.30) + 0.18 * (moss_mask * 0.30)
    base_g = base_g * (1.0 - moss_mask * 0.16) + 0.24 * (moss_mask * 0.16)
    base_b = base_b * (1.0 - moss_mask * 0.34) + 0.15 * (moss_mask * 0.34)

    # Dusty grey-buff medieval lime mortar (~0.29, 0.27, 0.24) instead of harsh black cartoon lines!
    mortar_r = 0.28 + 0.05 * (n_med - 0.5)
    mortar_g = 0.26 + 0.05 * (n_med - 0.5)
    mortar_b = 0.23 + 0.04 * (n_med - 0.5)

    ao_shade = 0.78 + 0.22 * ao
    albedo = np.ones((H, W, 4), dtype=np.float32)
    albedo[..., 0] = np.clip((base_r * bevel + mortar_r * (1.0 - bevel)) * ao_shade, 0.08, 0.75)
    albedo[..., 1] = np.clip((base_g * bevel + mortar_g * (1.0 - bevel)) * ao_shade, 0.08, 0.75)
    albedo[..., 2] = np.clip((base_b * bevel + mortar_b * (1.0 - bevel)) * ao_shade, 0.07, 0.75)

    rough = np.clip(0.74 + 0.14 * (1.0 - bevel) + 0.10 * (0.5 - n_micro) + 0.05 * streak_dark - 0.05 * block_var, 0.60, 0.95)
    normal = height_to_normal(height, strength=5.4)

    save_image("cathedral_stone_albedo.png", albedo, is_data=False)
    save_image("cathedral_stone_normal.png", normal, is_data=True)
    save_image("cathedral_stone_roughness.png", gray_to_rgba(rough), is_data=True)
    save_image("cathedral_stone_ao.png", gray_to_rgba(ao), is_data=True)


# ==============================================================================
# 2. CATHEDRAL FLOOR (4 maps: Irregular Medieval Slate & Limestone Flagstones — ZERO Checkerboard!)
# ==============================================================================
def generate_cathedral_floor():
    print("Generating Cathedral Floor 2K PBR maps (Irregular Medieval Slate & Limestone Flagstones, ZERO checkerboard)...")
    H, W = SIZE, SIZE
    y = np.linspace(0.0, 1.0, H, endpoint=False, dtype=np.float32)[:, None]
    x = np.linspace(0.0, 1.0, W, endpoint=False, dtype=np.float32)[None, :]

    n_macro = fbm_noise((H, W), [4, 8, 16], [0.50, 0.30, 0.20], seed=211)
    n_vein = fbm_noise((H, W), [10, 24, 48, 96], [0.42, 0.28, 0.18, 0.12], seed=212)
    n_micro = fbm_noise((H, W), [128, 256, 512], [0.45, 0.35, 0.20], seed=213)

    # 10 irregular medieval flagstone courses with varied widths & staggered joints (ZERO diamond grid!)
    row_edges = np.array([0.0, 0.085, 0.195, 0.280, 0.405, 0.495, 0.615, 0.710, 0.835, 0.915, 1.0], dtype=np.float32)
    r_id = np.clip(np.searchsorted(row_edges, y, side='right') - 1, 0, 9).astype(np.int32)
    ry0 = row_edges[r_id]
    ry1 = row_edges[r_id + 1]
    fy = (y - ry0) / (ry1 - ry0 + 1e-6)

    # Within each row, non-uniform stone slab widths via warped cumulative spacing
    slabs_per_row = np.array([5.0, 4.0, 6.0, 3.0, 5.0, 4.0, 6.0, 4.0, 5.0, 3.0], dtype=np.float32)
    row_shift = np.array([0.07, 0.43, 0.71, 0.19, 0.58, 0.84, 0.31, 0.67, 0.14, 0.51], dtype=np.float32)
    n_slabs = slabs_per_row[r_id]

    # Subtle organic width modulation per slab so stones aren't equal-length rectangles
    x_shifted = (x + row_shift[r_id]) % 1.0
    slab_warp = 0.035 * np.sin(x_shifted * 2.0 * math.pi * 2.0 + r_id * 1.7)
    sx = (x_shifted + slab_warp) * n_slabs
    c_id = np.floor(sx).astype(np.int32)
    fx = sx - np.floor(sx)

    # Chipped medieval slab edges + secondary hairline stress cracks across old stones
    wob_x = (n_vein - 0.5) * 0.035 + (n_micro - 0.5) * 0.015
    wob_y = (np.roll(n_vein, 419, axis=1) - 0.5) * 0.045 + (n_micro - 0.5) * 0.018

    dx = np.minimum(fx + wob_x, 1.0 - (fx + wob_x)) / (n_slabs / 4.5)
    dy = np.minimum(fy + wob_y, 1.0 - (fy + wob_y)) * ((ry1 - ry0) * 8.5)
    joint_d = np.minimum(dx, dy)
    grout_mask = smoothstep(0.008, 0.032, joint_d)

    # Secondary Voronoi age fractures cutting across some old flagstones
    v_dist, v_hash = voronoi_cracks(x, y, grid_n=7, jitter=0.85, seed=219, tileable=True)
    hairline_crack = (1.0 - smoothstep(0.004, 0.018, v_dist + (n_vein - 0.5) * 0.03)) * (v_hash > 0.45).astype(np.float32)

    # Per-flagstone natural quarry tone (dark slate ~0.18..0.24 mingled organically with weathered grey-buff stone ~0.24..0.31)
    rng = np.random.default_rng(215)
    tone_table = rng.uniform(0.0, 1.0, size=(16, 16)).astype(np.float32)
    tilt_table = rng.uniform(-0.06, 0.06, size=(16, 16)).astype(np.float32)
    slab_tone = tone_table[r_id % 16, c_id % 16]
    slab_tilt = tilt_table[r_id % 16, c_id % 16]

    vein_wave = np.power(1.0 - np.abs(np.sin((x * 4.0 + y * 5.0 + n_vein * 2.8) * math.pi)), 7.0)

    # Blend organically between cool dark cathedral slate and warm weathered ash-limestone (NO checkerboard!)
    slate_r, slate_g, slate_b = 0.17, 0.18, 0.205
    lime_r, lime_g, lime_b = 0.285, 0.270, 0.240
    mix_f = smoothstep(0.15, 0.85, slab_tone)

    col_r = slate_r * (1.0 - mix_f) + lime_r * mix_f + 0.05 * (n_macro - 0.5) + 0.03 * (n_micro - 0.5) - 0.03 * vein_wave
    col_g = slate_g * (1.0 - mix_f) + lime_g * mix_f + 0.05 * (n_macro - 0.5) + 0.03 * (n_micro - 0.5) - 0.03 * vein_wave
    col_b = slate_b * (1.0 - mix_f) + lime_b * mix_f + 0.045 * (n_macro - 0.5) + 0.03 * (n_micro - 0.5) - 0.025 * vein_wave

    # Damp moss & ash along mortar joints
    joint_moss = np.clip((1.0 - grout_mask) * 0.7 + (1.0 - n_macro) * 0.5 - 0.42, 0.0, 1.0)
    col_r = col_r * (1.0 - joint_moss * 0.35) + 0.13 * (joint_moss * 0.35)
    col_g = col_g * (1.0 - joint_moss * 0.20) + 0.18 * (joint_moss * 0.20)
    col_b = col_b * (1.0 - joint_moss * 0.38) + 0.11 * (joint_moss * 0.38)

    ao = np.clip((0.28 + 0.72 * grout_mask) * (1.0 - 0.42 * hairline_crack) - 0.09 * (1.0 - n_micro), 0.20, 1.0)
    ao_shade = 0.72 + 0.28 * ao

    # Ashen mortar (~0.11, 0.11, 0.10)
    albedo = np.ones((H, W, 4), dtype=np.float32)
    albedo[..., 0] = np.clip((col_r * grout_mask + 0.11 * (1.0 - grout_mask)) * ao_shade * (1.0 - 0.25 * hairline_crack), 0.05, 0.65)
    albedo[..., 1] = np.clip((col_g * grout_mask + 0.11 * (1.0 - grout_mask)) * ao_shade * (1.0 - 0.25 * hairline_crack), 0.05, 0.65)
    albedo[..., 2] = np.clip((col_b * grout_mask + 0.10 * (1.0 - grout_mask)) * ao_shade * (1.0 - 0.25 * hairline_crack), 0.05, 0.65)

    pitting = np.where(n_micro < 0.18, (n_micro - 0.18) * 0.85, 0.0)
    height = grout_mask * (0.78 + slab_tilt + 0.08 * n_vein + 0.05 * n_micro - 0.22 * hairline_crack + pitting)
    normal = height_to_normal(np.clip(height, 0.0, 1.0), strength=5.8)

    # Satin-matte worn cathedral flagstone roughness strictly in [0.54, 0.92]
    rough = (0.62 + 0.10 * (0.5 - n_macro) + 0.08 * (0.5 - n_micro) + 0.12 * hairline_crack) * grout_mask + 0.90 * (1.0 - grout_mask)
    rough = np.clip(rough, 0.54, 0.92)

    save_image("cathedral_floor_albedo.png", albedo, is_data=False)
    save_image("cathedral_floor_normal.png", normal, is_data=True)
    save_image("cathedral_floor_roughness.png", gray_to_rgba(rough), is_data=True)
    save_image("cathedral_floor_ao.png", gray_to_rgba(ao), is_data=True)


# ==============================================================================
# 3. STAINED GLASS (3 maps: Chartres Gothic Rose & Draconic Heraldry)
# ==============================================================================
def generate_stained_glass():
    print("Generating Stained Glass 2K PBR + Emission maps (Chartres Gothic Rose & Draconic Heraldry)...")
    H, W = SIZE, SIZE
    y = np.linspace(-1.0, 1.0, H, dtype=np.float32)[:, None]
    x = np.linspace(-1.0, 1.0, W, dtype=np.float32)[None, :]

    r = np.sqrt(x * x + y * y)
    theta = np.arctan2(y, x)
    ang_pos = theta + math.pi

    n_mottle = fbm_noise((H, W), [12, 28, 64, 128], [0.42, 0.28, 0.18, 0.12], seed=301)
    n_swirl = fbm_noise((H, W), [20, 48, 96], [0.50, 0.30, 0.20], seed=302)

    ring_iron = np.minimum(
        np.minimum(np.abs(r - 0.16), np.abs(r - 0.44)),
        np.minimum(np.abs(r - 0.73), np.abs(r - 0.94)),
    )
    spoke12 = np.abs(np.sin(theta * 6.0)) * r
    spoke12_eff = np.where((r >= 0.155) & (r <= 0.945), spoke12, 1.0)

    spoke24 = np.abs(np.sin(theta * 12.0)) * r
    spoke24_eff = np.where((r >= 0.725) & (r <= 0.945), spoke24, 1.0)

    star_r = 0.095 + 0.036 * np.cos(theta * 6.0)
    oculus_lead = np.where(r < 0.165, np.minimum(np.abs(r - star_r), np.abs(r - 0.042)), 1.0)

    petal12_arch = 0.385 - 0.095 * np.power(1.0 - np.abs(np.cos(theta * 6.0)), 1.35)
    inner_rib = np.abs(r - (0.265 + 0.04 * np.abs(np.cos(theta * 6.0))))
    inner_lead = np.where((r >= 0.16) & (r < 0.44), np.minimum(np.abs(r - petal12_arch), inner_rib * 1.25), 1.0)

    sec12 = np.floor(ang_pos / (math.pi / 6.0))
    med_ang = (sec12 + 0.5) * (math.pi / 6.0) - math.pi
    mx = 0.585 * np.cos(med_ang)
    my = 0.585 * np.sin(med_ang)
    dx_m = x - mx
    dy_m = y - my
    rm = np.sqrt(dx_m * dx_m + dy_m * dy_m)
    phi_m = np.arctan2(dy_m, dx_m) - med_ang
    quat_foil = 0.086 + 0.022 * np.abs(np.cos(phi_m * 2.0))
    med_circle = np.abs(rm - 0.118)
    med_quat = np.abs(rm - quat_foil)
    med_eye = np.abs(rm - 0.032)
    mid_lead = np.where((r >= 0.44) & (r < 0.73), np.minimum(med_circle, np.minimum(med_quat, med_eye)), 1.0)

    cusp24 = 0.895 - 0.065 * np.power(1.0 - np.abs(np.cos(theta * 12.0)), 1.4)
    outer_eye_ang = (np.floor(ang_pos / (math.pi / 12.0)) + 0.5) * (math.pi / 12.0) - math.pi
    ox = 0.825 * np.cos(outer_eye_ang)
    oy = 0.825 * np.sin(outer_eye_ang)
    ro = np.sqrt((x - ox) ** 2 + (y - oy) ** 2)
    outer_lead = np.where((r >= 0.73) & (r < 0.94), np.minimum(np.abs(r - cusp24), np.abs(ro - 0.042)), 1.0)

    qx = np.abs(((x + y) * 7.0) % 1.0 - 0.5) / 7.0
    qy = np.abs(((x - y) * 7.0) % 1.0 - 0.5) / 7.0
    quarry_fine = np.minimum(qx, qy)
    spandrel_lead = np.where(r >= 0.94, quarry_fine * 1.1, quarry_fine * 2.4)

    primary_dist = np.minimum(ring_iron, spoke12_eff)
    secondary_dist = np.minimum(
        np.minimum(oculus_lead, inner_lead),
        np.minimum(np.minimum(mid_lead, outer_lead), np.minimum(spoke24_eff, spandrel_lead)),
    )

    primary_mask = smoothstep(0.0085, 0.0155, primary_dist)
    secondary_mask = smoothstep(0.0050, 0.0105, secondary_dist)
    glass_mask = primary_mask * secondary_mask
    lead_dist = np.minimum(primary_dist, secondary_dist)

    SAPPHIRE = (0.07, 0.23, 0.84)
    RUBY     = (0.84, 0.09, 0.15)
    AMBER    = (0.92, 0.60, 0.11)
    AMETHYST = (0.50, 0.14, 0.74)
    EMERALD  = (0.09, 0.58, 0.30)

    col_r = np.full((H, W), SAPPHIRE[0], dtype=np.float32)
    col_g = np.full((H, W), SAPPHIRE[1], dtype=np.float32)
    col_b = np.full((H, W), SAPPHIRE[2], dtype=np.float32)

    def assign_color(mask, rgb):
        nonlocal col_r, col_g, col_b
        col_r = np.where(mask, rgb[0], col_r)
        col_g = np.where(mask, rgb[1], col_g)
        col_b = np.where(mask, rgb[2], col_b)

    sec12_i = sec12.astype(np.int32) % 12
    sec24_i = (np.floor(ang_pos / (math.pi / 12.0)).astype(np.int32)) % 24

    assign_color(r < 0.16, RUBY)
    assign_color(r < star_r, AMBER)
    assign_color(r < 0.042, RUBY)

    in_b = (r >= 0.16) & (r < 0.44)
    assign_color(in_b & ((sec12_i % 2) == 0), SAPPHIRE)
    assign_color(in_b & ((sec12_i % 2) == 1), RUBY)
    assign_color(in_b & (r > petal12_arch), AMBER)

    in_c = (r >= 0.44) & (r < 0.73)
    assign_color(in_c, SAPPHIRE)
    assign_color(in_c & (rm < 0.118), AMETHYST)
    in_quat = in_c & (rm < quat_foil)
    assign_color(in_quat & ((sec12_i % 3) == 0), RUBY)
    assign_color(in_quat & ((sec12_i % 3) == 1), AMBER)
    assign_color(in_quat & ((sec12_i % 3) == 2), EMERALD)
    assign_color(in_c & (rm < 0.032), AMBER)
    assign_color(in_c & (rm < 0.032) & ((sec12_i % 3) == 1), RUBY)

    in_d = (r >= 0.73) & (r < 0.94)
    assign_color(in_d & ((sec24_i % 4) == 0), SAPPHIRE)
    assign_color(in_d & ((sec24_i % 4) == 1), RUBY)
    assign_color(in_d & ((sec24_i % 4) == 2), AMETHYST)
    assign_color(in_d & ((sec24_i % 4) == 3), EMERALD)
    assign_color(in_d & (r > cusp24), SAPPHIRE)
    assign_color(in_d & (ro < 0.042), AMBER)

    in_e = r >= 0.94
    q_checker = ((np.floor((x + y) * 7.0).astype(np.int32) + np.floor((x - y) * 7.0).astype(np.int32)) % 2) == 0
    assign_color(in_e & q_checker, (0.06, 0.18, 0.68))
    assign_color(in_e & (~q_checker), (0.34, 0.11, 0.54))

    lead_vignette = 0.30 + 0.70 * smoothstep(0.006, 0.042, lead_dist)
    mottle = 0.76 + 0.32 * n_mottle + 0.12 * (n_swirl - 0.5)
    transmittance = np.clip(lead_vignette * mottle, 0.0, 1.08)

    albedo = np.ones((H, W, 4), dtype=np.float32)
    albedo[..., 0] = np.clip(col_r * transmittance * 0.88, 0.0, 0.95) * glass_mask + 0.04 * (1.0 - glass_mask)
    albedo[..., 1] = np.clip(col_g * transmittance * 0.88, 0.0, 0.95) * glass_mask + 0.04 * (1.0 - glass_mask)
    albedo[..., 2] = np.clip(col_b * transmittance * 0.88, 0.0, 0.95) * glass_mask + 0.05 * (1.0 - glass_mask)

    emission = np.ones((H, W, 4), dtype=np.float32)
    emission[..., 0] = np.clip(col_r * transmittance * 1.02, 0.0, 0.98) * glass_mask
    emission[..., 1] = np.clip(col_g * transmittance * 1.02, 0.0, 0.98) * glass_mask
    emission[..., 2] = np.clip(col_b * transmittance * 1.02, 0.0, 0.98) * glass_mask

    rough = np.clip(glass_mask * (0.16 + 0.12 * n_mottle + 0.15 * (1.0 - lead_vignette)) + (1.0 - glass_mask) * 0.72, 0.14, 0.85)

    save_image("stained_glass_albedo.png", albedo, is_data=False)
    save_image("stained_glass_emission.png", emission, is_data=False)
    save_image("stained_glass_roughness.png", gray_to_rgba(rough), is_data=True)


# ==============================================================================
# 4. BOARD FRAME (4 maps: Monolithic Volcanic Dragon-Stone, Crag & Wyrm-Relief)
# ==============================================================================
def generate_board_frame():
    print("Generating Board Frame 2K PBR maps (Monolithic Volcanic Dragon-Basalt & Wyrm-Relief Crag Stone)...")
    H, W = SIZE, SIZE
    y = np.linspace(0.0, 1.0, H, endpoint=False, dtype=np.float32)[:, None]
    x = np.linspace(0.0, 1.0, W, endpoint=False, dtype=np.float32)[None, :]

    n_basalt = fbm_noise((H, W), [8, 16, 48, 96], [0.40, 0.28, 0.20, 0.12], seed=401)
    n_grain = fbm_noise((H, W), [160, 320, 512], [0.45, 0.35, 0.20], seed=402)
    v_crag, _ = voronoi_cracks(x, y, grid_n=9, jitter=0.82, seed=409, tileable=True)
    crag_fissure = 1.0 - smoothstep(0.005, 0.026, v_crag + (n_basalt - 0.5) * 0.03)

    vy = (y * 2.0) % 1.0

    # Imbricated volcanic dragon scales in central band + organic wyrm-interlace & runic stone carving (ZERO bright stripes!)
    in_scales = smoothstep(0.24, 0.30, vy) * smoothstep(0.76, 0.70, vy)
    sc_v = np.clip((vy - 0.26) / 0.48, 0.0, 1.0)
    sc_h, sc_ao = dragon_scales_field(x, sc_v, cols=16.0, rows=3.0)

    in_braid = np.clip(smoothstep(0.18, 0.13, vy) + smoothstep(0.82, 0.87, vy), 0.0, 1.0)
    by_local = np.where(vy < 0.5, vy / 0.17, (1.0 - vy) / 0.17)
    bc = (by_local - 0.5) * 2.0
    phase = x * 20.0 * math.pi
    d1 = np.abs(bc - 0.50 * np.sin(phase))
    d2 = np.abs(bc + 0.50 * np.sin(phase))
    rib1 = smoothstep(0.32, 0.14, d1) * (0.65 + 0.35 * (0.5 + 0.5 * np.cos(phase)))
    rib2 = smoothstep(0.32, 0.14, d2) * (0.65 + 0.35 * (0.5 - 0.5 * np.cos(phase)))
    braid_h = np.maximum(rib1, rib2)

    height = (
        (0.52 + 0.16 * n_basalt + 0.08 * n_grain) * (1.0 - 0.75 * in_scales - 0.75 * in_braid)
        + 0.75 * in_scales * (0.35 + 0.52 * sc_h + 0.08 * n_grain)
        + 0.75 * in_braid * (0.32 + 0.52 * braid_h + 0.06 * n_grain)
        - 0.28 * crag_fissure
    )
    height = np.clip(height, 0.0, 1.0)

    crevice_ao = np.clip(
        ((1.0 - in_scales) + in_scales * sc_ao) * (1.0 - 0.42 * crag_fissure),
        0.24,
        1.0,
    )

    # Dark chiselled volcanic obsidian-basalt (~0.14..0.21) with weathered mineral frost on ridges
    ridge_wear = np.clip((height - 0.62) * 0.28, 0.0, 0.065)
    basalt_r = (0.145 + 0.055 * (n_basalt - 0.5) + 0.03 * (n_grain - 0.5) + ridge_wear) * (0.62 + 0.38 * crevice_ao)
    basalt_g = (0.152 + 0.055 * (n_basalt - 0.5) + 0.03 * (n_grain - 0.5) + ridge_wear) * (0.62 + 0.38 * crevice_ao)
    basalt_b = (0.172 + 0.062 * (n_basalt - 0.5) + 0.035 * (n_grain - 0.5) + ridge_wear * 1.08) * (0.62 + 0.38 * crevice_ao)

    # Subtle weathered dark-bronze mineral flecks ONLY on raised crests (organic, non-striped!)
    bronze_fleck = np.clip((height - 0.72) * 2.2, 0.0, 1.0) * smoothstep(0.58, 0.78, n_basalt) * 0.35

    albedo = np.ones((H, W, 4), dtype=np.float32)
    albedo[..., 0] = np.clip(basalt_r * (1.0 - bronze_fleck) + 0.34 * bronze_fleck, 0.04, 0.55)
    albedo[..., 1] = np.clip(basalt_g * (1.0 - bronze_fleck) + 0.26 * bronze_fleck, 0.04, 0.55)
    albedo[..., 2] = np.clip(basalt_b * (1.0 - bronze_fleck) + 0.16 * bronze_fleck, 0.05, 0.55)

    rough = np.clip(0.66 + 0.14 * (1.0 - crevice_ao) + 0.08 * (0.5 - n_grain) - 0.10 * bronze_fleck, 0.54, 0.88)
    metallic = bronze_fleck * (0.45 + 0.10 * n_grain)
    normal = height_to_normal(height, strength=6.6)

    save_image("board_frame_albedo.png", albedo, is_data=False)
    save_image("board_frame_normal.png", normal, is_data=True)
    save_image("board_frame_roughness.png", gray_to_rgba(rough), is_data=True)
    save_image("board_frame_metallic.png", gray_to_rgba(metallic), is_data=True)


# ==============================================================================
# 5. BOARD TILES -> CENTRAL DRAGON SANCTUM RITUAL FLOOR & ARCANE MAGIC CIRCLE!
#    (5 maps: ZERO 8x8 checkerboard! Cracked Basalt-Limestone + Elder Summoning Seal!)
# ==============================================================================
def generate_board_tiles():
    print("Generating Sanctum Altar Ritual Floor & Elder Draconic Magic Circle 2K PBR + AO maps (ZERO checkerboard)...")
    H, W = SIZE, SIZE
    y = np.linspace(0.0, 1.0, H, endpoint=False, dtype=np.float32)[:, None]
    x = np.linspace(0.0, 1.0, W, endpoint=False, dtype=np.float32)[None, :]

    cx = x - 0.5
    cy = y - 0.5
    r = np.sqrt(cx * cx + cy * cy)
    theta = np.arctan2(cy, cx)  # [-pi, pi]
    ang_pos = theta + math.pi   # [0, 2*pi]

    n_macro = fbm_noise((H, W), [4, 8, 16], [0.50, 0.30, 0.20], seed=511)
    n_med = fbm_noise((H, W), [20, 40, 80], [0.48, 0.32, 0.20], seed=512)
    n_micro = fbm_noise((H, W), [160, 320, 512], [0.45, 0.35, 0.20], seed=513)

    # --- A. Ancient Cracked Polygonal & Radial Temple Stone Flagstones (ZERO 8x8 grid!) ---
    # Combine Voronoi irregular polygonal slabs with weathered concentric temple ring joints
    v_edge1, v_hash1 = voronoi_cracks(x, y, grid_n=13, jitter=0.84, seed=521, tileable=False)
    v_edge2, v_hash2 = voronoi_cracks(x, y, grid_n=6, jitter=0.88, seed=522, tileable=False)

    wob_v = (n_med - 0.5) * 0.038 + (n_micro - 0.5) * 0.015
    poly_joint = smoothstep(0.010, 0.038, v_edge1 + wob_v)

    # Concentric ancient temple masonry ring seams around the altar center
    r_warped = r + (n_med - 0.5) * 0.0045
    temple_rings = np.minimum(
        np.minimum(np.abs(r_warped - 0.165), np.abs(r_warped - 0.295)),
        np.abs(r_warped - 0.485),
    )
    ring_seam = smoothstep(0.0018, 0.0055, temple_rings)
    slab_mask = poly_joint * ring_seam

    # --- B. Radial Battle-Fracture Cracks & Scorched Dragon-Claw Gouges ---
    # 7 jagged impact fracture fissures radiating from battle impact zones
    fracture = np.zeros((H, W), dtype=np.float32)
    crack_specs = [
        (0.00, 0.00,  0.38, 0.49),
        (0.00, 0.00, -2.15, 0.48),
        (0.00, 0.00,  1.85, 0.46),
        (0.18, -0.14, 0.92, 0.34),
        (-0.20, 0.16, -0.78, 0.36),
        (0.12, 0.22,  2.55, 0.30),
        (-0.16, -0.20, -2.85, 0.32),
    ]
    for ox_c, oy_c, ang_c, len_c in crack_specs:
        bx_c = ox_c + len_c * math.cos(ang_c)
        by_c = oy_c + len_c * math.sin(ang_c)
        # Warp coordinates with multi-scale noise for jagged lightning-like stone cracks
        wx_p = cx + (n_med - 0.5) * 0.032 + (n_micro - 0.5) * 0.009
        wy_p = cy + (np.roll(n_med, 337, axis=0) - 0.5) * 0.032 + (n_micro - 0.5) * 0.009
        d_seg = segment_sdf(wx_p, wy_p, ox_c, oy_c, bx_c, by_c)
        fracture = np.maximum(fracture, 1.0 - smoothstep(0.0012, 0.0052, d_seg))

    # Scorched parallel 3-talon Dragon-Claw Gouges scarred into the stone slabs!
    claw_gouge = np.zeros((H, W), dtype=np.float32)
    claw_sets = [
        (-0.24, -0.12, 0.62, 0.16),
        ( 0.22,  0.15, -2.42, 0.15),
        (-0.14,  0.26, -0.48, 0.14),
        ( 0.26, -0.22,  2.18, 0.15),
    ]
    for gx0, gy0, g_ang, g_len in claw_sets:
        ca, sa = math.cos(g_ang), math.sin(g_ang)
        px_na, py_na = -sa, ca
        for talon_i in (-1.0, 0.0, 1.0):
            sx0 = gx0 + px_na * (talon_i * 0.016)
            sy0 = gy0 + py_na * (talon_i * 0.016)
            sx1 = sx0 + ca * g_len
            sy1 = sy0 + sa * g_len
            # Slight talon curve via noise
            d_claw = segment_sdf(cx + (n_micro - 0.5) * 0.004, cy + (n_micro - 0.5) * 0.004, sx0, sy0, sx1, sy1)
            taper = smoothstep(g_len * 0.55, 0.0, np.sqrt((cx - 0.5 * (sx0 + sx1)) ** 2 + (cy - 0.5 * (sy0 + sy1)) ** 2))
            claw_gouge = np.maximum(claw_gouge, (1.0 - smoothstep(0.0010, 0.0042, d_claw)) * taper)

    # --- C. Monumental Carved Elder Draconic Summoning Magic Circle at (0.5, 0.5) ---
    # 1. Concentric Engraved Ward Rings (spanning r = 0.048 out to r = 0.468 -> ~9.3m diameter!)
    d_rings_major = np.minimum(
        np.minimum(np.abs(r - 0.468), np.abs(r - 0.408)),
        np.minimum(np.abs(r - 0.282), np.abs(r - 0.142)),
    )
    d_rings_minor = np.minimum(
        np.minimum(np.abs(r - 0.456), np.abs(r - 0.420)),
        np.minimum(np.abs(r - 0.268), np.minimum(np.abs(r - 0.128), np.abs(r - 0.052))),
    )
    ring_groove = np.maximum(
        1.0 - smoothstep(0.0018, 0.0048, d_rings_major),
        0.85 * (1.0 - smoothstep(0.0012, 0.0034, d_rings_minor)),
    )

    # 2. 8-Pointed Draconic Astrolabe Octagram ({8/3} star chords inscribed in R = 0.408) + 8 Compass Rays
    R_oct = 0.408
    oct_dist = np.full((H, W), 1e9, dtype=np.float32)
    ray_dist = np.full((H, W), 1e9, dtype=np.float32)
    sat_dist = np.full((H, W), 1e9, dtype=np.float32)

    for k in range(8):
        a0 = k * (math.pi * 0.25)
        a1 = (k + 3) * (math.pi * 0.25)
        oct_dist = np.minimum(
            oct_dist,
            segment_sdf(cx, cy, R_oct * math.cos(a0), R_oct * math.sin(a0), R_oct * math.cos(a1), R_oct * math.sin(a1)),
        )
        # Compass astrolabe ray from r = 0.052 to r = 0.468
        ray_dist = np.minimum(
            ray_dist,
            segment_sdf(cx, cy, 0.052 * math.cos(a0), 0.052 * math.sin(a0), 0.468 * math.cos(a0), 0.468 * math.sin(a0)),
        )
        # 8 Satellite Draconic Locus Circles at r = 0.342 along the 8 star tips/valleys
        asat = (k + 0.5) * (math.pi * 0.25)
        sx_c, sy_c = 0.342 * math.cos(asat), 0.342 * math.sin(asat)
        rs = np.sqrt((cx - sx_c) ** 2 + (cy - sy_c) ** 2)
        sat_dist = np.minimum(sat_dist, np.minimum(np.abs(rs - 0.038), np.abs(rs - 0.016)))

    astrolabe_groove = np.maximum(
        1.0 - smoothstep(0.0016, 0.0044, oct_dist),
        np.maximum(
            0.85 * (1.0 - smoothstep(0.0012, 0.0036, ray_dist)),
            0.90 * (1.0 - smoothstep(0.0014, 0.0038, sat_dist)),
        ),
    )

    # 3. Outer Ring of 36 Elder Draconic Rune Glyphs (r in [0.422, 0.454]) + Inner Ring of 24 Glyphs (r in [0.244, 0.266])
    def elder_rune_band(r_in, r_out, count):
        in_band = smoothstep(r_in, r_in + 0.003, r) * smoothstep(r_out, r_out - 0.003, r)
        u_ang = (ang_pos / (2.0 * math.pi)) * count
        g_id = np.floor(u_ang).astype(np.int32) % 6
        fu = u_ang - np.floor(u_ang)              # [0, 1) angular cell
        fv = np.clip((r - r_in) / (r_out - r_in), 0.0, 1.0)  # [0, 1) radial cell

        box = smoothstep(0.14, 0.22, fu) * smoothstep(0.86, 0.78, fu) * smoothstep(0.10, 0.18, fv) * smoothstep(0.90, 0.82, fv)
        stave1 = np.exp(-((fu - 0.30) / 0.055) ** 2)
        stave2 = np.where((g_id % 2) == 0, np.exp(-((fu - 0.70) / 0.055) ** 2), 0.0)
        slash1 = np.exp(-(((fv - 0.5) - (fu - 0.5) * 1.15) / 0.072) ** 2)
        slash2 = np.exp(-(((fv - 0.5) + (fu - 0.5) * 1.15) / 0.072) ** 2)
        chev = np.exp(-((np.abs(fv - 0.55) - np.abs(fu - 0.5) * 0.9) / 0.065) ** 2)
        branches = np.where(g_id < 2, slash1, np.where(g_id < 4, slash2, chev))
        return np.clip((stave1 + stave2 + branches) * box, 0.0, 1.0) * in_band

    runes_outer = elder_rune_band(0.422, 0.454, 36.0)
    runes_inner = elder_rune_band(0.236, 0.264, 24.0)

    # Central Draconic Eye / Compass Rose Seal inside r < 0.128
    star_center = 0.088 + 0.028 * np.cos(theta * 4.0)
    center_seal = np.where(r < 0.13, 1.0 - smoothstep(0.0014, 0.0040, np.abs(r - star_center)), 0.0)

    magic_circle = np.clip(
        np.maximum(np.maximum(ring_groove, astrolabe_groove), np.maximum(np.maximum(runes_outer, runes_inner), center_seal)),
        0.0,
        1.0,
    )
    # Raised patinated bronze astrolabe rim fillets flanking the main rings
    bronze_rim = (
        np.exp(-((np.abs(r - 0.473)) / 0.0022) ** 2)
        + np.exp(-((np.abs(r - 0.287)) / 0.0020) ** 2)
        + np.exp(-((np.abs(r - 0.146)) / 0.0018) ** 2)
    )
    bronze_rim = np.clip(bronze_rim, 0.0, 1.0) * slab_mask

    # --- D. Stone Albedo + Subtle Glowing Icy-Cyan & Molten-Gold Arcane Ley-Line Veins ---
    # Weathered dark volcanic-basalt & ancient temple-limestone (~0.17..0.28) so BOTH White & Black stone dragons pop!
    slab_var = (v_hash1 - 0.5) * 0.055 + (v_hash2 - 0.5) * 0.035
    stone_r = 0.215 + slab_var + 0.045 * (n_macro - 0.5) + 0.030 * (n_med - 0.5) + 0.020 * (n_micro - 0.5)
    stone_g = 0.212 + slab_var * 0.95 + 0.045 * (n_macro - 0.5) + 0.030 * (n_med - 0.5) + 0.020 * (n_micro - 0.5)
    stone_b = 0.222 + slab_var * 0.90 + 0.048 * (n_macro - 0.5) + 0.032 * (n_med - 0.5) + 0.022 * (n_micro - 0.5)

    # Outer edge darkening toward the jagged basalt crags (r > 0.46)
    rim_ash = smoothstep(0.42, 0.58, r) * 0.28
    stone_r *= (1.0 - rim_ash)
    stone_g *= (1.0 - rim_ash)
    stone_b *= (1.0 - rim_ash * 0.90)

    # Scorched soot darkening around dragon-claw gouges & battle fractures
    scorch = np.clip(0.55 * claw_gouge + 0.35 * fracture, 0.0, 0.70)
    stone_r *= (1.0 - scorch)
    stone_g *= (1.0 - scorch)
    stone_b *= (1.0 - scorch)

    # Blend patinated antique bronze astrolabe rims
    stone_r = stone_r * (1.0 - bronze_rim * 0.75) + 0.48 * (bronze_rim * 0.75)
    stone_g = stone_g * (1.0 - bronze_rim * 0.75) + 0.37 * (bronze_rim * 0.75)
    stone_b = stone_b * (1.0 - bronze_rim * 0.75) + 0.19 * (bronze_rim * 0.75)

    # Dual-aspect Arcane Ley-Line Glow inside carved magic-circle channels:
    # Interwoven Icy-Cyan (celestial ward) & Molten-Gold (draconic fire) harmonic pulse!
    ley_pulse = 0.68 + 0.32 * n_med
    harmonic = 0.5 + 0.5 * np.sin(theta * 4.0 + r * 22.0)
    # Outer rune ring & octagram lean warm molten-gold; inner runes, satellite loci & compass rays lean icy-cyan!
    cyan_weight = np.clip(0.65 * runes_inner + 0.75 * (1.0 - smoothstep(0.0014, 0.0038, sat_dist)) + 0.45 * harmonic, 0.0, 1.0)
    ley_r = (0.94 * (1.0 - cyan_weight) + 0.18 * cyan_weight) * ley_pulse
    ley_g = (0.58 * (1.0 - cyan_weight) + 0.78 * cyan_weight) * ley_pulse
    ley_b = (0.14 * (1.0 - cyan_weight) + 0.98 * cyan_weight) * ley_pulse

    arcane_intensity = np.clip(magic_circle * (0.52 + 0.28 * n_macro), 0.0, 0.78)

    ao = np.clip(
        (0.24 + 0.76 * slab_mask) * (1.0 - 0.55 * fracture) * (1.0 - 0.50 * claw_gouge) * (1.0 - 0.28 * magic_circle)
        - 0.08 * (1.0 - n_micro),
        0.14,
        1.0,
    )
    ao_shade = 0.68 + 0.32 * ao

    base_r = (stone_r * slab_mask + 0.08 * (1.0 - slab_mask)) * ao_shade
    base_g = (stone_g * slab_mask + 0.08 * (1.0 - slab_mask)) * ao_shade
    base_b = (stone_b * slab_mask + 0.09 * (1.0 - slab_mask)) * ao_shade

    albedo = np.ones((H, W, 4), dtype=np.float32)
    albedo[..., 0] = np.clip(base_r * (1.0 - arcane_intensity) + ley_r * arcane_intensity, 0.04, 0.92)
    albedo[..., 1] = np.clip(base_g * (1.0 - arcane_intensity) + ley_g * arcane_intensity, 0.04, 0.92)
    albedo[..., 2] = np.clip(base_b * (1.0 - arcane_intensity) + ley_b * arcane_intensity, 0.05, 0.96)

    pitting = np.where(n_micro < 0.19, (n_micro - 0.19) * 0.75, 0.0)
    height = (
        slab_mask * (0.82 + (v_hash1 - 0.5) * 0.08 + 0.06 * n_med + 0.04 * n_micro + pitting)
        - 0.34 * fracture
        - 0.30 * claw_gouge
        - 0.22 * magic_circle
        + 0.05 * bronze_rim
    )
    normal = height_to_normal(np.clip(height, 0.0, 1.0), strength=6.2)

    # Satin-matte weathered stone roughness in [0.48, 0.90] (slightly smoother inside glassy arcane rune channels)
    rough_stone = 0.64 + 0.10 * (0.5 - n_micro) + 0.08 * (0.5 - n_macro) + 0.14 * fracture + 0.12 * claw_gouge
    rough = rough_stone * (1.0 - 0.30 * magic_circle) * (1.0 - 0.22 * bronze_rim)
    rough = rough * slab_mask + 0.90 * (1.0 - slab_mask)
    rough = np.clip(rough, 0.48, 0.92)

    metallic = np.clip(bronze_rim * 0.62 + magic_circle * 0.12, 0.0, 0.70)

    save_image("board_tiles_albedo.png", albedo, is_data=False)
    save_image("board_tiles_normal.png", normal, is_data=True)
    save_image("board_tiles_roughness.png", gray_to_rgba(rough), is_data=True)
    save_image("board_tiles_metallic.png", gray_to_rgba(metallic), is_data=True)
    save_image("board_tiles_ao.png", gray_to_rgba(ao), is_data=True)


def generate_all_textures():
    generate_cathedral_stone()
    generate_cathedral_floor()
    generate_stained_glass()
    generate_board_frame()
    generate_board_tiles()
    print(f"All 20 2K ({SIZE}x{SIZE}) PBR Dragon-Sanctum textures generated successfully in {TEXTURES_DIR}")


if __name__ == "__main__":
    generate_all_textures()
