"""
Procedural 2K (2048x2048) Dragon-Stonework PBR Texture & Material Generator.

Generates 12 deterministic 2048x2048 PNG maps in TEXTURES_DIR:
  - white_piece_{albedo,normal,roughness,metallic,ao,emission}.png
  - black_piece_{albedo,normal,roughness,metallic,ao,emission}.png

All maps use the symmetric vertical coordinate `s = 0.5 - abs(v - 0.5)` so both
`flipY=True` and `flipY=False` align strictly with `dragon_spec.py` UV zones:
  1. UV_ZONE_SCALES (s in [0.34, 0.50]): Carved rounded-ogive dragon osteoderm stone scales
  2. UV_ZONE_STONE  (s in [0.19, 0.33]): Granular weathered Caen limestone / volcanic basalt
  3. UV_ZONE_RUNES  (s in [0.10, 0.18]): Recessed Elder Draconic Runes & Wyrm Knotwork frieze
  4. UV_ZONE_BRONZE (s in [0.01, 0.09]): Aged, heavily patinated dark draconic stone-bronze inlay
"""

import math
import os
import struct
import sys
import zlib
import numpy as np
import bpy

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from dragon_spec import (
    TEXTURES_DIR,
    TEXTURE_SIZE,
)


def _save_png_uint8(filepath: str, arr: np.ndarray) -> None:
    """
    Deterministic, zero-dependency 8-bit PNG writer (Grayscale HxW or RGB HxWx3).
    """
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    if arr.ndim == 2:
        h, w = arr.shape
        color_type = 0
        raw_rows = np.concatenate(
            [np.zeros((h, 1), dtype=np.uint8), arr], axis=1
        ).tobytes()
    elif arr.ndim == 3 and arr.shape[2] == 3:
        h, w, _ = arr.shape
        color_type = 2
        reshaped = arr.reshape(h, w * 3)
        raw_rows = np.concatenate(
            [np.zeros((h, 1), dtype=np.uint8), reshaped], axis=1
        ).tobytes()
    else:
        raise ValueError(f"Unsupported PNG array shape: {arr.shape}")

    def _chunk(ctype: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(ctype + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + ctype + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", w, h, 8, color_type, 0, 0, 0)
    compressed = zlib.compress(raw_rows, level=4)

    with open(filepath, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(_chunk(b"IHDR", ihdr))
        f.write(_chunk(b"IDAT", compressed))
        f.write(_chunk(b"IEND", b""))


def _smoothstep(edge0: float, edge1: float, x: np.ndarray) -> np.ndarray:
    t = np.clip((x - edge0) / max(edge1 - edge0, 1e-6), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _cell_clast_noise(u: np.ndarray, s: np.ndarray, freq_u: float, freq_s: float, seed: float) -> np.ndarray:
    """
    Smooth bilinearly-interpolated deterministic mineral-clast / sandstone grit noise
    (periodic in U with period 1.0, symmetric in S, zero closed-loop isoline artifacts).
    """
    gu = u * np.float32(freq_u)
    gs = s * np.float32(freq_s)
    iu0 = np.floor(gu)
    is0 = np.floor(gs)
    fu = gu - iu0
    fs = gs - is0
    su = fu * fu * (np.float32(3.0) - np.float32(2.0) * fu)
    ss = fs * fs * (np.float32(3.0) - np.float32(2.0) * fs)

    fu_mod = np.float32(freq_u)

    def _h(ix: np.ndarray, iy: np.ndarray) -> np.ndarray:
        wx = np.mod(ix, fu_mod)
        raw = np.sin(wx * np.float32(127.1) + iy * np.float32(311.7) + np.float32(seed)) * np.float32(43758.5453)
        return (raw - np.floor(raw)).astype(np.float32)

    c00 = _h(iu0, is0)
    c10 = _h(iu0 + 1.0, is0)
    c01 = _h(iu0, is0 + 1.0)
    c11 = _h(iu0 + 1.0, is0 + 1.0)

    nx0 = c00 + su * (c10 - c00)
    nx1 = c01 + su * (c11 - c01)
    return (nx0 + ss * (nx1 - nx0)) * np.float32(2.0) - np.float32(1.0)


def synthesize_dragon_piece_pbr(res: int = TEXTURE_SIZE) -> dict[str, str]:
    """
    Synthesize all 12 deterministic 2K Dragon-Stonework PBR PNG textures for
    White (carved Cathedral Caen wyrm-limestone + soulfire runes) and Black
    (carved volcanic dragon-basalt + dry-brushed ash-grey scale ridges + magma runes).
    """
    print(f"[DragonPBR] Synthesizing 12 deterministic {res}x{res} Dragon-Stonework PBR maps (Pass 2)...")
    u = np.linspace(0.0, 1.0, res, endpoint=False, dtype=np.float32)[None, :]
    v = np.linspace(0.0, 1.0, res, endpoint=True, dtype=np.float32)[:, None]

    # Symmetric vertical coordinate s in [0.0, 0.5]
    s = (0.5 - np.abs(v - 0.5)).astype(np.float32)
    two_pi = np.float32(2.0 * math.pi)

    # ==========================================================================
    # MULTI-SCALE GRANULAR MINERAL CLAST & STONE GRAIN NOISE (ZERO SQUIGGLE LOOPS)
    # ==========================================================================
    n_macro = _cell_clast_noise(u, s, 12.0, 18.0, 1.73)
    n_med = (
        0.60 * _cell_clast_noise(u, s, 28.0, 42.0, 5.19)
        + 0.40 * _cell_clast_noise(u, s, 56.0, 84.0, 11.41)
    ).astype(np.float32)
    n_fine = (
        0.58 * _cell_clast_noise(u, s, 128.0, 192.0, 23.87)
        + 0.42 * _cell_clast_noise(u, s, 256.0, 384.0, 41.29)
    ).astype(np.float32)

    # Ultra-fine sandstone / basalt crystal sparkle & mason stipple
    micro_grain = (
        0.55 * _cell_clast_noise(u, s, 420.0, 520.0, 67.3)
        + 0.45 * np.sin(two_pi * (211.0 * u + 238.0 * s + 0.25 * n_fine))
        * np.cos(two_pi * (263.0 * u - 244.0 * s))
    ).astype(np.float32)

    # Porous travertine / vesicular basalt stone pits (localized pores, no loops)
    pit_field = 0.55 * _cell_clast_noise(u, s, 160.0, 220.0, 89.1) + 0.45 * _cell_clast_noise(u, s, 320.0, 440.0, 103.7)
    stone_pits = (_smoothstep(0.46, 0.86, pit_field) ** 2).astype(np.float32)

    # ==========================================================================
    # PARTITION OF UNITY FOR THE 4 SYMMETRIC UV ZONES
    #   Bronze : s in [0.000, 0.095)  -> covers UV_ZONE_BRONZE [0.01, 0.09]
    #   Runes  : s in [0.095, 0.185)  -> covers UV_ZONE_RUNES  [0.10, 0.18]
    #   Stone  : s in [0.185, 0.336)  -> covers UV_ZONE_STONE  [0.19, 0.33]
    #   Scales : s in [0.336, 0.500]  -> covers UV_ZONE_SCALES [0.34, 0.50]
    # ==========================================================================
    t_b_r = _smoothstep(0.092, 0.098, s)
    t_r_st = _smoothstep(0.182, 0.188, s)
    t_st_sc = _smoothstep(0.333, 0.339, s)

    z_bronze = (1.0 - t_b_r).astype(np.float32)
    z_runes = np.maximum(0.0, t_b_r - t_r_st).astype(np.float32)
    z_stone = np.maximum(0.0, t_r_st - t_st_sc).astype(np.float32)
    z_scales = t_st_sc.astype(np.float32)

    band_groove = (
        np.exp(-28000.0 * ((s - 0.095) ** 2))
        + np.exp(-28000.0 * ((s - 0.185) ** 2))
        + np.exp(-28000.0 * ((s - 0.336) ** 2))
    ).astype(np.float32)

    # ==========================================================================
    # ZONE 1: UV_ZONE_SCALES — ROUNDED-OGIVE CARVED DRAGON OSTEODERM SCALES
    # ==========================================================================
    freq_u = np.float32(16.0)   # 16 monumental carved stone osteoderms around circumference
    freq_s = np.float32(34.0)   # Staggered overlapping tiers across s in [0.34, 0.50]

    # Hand-chiselled edge irregularity & weathered stone chips along scale rims
    edge_chips = (0.026 * n_med + 0.022 * n_fine + 0.012 * micro_grain).astype(np.float32)
    s_sc = s * freq_s + 0.022 * n_macro
    u_sc = u * freq_u + 0.012 * n_med
    j_base = np.floor(s_sc)

    scale_d_edge = np.zeros((res, res), dtype=np.float32)
    scale_ax = np.zeros((res, res), dtype=np.float32)
    scale_ly = np.zeros((res, res), dtype=np.float32)
    scale_hash = np.zeros((res, res), dtype=np.float32)
    under_overlap_shadow = np.zeros((res, res), dtype=np.float32)

    for dj in (1, 0, -1):
        j_row = j_base + np.float32(dj)
        row_shift = np.mod(j_row, 2.0) * np.float32(0.5)
        u_shifted = u_sc + row_shift
        col_idx = np.mod(np.floor(u_shifted), freq_u)
        lx = (u_shifted - np.floor(u_shifted)) - np.float32(0.5)
        ax = np.clip(np.abs(lx) * np.float32(2.0), 0.0, 1.35)
        ly = s_sc - j_row

        # Rounded-ogive Gothic shield-boss / dragon osteoderm profile (ax ** 1.70)
        tip_y = np.float32(1.32) - np.float32(0.68) * (ax ** np.float32(1.70)) + edge_chips
        d_edge = tip_y - ly

        if dj < 1:
            # Broad, soft cast step-shadow beneath overlapping osteoderm rim
            outside_shadow = (
                np.exp(-24.0 * (d_edge ** 2))
                * ((d_edge < 0.0) & (d_edge > -0.32)).astype(np.float32)
            )
            under_overlap_shadow = np.maximum(under_overlap_shadow, outside_shadow)

        mask = (d_edge >= 0.0) if dj < 1 else np.ones((res, res), dtype=bool)
        cell_h = np.mod(np.sin(col_idx * 12.9898 + j_row * 78.233) * 43758.5453, 1.0).astype(np.float32)

        scale_d_edge = np.where(mask, d_edge, scale_d_edge)
        scale_ax = np.where(mask, ax, scale_ax)
        scale_ly = np.where(mask, ly, scale_ly)
        scale_hash = np.where(mask, cell_h, scale_hash)

    # Broad chiselled mortar groove & under-scale overlap pocket (no razor-thin ink line)
    scale_crevice = np.clip(
        0.65 * np.exp(-55.0 * (scale_d_edge ** 2)) + 0.55 * under_overlap_shadow,
        0.0,
        1.0,
    ).astype(np.float32)

    # Generous 3D chiselled stone chamfer + convex 3D pillowed osteoderm dome + faceted roof!
    scale_rim_ramp = _smoothstep(0.0, 0.24, scale_d_edge)
    scale_dome = (
        _smoothstep(0.015, 0.26, scale_d_edge)
        * np.clip(1.0 - 0.82 * (scale_ax ** 1.65), 0.0, 1.0)
        * np.clip(1.18 - 0.36 * scale_ly, 0.32, 1.0)
    ).astype(np.float32)

    # Bold 3D gable/facet roof slope across the entire osteoderm so left/right halves catch 3D directional light
    scale_facet_roof = (
        _smoothstep(0.01, 0.20, scale_d_edge)
        * np.clip(1.0 - 0.88 * scale_ax, 0.0, 1.0)
        * np.clip(1.15 - 0.32 * scale_ly, 0.35, 1.0)
    ).astype(np.float32)

    # Crisp weathered bevel lip & central dorsal dragon-scale keel ridge
    scale_bevel_lip = (
        np.exp(-135.0 * ((scale_d_edge - 0.175) ** 2))
        * (1.0 - 0.22 * scale_ax)
        * (0.82 + 0.30 * _smoothstep(-0.3, 0.5, n_fine))
    ).astype(np.float32)

    scale_keel = (
        np.exp(-14.0 * (scale_ax ** 2))
        * _smoothstep(0.025, 0.18, scale_d_edge)
        * np.clip(1.18 - 0.34 * scale_ly, 0.32, 1.0)
    ).astype(np.float32)

    # Subtle diagonal mason tool marks & chipped rim pits
    chisel_dir = np.where(scale_hash > 0.5, np.float32(1.0), np.float32(-1.0))
    chisel_phase = two_pi * (88.0 * u + chisel_dir * 66.0 * s + 0.22 * n_fine)
    scale_chisel = (
        ((0.5 + 0.5 * np.sin(chisel_phase)) ** 3)
        * scale_rim_ramp
        * (1.0 - 0.45 * scale_keel)
    ).astype(np.float32)

    rim_chip_pits = (
        _smoothstep(0.25, 0.78, n_fine)
        * np.exp(-140.0 * ((scale_d_edge - 0.08) ** 2))
    ).astype(np.float32)

    # Strong macro 3D relief across the entire osteoderm dome, gable facet, chamfer & keel
    h_scales = (
        0.92 * scale_rim_ramp
        + 0.85 * scale_dome
        + 0.78 * scale_facet_roof
        + 0.68 * scale_keel
        + 0.20 * scale_bevel_lip
        - 0.34 * scale_crevice
        - 0.10 * rim_chip_pits
        - 0.045 * scale_chisel
        - 0.070 * stone_pits
        + 0.085 * (scale_hash - 0.5) * scale_rim_ramp
        + 0.038 * n_fine
        + 0.022 * micro_grain
    ).astype(np.float32)

    ao_scales = np.clip(
        1.0
        - 0.48 * scale_crevice
        - 0.18 * (1.0 - scale_rim_ramp)
        - 0.08 * stone_pits
        - 0.06 * rim_chip_pits
        + 0.10 * (scale_keel + 0.5 * scale_dome),
        0.30,
        1.0,
    ).astype(np.float32)

    # ==========================================================================
    # ZONE 2: UV_ZONE_STONE — GRANULAR CARVED LIMESTONE & BASALT (NO SQUIGGLE LOOPS!)
    # ==========================================================================
    # Horizontal ashlar / sedimentary stone bedding & subtle carved fluting
    bedding = (
        0.5 + 0.5 * np.sin(two_pi * (22.0 * s + 0.18 * n_macro + 0.09 * n_med))
    ).astype(np.float32)

    # Bush-hammer / mason point-chisel stipple across carved stone blocks, horns, and wings
    stipple = (
        _smoothstep(0.15, 0.80, 0.5 + 0.5 * _cell_clast_noise(u, s, 192.0, 256.0, 149.3))
    ).astype(np.float32)

    # Strictly GATED short hairline stone micro-chips (never forming closed loops!)
    chip_gate = _smoothstep(0.56, 0.86, 0.5 + 0.5 * n_macro) * _smoothstep(0.48, 0.82, 0.5 + 0.5 * n_med)
    chip_line = np.exp(-95.0 * (np.sin(two_pi * (9.0 * u - 11.0 * s) + 1.15 * n_med + 0.45 * n_fine) ** 2))
    gated_micro_chips = (chip_line * chip_gate).astype(np.float32)

    # Natural mineral clast ridges for dry-brush edge catching
    stone_ridge = np.clip(
        0.45 * _smoothstep(0.15, 0.72, n_med)
        + 0.35 * _smoothstep(0.20, 0.78, n_fine)
        + 0.25 * bedding,
        0.0,
        1.0,
    ).astype(np.float32)

    stone_pocket = np.clip(
        0.50 * stone_pits
        + 0.35 * gated_micro_chips
        + 0.25 * _smoothstep(0.25, 0.78, -n_med),
        0.0,
        1.0,
    ).astype(np.float32)

    h_stone = (
        0.12 * bedding
        + 0.14 * n_med
        + 0.08 * n_fine
        - 0.26 * gated_micro_chips
        - 0.15 * stone_pits
        - 0.055 * stipple
        + 0.032 * micro_grain
    ).astype(np.float32)

    ao_stone = np.clip(
        1.0 - 0.38 * gated_micro_chips - 0.26 * stone_pits - 0.12 * _smoothstep(0.15, 0.75, -n_med),
        0.34,
        1.0,
    ).astype(np.float32)

    # ==========================================================================
    # ZONE 3: UV_ZONE_RUNES — CARVED FRIEZE WITH ELDER DRACONIC RUNES & KNOTWORK
    # ==========================================================================
    s_rune_c = np.float32(0.140)
    dy_r = (s - s_rune_c) / np.float32(0.038)

    braid_a = np.abs(dy_r) - (0.84 + 0.055 * np.sin(two_pi * 32.0 * u))
    braid_b = np.abs(dy_r) - (0.84 - 0.055 * np.sin(two_pi * 32.0 * u))
    knot_cord = np.clip(
        np.exp(-420.0 * (braid_a ** 2)) + np.exp(-420.0 * (braid_b ** 2)),
        0.0,
        1.0,
    ).astype(np.float32)

    u16 = u * np.float32(16.0)
    cell_id = np.mod(np.floor(u16), 4.0)
    cx = (u16 - np.floor(u16) - np.float32(0.5)) * np.float32(2.0)
    cy = np.clip(dy_r / np.float32(0.68), -1.4, 1.4)
    in_box = ((np.abs(cx) < 0.62) & (np.abs(cy) < 0.86)).astype(np.float32)

    g0 = np.clip(
        np.exp(-150.0 * (cx ** 2))
        + np.exp(-140.0 * ((cy - 0.95 * np.abs(cx) - 0.05) ** 2)) * (cy > -0.05).astype(np.float32)
        + np.exp(-160.0 * ((np.abs(cx) + np.abs(cy + 0.35) - 0.34) ** 2)),
        0.0,
        1.0,
    )
    g1 = np.clip(
        np.exp(-145.0 * ((cy - 1.10 * cx) ** 2))
        + np.exp(-145.0 * ((cy + 1.10 * cx) ** 2))
        + np.exp(-160.0 * ((np.abs(cx) + np.abs(cy - 0.28) - 0.36) ** 2))
        + np.exp(-170.0 * ((np.abs(cx) - 0.46) ** 2)) * (np.abs(cy) < 0.48).astype(np.float32),
        0.0,
        1.0,
    )
    g2 = np.clip(
        np.exp(-150.0 * ((cx + 0.24) ** 2))
        + np.exp(-140.0 * ((cy - 0.85 * cx - 0.32) ** 2))
        + np.exp(-140.0 * ((cy - 0.85 * cx + 0.14) ** 2))
        + np.exp(-150.0 * ((cx - 0.28 * np.sin(cy * 3.6) - 0.22) ** 2)),
        0.0,
        1.0,
    )
    g3 = np.clip(
        np.exp(-155.0 * ((np.abs(cx) * 1.15 + np.abs(cy) - 0.44) ** 2))
        + np.exp(-145.0 * ((cy + 0.95 * np.abs(cx) - 0.72) ** 2)) * (cy > 0.20).astype(np.float32)
        + np.exp(-145.0 * ((cy - 0.95 * np.abs(cx) + 0.72) ** 2)) * (cy < -0.20).astype(np.float32),
        0.0,
        1.0,
    )

    glyph_sel = np.where(
        cell_id < 0.5,
        g0,
        np.where(cell_id < 1.5, g1, np.where(cell_id < 2.5, g2, g3)),
    )
    rune_core = (glyph_sel * in_box * z_runes).astype(np.float32)
    rune_halo = (
        np.exp(-3.8 * (cx * cx + cy * cy)) * (np.abs(dy_r) < 0.82).astype(np.float32) * z_runes
    ).astype(np.float32)

    # Subtle 10% ambient fissure glow strictly inside the rune frieze channel
    rune_fissures = (
        np.exp(-95.0 * (np.sin(two_pi * (16.0 * u + 12.0 * s) + 1.2 * n_med) ** 2))
        * _smoothstep(0.35, 0.80, 0.5 + 0.5 * n_macro)
        * (np.abs(dy_r) < 0.76).astype(np.float32)
        * z_runes
        * 0.12
    ).astype(np.float32)

    frieze_trough = ((np.abs(dy_r) < 0.78).astype(np.float32) * z_runes).astype(np.float32)

    h_runes = (
        -0.12 * frieze_trough
        + 0.22 * knot_cord
        - 0.54 * rune_core
        - 0.10 * rune_fissures
        - 0.08 * stone_pits
        + 0.025 * micro_grain
    ).astype(np.float32)

    ao_runes = np.clip(
        1.0 - 0.20 * frieze_trough - 0.50 * rune_core - 0.22 * (1.0 - knot_cord) * (np.abs(dy_r) > 0.76).astype(np.float32),
        0.26,
        1.0,
    ).astype(np.float32)

    # ==========================================================================
    # ZONE 4: UV_ZONE_BRONZE — AGED PATINATED DARK DRACONIC STONE-BRONZE INLAY
    # ==========================================================================
    fil_u = two_pi * 24.0 * u
    fil_s = two_pi * 44.0 * s
    bronze_scroll = np.exp(
        -12.0 * ((np.sin(fil_u + 0.75 * np.cos(fil_s)) * np.cos(fil_s - 0.75 * np.sin(fil_u))) ** 2)
    ).astype(np.float32)

    rivet_x = ((u * 48.0) % 1.0) - 0.5
    rivet_y = (s - 0.050) / 0.028
    bronze_rivets = (
        np.clip(1.0 - (rivet_x * 3.2) ** 2 - (rivet_y * 2.6) ** 2, 0.0, 1.0) ** 2
    ).astype(np.float32)

    bronze_relief = np.clip(0.72 * bronze_scroll + 0.85 * bronze_rivets, 0.0, 1.0).astype(np.float32)
    bronze_patina = np.clip(
        (1.0 - bronze_relief) * (0.65 + 0.35 * (0.5 + 0.5 * n_med)) + 0.30 * stone_pits,
        0.0,
        1.0,
    ).astype(np.float32)

    h_bronze = (
        0.18 * bronze_relief
        - 0.10 * bronze_patina
        - 0.05 * stone_pits
        + 0.02 * micro_grain
    ).astype(np.float32)

    ao_bronze = np.clip(1.0 - 0.42 * bronze_patina + 0.08 * bronze_relief, 0.38, 1.0).astype(np.float32)

    # ==========================================================================
    # COMPOSITE HEIGHT, AO, ROUGHNESS, METALLIC & NORMAL MAPS
    # ==========================================================================
    height = (
        z_scales * h_scales
        + z_stone * h_stone
        + z_runes * h_runes
        + z_bronze * h_bronze
        - 0.24 * band_groove
    ).astype(np.float32)

    ao_float = np.clip(
        (
            z_scales * ao_scales
            + z_stone * ao_stone
            + z_runes * ao_runes
            + z_bronze * ao_bronze
        )
        * (1.0 - 0.38 * band_groove),
        0.22,
        1.0,
    ).astype(np.float32)

    # Roughness: 0.52 worn scale ridges/domes to 0.90 dusty crevices
    rough_scales = np.clip(
        0.72
        - 0.20 * np.clip(0.65 * scale_keel + 0.55 * scale_bevel_lip + 0.35 * scale_dome, 0.0, 1.0)
        + 0.18 * scale_crevice
        + 0.04 * scale_chisel,
        0.52,
        0.90,
    )
    rough_stone = np.clip(
        0.72 + 0.16 * stone_pocket + 0.05 * stipple - 0.14 * stone_ridge,
        0.58,
        0.92,
    )
    rough_runes = np.clip(
        0.76 - 0.14 * knot_cord + 0.12 * frieze_trough,
        0.60,
        0.90,
    )
    rough_bronze = np.clip(
        0.42 + 0.20 * bronze_patina,
        0.42,
        0.62,
    )
    rough_common = (
        z_scales * rough_scales
        + z_stone * rough_stone
        + z_runes * rough_runes
        + z_bronze * rough_bronze
    ).astype(np.float32)

    metal_bronze = np.clip(0.65 - 0.17 * bronze_patina, 0.48, 0.65)
    metallic_common = (z_bronze * metal_bronze).astype(np.float32)

    dh_du_1 = (np.roll(height, -1, axis=1) - np.roll(height, 1, axis=1)) * np.float32(0.5 * res / 256.0)
    dh_du_4 = (np.roll(height, -4, axis=1) - np.roll(height, 4, axis=1)) * np.float32(0.125 * res / 256.0)
    dh_du = np.float32(0.55) * dh_du_1 + np.float32(0.95) * dh_du_4

    dh_dv_1 = np.zeros_like(height)
    dh_dv_1[1:-1, :] = (height[2:, :] - height[:-2, :]) * np.float32(0.5 * res / 256.0)
    dh_dv_4 = np.zeros_like(height)
    dh_dv_4[4:-4, :] = (height[8:, :] - height[:-8, :]) * np.float32(0.125 * res / 256.0)
    dh_dv = np.float32(0.55) * dh_dv_1 + np.float32(0.95) * dh_dv_4

    def _build_normal_uint8(strength: float) -> np.ndarray:
        nx = -dh_du * np.float32(strength)
        ny = dh_dv * np.float32(strength)
        nz = np.ones_like(height)
        inv_l = np.float32(1.0) / np.sqrt(nx * nx + ny * ny + nz * nz)
        return np.stack(
            [
                np.clip((nx * inv_l * 0.5 + 0.5) * 255.0, 0, 255),
                np.clip((ny * inv_l * 0.5 + 0.5) * 255.0, 0, 255),
                np.clip((nz * inv_l * 0.5 + 0.5) * 255.0, 0, 255),
            ],
            axis=-1,
        ).astype(np.uint8)

    # Clean magical emission concentrated in UV_ZONE_RUNES (zero random scale-border clutter!)
    total_glow_sharp = np.clip(rune_core + rune_fissures, 0.0, 1.0)
    total_glow_soft = np.clip(total_glow_sharp + 0.28 * rune_halo, 0.0, 1.0)

    # Sculptural highlight & crevice masks
    sculpt_highlight = np.clip(
        z_scales * np.clip(0.80 * scale_keel + 0.72 * scale_bevel_lip + 0.42 * scale_dome, 0.0, 1.0)
        + z_stone * (0.68 * stone_ridge)
        + z_runes * (0.72 * knot_cord),
        0.0,
        1.0,
    ).astype(np.float32)

    sculpt_crevice = np.clip(
        z_scales * scale_crevice
        + z_stone * (0.45 * stone_pocket)
        + z_runes * np.clip(0.32 * frieze_trough + 0.65 * rune_core, 0.0, 1.0)
        + 0.55 * band_groove,
        0.0,
        1.0,
    ).astype(np.float32)

    # ==========================================================================
    # WHITE FACTION: CARVED CATHEDRAL CAEN LIMESTONE / AGED TRAVERTINE
    #   - Base stone body: (0.78, 0.74, 0.67) +/- 0.04 warm/cool mineral clast mottling
    #   - Chiselled ridge/keel highlights: (0.87, 0.84, 0.78)
    #   - Soft warm taupe-sandstone crevice mortar: (0.58, 0.54, 0.48) [NEVER < 0.48!]
    # ==========================================================================
    w_clast = (
        0.026 * n_macro
        + 0.022 * n_med
        + 0.014 * n_fine
        + 0.026 * (scale_hash - 0.5) * z_scales
        - 0.014 * scale_chisel * z_scales
    ).astype(np.float32)

    w_st_r = 0.78 + w_clast + 0.095 * sculpt_highlight
    w_st_g = 0.74 + w_clast * 0.96 + 0.105 * sculpt_highlight
    w_st_b = 0.67 + w_clast * 0.88 + 0.115 * sculpt_highlight

    # Gentle warm sandstone mortar shift in crevices — 3D shading comes from Normal + AO + Roughness!
    w_crev_w = np.clip(0.62 * sculpt_crevice, 0.0, 0.68)
    w_st_r = np.maximum(0.56, w_st_r * (1.0 - w_crev_w) + 0.58 * w_crev_w)
    w_st_g = np.maximum(0.53, w_st_g * (1.0 - w_crev_w) + 0.54 * w_crev_w)
    w_st_b = np.maximum(0.49, w_st_b * (1.0 - w_crev_w) + 0.49 * w_crev_w)

    # Aged patinated dark stone-bronze (restricted strictly to UV_ZONE_BRONZE)
    w_br_r = 0.45 * (1.0 - 0.50 * bronze_patina) + 0.07 * bronze_relief
    w_br_g = 0.39 * (1.0 - 0.46 * bronze_patina) + 0.06 * bronze_relief
    w_br_b = 0.30 * (1.0 - 0.40 * bronze_patina) + 0.04 * bronze_relief

    w_r = w_st_r * (1.0 - z_bronze) + w_br_r * z_bronze
    w_g = w_st_g * (1.0 - z_bronze) + w_br_g * z_bronze
    w_b = w_st_b * (1.0 - z_bronze) + w_br_b * z_bronze

    # Ethereal icy-cyan + pale-gold soulfire core in rune recesses
    soul_core = rune_core ** 2
    w_r = w_r * (1.0 - 0.82 * total_glow_sharp) + (0.38 * total_glow_sharp + 0.54 * soul_core)
    w_g = w_g * (1.0 - 0.82 * total_glow_sharp) + (0.85 * total_glow_sharp + 0.11 * soul_core)
    w_b = w_b * (1.0 - 0.82 * total_glow_sharp) + (0.96 * total_glow_sharp - 0.14 * soul_core)

    white_albedo = np.stack(
        [
            np.clip(w_r * 255.0, 0, 255),
            np.clip(w_g * 255.0, 0, 255),
            np.clip(w_b * 255.0, 0, 255),
        ],
        axis=-1,
    ).astype(np.uint8)

    w_em_r = np.clip(0.24 * total_glow_soft + 0.72 * soul_core, 0.0, 1.0)
    w_em_g = np.clip(0.80 * total_glow_soft + 0.18 * soul_core, 0.0, 1.0)
    w_em_b = np.clip(1.00 * total_glow_soft - 0.18 * soul_core, 0.0, 1.0)
    white_emission = np.stack(
        [
            np.clip(w_em_r * 255.0, 0, 255),
            np.clip(w_em_g * 255.0, 0, 255),
            np.clip(w_em_b * 255.0, 0, 255),
        ],
        axis=-1,
    ).astype(np.uint8)

    white_normal = _build_normal_uint8(strength=3.10)
    white_roughness = np.clip(rough_common * 255.0, 0, 255).astype(np.uint8)
    white_metallic = np.clip(metallic_common * 255.0, 0, 255).astype(np.uint8)
    # Pale limestone interreflection keeps linear AO soft and warm (0.64..1.0) so seams never turn charcoal
    white_ao_float = np.clip(0.60 + 0.40 * ao_float, 0.64, 1.0)
    white_ao = np.clip(white_ao_float * 255.0, 0, 255).astype(np.uint8)

    # ==========================================================================
    # BLACK FACTION: VOLCANIC DRAGON-BASALT + DRY-BRUSHED ASH-GREY CHISEL EDGES
    #   - Base volcanic basalt body: (0.19, 0.20, 0.23)
    #   - Dry-brushed ash-grey stone highlights: (0.40, 0.41, 0.45) on keels/lips/ridges
    #   - Deep obsidian crevices: (0.06, 0.06, 0.08)
    # ==========================================================================
    b_clast = (
        0.018 * n_macro
        + 0.018 * n_med
        + 0.012 * n_fine
        + 0.022 * (scale_hash - 0.5) * z_scales
        - 0.016 * scale_chisel * z_scales
    ).astype(np.float32)

    b_drybrush = np.clip(
        z_scales * np.clip(0.88 * scale_keel + 0.85 * scale_bevel_lip + 0.30 * scale_dome, 0.0, 1.0)
        + z_stone * (0.72 * stone_ridge)
        + z_runes * (0.80 * knot_cord),
        0.0,
        1.0,
    ).astype(np.float32)

    b_st_r = 0.19 + b_clast + 0.215 * b_drybrush
    b_st_g = 0.20 + b_clast + 0.215 * b_drybrush
    b_st_b = 0.23 + b_clast + 0.225 * b_drybrush

    b_crev = np.clip(
        z_scales * scale_crevice
        + z_stone * (0.65 * stone_pocket)
        + z_runes * np.clip(0.40 * frieze_trough + 0.72 * rune_core, 0.0, 1.0)
        + 0.75 * band_groove,
        0.0,
        1.0,
    ).astype(np.float32)

    b_st_r = b_st_r * (1.0 - b_crev) + 0.06 * b_crev
    b_st_g = b_st_g * (1.0 - b_crev) + 0.06 * b_crev
    b_st_b = b_st_b * (1.0 - b_crev) + 0.08 * b_crev

    b_br_r = 0.34 * (1.0 - 0.56 * bronze_patina) + 0.07 * bronze_relief
    b_br_g = 0.27 * (1.0 - 0.54 * bronze_patina) + 0.06 * bronze_relief
    b_br_b = 0.21 * (1.0 - 0.50 * bronze_patina) + 0.04 * bronze_relief

    b_r = b_st_r * (1.0 - z_bronze) + b_br_r * z_bronze
    b_g = b_st_g * (1.0 - z_bronze) + b_br_g * z_bronze
    b_b = b_st_b * (1.0 - z_bronze) + b_br_b * z_bronze

    magma_core = rune_core ** 2
    b_r = b_r * (1.0 - 0.88 * total_glow_sharp) + 0.98 * total_glow_sharp
    b_g = b_g * (1.0 - 0.88 * total_glow_sharp) + (0.26 * total_glow_sharp + 0.42 * magma_core)
    b_b = b_b * (1.0 - 0.88 * total_glow_sharp) + (0.04 * total_glow_sharp + 0.12 * magma_core)

    black_albedo = np.stack(
        [
            np.clip(b_r * 255.0, 0, 255),
            np.clip(b_g * 255.0, 0, 255),
            np.clip(b_b * 255.0, 0, 255),
        ],
        axis=-1,
    ).astype(np.uint8)

    b_em_r = np.clip(0.96 * total_glow_soft + 0.04 * magma_core, 0.0, 1.0)
    b_em_g = np.clip(0.22 * total_glow_soft + 0.48 * magma_core, 0.0, 1.0)
    b_em_b = np.clip(0.03 * total_glow_soft + 0.12 * magma_core, 0.0, 1.0)
    black_emission = np.stack(
        [
            np.clip(b_em_r * 255.0, 0, 255),
            np.clip(b_em_g * 255.0, 0, 255),
            np.clip(b_em_b * 255.0, 0, 255),
        ],
        axis=-1,
    ).astype(np.uint8)

    black_normal = _build_normal_uint8(strength=3.20)
    black_roughness = np.clip((rough_common * 0.96) * 255.0, 0, 255).astype(np.uint8)
    black_metallic = np.clip(metallic_common * 255.0, 0, 255).astype(np.uint8)
    black_ao = np.clip(ao_float * 255.0, 0, 255).astype(np.uint8)

    tex_payloads = {
        "white_piece_albedo.png": white_albedo,
        "white_piece_normal.png": white_normal,
        "white_piece_roughness.png": white_roughness,
        "white_piece_metallic.png": white_metallic,
        "white_piece_ao.png": white_ao,
        "white_piece_emission.png": white_emission,
        "black_piece_albedo.png": black_albedo,
        "black_piece_normal.png": black_normal,
        "black_piece_roughness.png": black_roughness,
        "black_piece_metallic.png": black_metallic,
        "black_piece_ao.png": black_ao,
        "black_piece_emission.png": black_emission,
    }

    written_paths: dict[str, str] = {}
    for fname, arr in tex_payloads.items():
        fpath = os.path.join(TEXTURES_DIR, fname)
        _save_png_uint8(fpath, arr)
        written_paths[fname] = fpath
        print(f"  -> Saved {fname} ({arr.shape[1]}x{arr.shape[0]})")

    return written_paths


def create_dragon_piece_material(prefix: str = "white_piece") -> bpy.types.Material:
    """
    Build a Blender 5.2 Principled BSDF material for `white_piece` or `black_piece`:
      - Multiplies `ao` into `albedo` via `ShaderNodeMix` (RGBA MULTIPLY)
      - Wires `roughness`, `metallic`, `normal` (Strength 1.45)
      - Sets `Diffuse Roughness = 0.65` for carved Oren-Nayar stonework response
      - Wires `emission` -> `Emission Color` with `Emission Strength = 0.65`
    """
    mat_name = f"Mat_{prefix}"
    if mat_name in bpy.data.materials:
        mat = bpy.data.materials[mat_name]
    else:
        mat = bpy.data.materials.new(name=mat_name)

    if mat.node_tree is None:
        mat.use_nodes = True

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    out_node = nodes.new(type="ShaderNodeOutputMaterial")
    out_node.location = (620, 0)

    bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
    bsdf.location = (240, 0)
    links.new(bsdf.outputs["BSDF"], out_node.inputs["Surface"])

    if "Diffuse Roughness" in bsdf.inputs:
        bsdf.inputs["Diffuse Roughness"].default_value = 0.65

    def _load_tex_node(suffix: str, is_non_color: bool, loc_y: float):
        tex_path = os.path.join(TEXTURES_DIR, f"{prefix}_{suffix}.png")
        if not os.path.exists(tex_path):
            synthesize_dragon_piece_pbr(TEXTURE_SIZE)
        img = bpy.data.images.load(tex_path, check_existing=True)
        img.reload()
        img.colorspace_settings.name = "Non-Color" if is_non_color else "sRGB"
        node = nodes.new(type="ShaderNodeTexImage")
        node.name = f"Tex_{suffix}"
        node.label = f"{prefix}_{suffix}"
        node.image = img
        node.location = (-460, loc_y)
        return node

    albedo_node = _load_tex_node("albedo", False, 380)
    ao_node = _load_tex_node("ao", True, 180)
    roughness_node = _load_tex_node("roughness", True, -20)
    metallic_node = _load_tex_node("metallic", True, -220)
    normal_tex_node = _load_tex_node("normal", True, -420)
    emission_node = _load_tex_node("emission", False, -640)

    # Multiply AO into Albedo (warm interreflection factor on White so limestone crevices stay warm stone, deeper on Black)
    ao_mix = nodes.new(type="ShaderNodeMix")
    ao_mix.data_type = "RGBA"
    ao_mix.blend_type = "MULTIPLY"
    ao_mix.location = (-80, 280)
    ao_mix.inputs[0].default_value = 0.34 if "white" in prefix.lower() else 0.80
    links.new(albedo_node.outputs["Color"], ao_mix.inputs[6])
    links.new(ao_node.outputs["Color"], ao_mix.inputs[7])
    links.new(ao_mix.outputs[2], bsdf.inputs["Base Color"])

    links.new(roughness_node.outputs["Color"], bsdf.inputs["Roughness"])
    links.new(metallic_node.outputs["Color"], bsdf.inputs["Metallic"])

    norm_map = nodes.new(type="ShaderNodeNormalMap")
    norm_map.location = (-80, -420)
    norm_map.inputs["Strength"].default_value = 1.55
    links.new(normal_tex_node.outputs["Color"], norm_map.inputs["Color"])
    links.new(norm_map.outputs["Normal"], bsdf.inputs["Normal"])

    if "Emission Color" in bsdf.inputs:
        links.new(emission_node.outputs["Color"], bsdf.inputs["Emission Color"])
        bsdf.inputs["Emission Strength"].default_value = 0.65
    elif "Emission" in bsdf.inputs:
        links.new(emission_node.outputs["Color"], bsdf.inputs["Emission"])

    return mat


if __name__ == "__main__":
    synthesize_dragon_piece_pbr(TEXTURE_SIZE)
    create_dragon_piece_material("white_piece")
    create_dragon_piece_material("black_piece")
