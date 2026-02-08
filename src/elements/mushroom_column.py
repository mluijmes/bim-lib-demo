import Rhino.Geometry as rg
import rhinoscriptsyntax as rs
from typing import List
from System import Guid


def _coerce_point3d(p) -> rg.Point3d:
    """
    Grasshopper-safe point coercion.
    Accepts:
    - Point3d
    - Guid (Rhino point object)
    """

    # Case 1: already a Point3d
    if isinstance(p, rg.Point3d):
        return p

    # Case 2: Guid -> Rhino geometry
    if isinstance(p, Guid):
        geom = rs.coercegeometry(p)
        if isinstance(geom, rg.Point):
            return geom.Location
        if isinstance(geom, rg.Point3d):
            return geom

    raise TypeError("base_point must be a Grasshopper Point or Point3d")


def mushroom_column(
    base_point,
    height_mm: float = 3200,

    shaft_radius_mm: float = 250,
    capital_radius_mm: float = 600,
    capital_height_mm: float = 450,

    slab_thickness_mm: float = 300,
    slab_radius_mm: float = 1200,

    fillet_radius_mm: float = 0
) -> List[rg.Brep]:

    # --------------------------------------------------
    # Coerce inputs
    # --------------------------------------------------
    pt = _coerce_point3d(base_point)

    height_mm = float(height_mm)
    shaft_radius_mm = float(shaft_radius_mm)
    capital_radius_mm = float(capital_radius_mm)
    capital_height_mm = float(capital_height_mm)
    slab_thickness_mm = float(slab_thickness_mm)
    slab_radius_mm = float(slab_radius_mm)
    fillet_radius_mm = float(fillet_radius_mm)

    z_axis = rg.Vector3d.ZAxis
    breps: List[rg.Brep] = []

    # --------------------------------------------------
    # Shaft
    # --------------------------------------------------
    shaft_plane = rg.Plane(pt, z_axis)
    shaft_circle = rg.Circle(shaft_plane, shaft_radius_mm)

    shaft = rg.Extrusion.Create(
        shaft_circle.ToNurbsCurve(),
        height_mm - capital_height_mm,
        True
    )
    if shaft:
        breps.append(shaft.ToBrep())

    # --------------------------------------------------
    # Capital (mushroom flare)
    # --------------------------------------------------
    cap_base_pt = rg.Point3d(pt.X, pt.Y, pt.Z + height_mm - capital_height_mm)
    cap_top_pt = rg.Point3d(pt.X, pt.Y, pt.Z + height_mm)

    base_plane = rg.Plane(cap_base_pt, z_axis)
    top_plane = rg.Plane(cap_top_pt, z_axis)

    base_circle = rg.Circle(base_plane, shaft_radius_mm)
    top_circle = rg.Circle(top_plane, capital_radius_mm)

    loft = rg.Brep.CreateFromLoft(
        [base_circle.ToNurbsCurve(), top_circle.ToNurbsCurve()],
        rg.Point3d.Unset,
        rg.Point3d.Unset,
        rg.LoftType.Straight,
        False
    )

    if loft and len(loft) > 0:
        capital = loft[0].CapPlanarHoles(0.01) or loft[0]
        breps.append(capital)

    # --------------------------------------------------
    # Slab head
    # --------------------------------------------------
    slab_plane = rg.Plane(cap_top_pt, z_axis)
    slab_circle = rg.Circle(slab_plane, slab_radius_mm)

    slab = rg.Extrusion.Create(
        slab_circle.ToNurbsCurve(),
        slab_thickness_mm,
        True
    )
    if slab:
        breps.append(slab.ToBrep())

    # --------------------------------------------------
    # Optional fillet
    # --------------------------------------------------
    if fillet_radius_mm > 0 and len(breps) >= 2:
        try:
            joined = rg.Brep.JoinBreps(breps, 0.01)
            if joined:
                filleted = rg.Brep.CreateFilletEdges(
                    joined[0],
                    joined[0].Edges,
                    [fillet_radius_mm] * joined[0].Edges.Count,
                    [fillet_radius_mm] * joined[0].Edges.Count,
                    rg.BlendType.Fillet,
                    0.01
                )
                if filleted:
                    breps = filleted
        except:
            pass

    return breps
