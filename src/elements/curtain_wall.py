import Rhino.Geometry as rg
import rhinoscriptsyntax as rs
from typing import List, Tuple


# ---------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------

def _coerce_polyline(crv) -> rg.Polyline:
    crv = rs.coercecurve(crv)
    if not crv:
        raise TypeError("guide must be a Curve")

    success, pl = crv.TryGetPolyline()
    if not success:
        raise TypeError("guide must be a polyline (or convertible to polyline)")

    if pl.Count < 2:
        raise ValueError("polyline must have at least 2 points")

    return pl


def _centered_rect_curve(plane: rg.Plane, size_x: float, size_y: float) -> rg.Curve:
    """Rectangle centered on plane origin (critical!)."""
    ix = rg.Interval(-size_x * 0.5, size_x * 0.5)
    iy = rg.Interval(-size_y * 0.5, size_y * 0.5)
    return rg.Rectangle3d(plane, ix, iy).ToNurbsCurve()


def _box_brep(plane: rg.Plane, size_x: float, size_y: float, height_z: float) -> rg.Brep:
    crv = _centered_rect_curve(plane, float(size_x), float(size_y))
    ext = rg.Extrusion.Create(crv, float(height_z), True)
    return ext.ToBrep() if ext else None


def _panel_brep(plane: rg.Plane, width_mm: float, height_mm: float, thickness_mm: float) -> rg.Brep:
    # thickness is the "depth" in plane Y
    return _box_brep(plane, float(width_mm), float(thickness_mm), float(height_mm))


# ---------------------------------------------------------------------
# main
# ---------------------------------------------------------------------

def curtain_wall(
    guide,
    mullion_spacing_mm: int = 1350,

    mullion_width_mm: int = 60,
    mullion_depth_mm: int = 120,

    transom_height_mm: int = 60,
    transom_depth_mm: int = 120,

    panel_thickness_mm: int = 24,
    glass_inset_mm: int = 40,
    glass_gap_mm: int = 12,

    story_height_mm: int = 3200,
    stories: int = 1
) -> Tuple[List[rg.Brep], List[rg.Brep]]:

    pl = _coerce_polyline(guide)

    mullion_spacing_mm = float(mullion_spacing_mm)
    mullion_width_mm = float(mullion_width_mm)
    mullion_depth_mm = float(mullion_depth_mm)

    transom_height_mm = float(transom_height_mm)
    transom_depth_mm = float(transom_depth_mm)

    panel_thickness_mm = float(panel_thickness_mm)
    glass_inset_mm = float(glass_inset_mm)
    glass_gap_mm = float(glass_gap_mm)

    story_height_mm = float(story_height_mm)
    stories = int(stories)

    breps_mullions: List[rg.Brep] = []
    breps_glass: List[rg.Brep] = []

    # Used to keep yaxis consistent across polyline segments
    prev_yaxis = None



    for s in range(stories):
        z0 = s * story_height_mm
        z1 = z0 + story_height_mm

        for i in range(pl.Count - 1):
            p_start = rg.Point3d(pl[i])
            p_end = rg.Point3d(pl[i + 1])

            seg_vec = p_end - p_start
            seg_len = seg_vec.Length

            base_z = p_start.Z

            if seg_len <= 1e-6:
                continue

            xaxis = rg.Vector3d(seg_vec)
            xaxis.Unitize()

            # Candidate yaxis (left of segment in world Z-up)
            yaxis = rg.Vector3d.CrossProduct(rg.Vector3d.ZAxis, xaxis)
            if yaxis.IsTiny():
                yaxis = rg.Vector3d.YAxis
            yaxis.Unitize()

            # ---- keep yaxis consistent across segments ----
            if prev_yaxis is not None and rg.Vector3d.Multiply(yaxis, prev_yaxis) < 0:
                yaxis.Reverse()
            prev_yaxis = rg.Vector3d(yaxis)

            # Panels along this segment
            panel_count = max(1, int(seg_len // mullion_spacing_mm))
            step = seg_len / panel_count

            for j in range(panel_count):
                d0 = j * step
                d1 = (j + 1) * step

                base_pt = p_start + xaxis * d0
                next_pt = p_start + xaxis * d1

                base_pt.Z += z0
                next_pt.Z += z0

                # --- mullion at bay start (centered on guide) ---
                mull_plane = rg.Plane(base_pt, xaxis, yaxis)
                mull = _box_brep(mull_plane, mullion_width_mm, mullion_depth_mm, story_height_mm)
                if mull:
                    breps_mullions.append(mull)

                # --- clear span between mullion inner faces (edge-based) ---
                edge_offset = mullion_width_mm * 0.5
                panel_start = base_pt + xaxis * edge_offset
                panel_end = next_pt - xaxis * edge_offset

                clear_vec = panel_end - panel_start
                clear_span = clear_vec.Length
                if clear_span <= 1e-6:
                    continue

                clear_width = clear_span - 2.0 * glass_gap_mm
                clear_height = story_height_mm - 2.0 * transom_height_mm - 2.0 * glass_gap_mm

                if clear_width <= 1e-6 or clear_height <= 1e-6:
                    continue

                clear_dir = rg.Vector3d(clear_vec)
                clear_dir.Unitize()

                mid = (panel_start + panel_end) * 0.5

                # --- transoms: centered on guide (NO unintended forward shift anymore) ---
                bot_mid = rg.Point3d(mid.X, mid.Y, base_z + z0)
                bot_plane = rg.Plane(bot_mid, clear_dir, yaxis)
                bottom = _box_brep(bot_plane, clear_span, transom_depth_mm, transom_height_mm)
                if bottom:
                    breps_mullions.append(bottom)

                top_mid = rg.Point3d(mid.X, mid.Y, base_z + z1 - transom_height_mm)
                top_plane = rg.Plane(top_mid, clear_dir, yaxis)
                top = _box_brep(top_plane, clear_span, transom_depth_mm, transom_height_mm)
                if top:
                    breps_mullions.append(top)

                # --- glass: inset from the OUTER face of mullion ---
                # Mullion is centered on guide. Outer face is +yaxis*(mullion_depth/2).
                # Inset goes inward (towards -yaxis).
                glass_center_offset = (mullion_depth_mm * 0.5) - glass_inset_mm - (panel_thickness_mm * 0.5)
                glass_origin = rg.Point3d(
                    mid.X - yaxis.X * glass_center_offset,
                    mid.Y - yaxis.Y * glass_center_offset,
                    base_z + z0 + transom_height_mm + glass_gap_mm
                )
                glass_plane = rg.Plane(glass_origin, clear_dir, yaxis)

                glass = _panel_brep(glass_plane, clear_width, clear_height, panel_thickness_mm)
                if glass:
                    breps_glass.append(glass)

            # --- final mullion at segment end ---
            end_pt = rg.Point3d(p_end)
            end_pt.Z += z0
            end_plane = rg.Plane(end_pt, xaxis, yaxis)
            end_mull = _box_brep(end_plane, mullion_width_mm, mullion_depth_mm, story_height_mm)
            if end_mull:
                breps_mullions.append(end_mull)

    return breps_mullions, breps_glass
