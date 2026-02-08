import Rhino.Geometry as rg
import rhinoscriptsyntax as rs
from typing import Dict


def _coerce_curve(crv):
    crv = rs.coercecurve(crv)
    if not crv:
        raise TypeError("boundary must be a Curve")
    return crv


def _planar_slab(curve, z_base, thickness):
    """
    Create a planar slab by extruding a curve downward.
    Grasshopper-safe implementation.
    """
    crv = curve.Duplicate()
    crv.Transform(rg.Transform.Translation(0, 0, float(z_base)))

    ext = rg.Extrusion.Create(
        crv,
        -float(thickness),   # extrude DOWN
        True                 # cap
    )

    return ext.ToBrep() if ext else None


def floor_plate(
    boundary,
    elevation_mm: float,

    finish_thickness_mm: float = 15,
    screed_thickness_mm: float = 70,
    insulation_thickness_mm: float = 30,
    structural_thickness_mm: float = 250
) -> Dict[str, rg.Brep]:
    """
    Multi-layer floor build-up.

    Returns:
      {
        "finish": Brep,
        "screed": Brep,
        "insulation": Brep,
        "structural": Brep
      }
    """

    boundary = _coerce_curve(boundary)

    elevation_mm = float(elevation_mm)
    finish_thickness_mm = float(finish_thickness_mm)
    screed_thickness_mm = float(screed_thickness_mm)
    insulation_thickness_mm = float(insulation_thickness_mm)
    structural_thickness_mm = float(structural_thickness_mm)

    z = elevation_mm
    layers = {}

    layers["finish"] = _planar_slab(boundary, z, finish_thickness_mm)
    z -= finish_thickness_mm

    layers["screed"] = _planar_slab(boundary, z, screed_thickness_mm)
    z -= screed_thickness_mm

    layers["insulation"] = _planar_slab(boundary, z, insulation_thickness_mm)
    z -= insulation_thickness_mm

    layers["structural"] = _planar_slab(boundary, z, structural_thickness_mm)

    return layers
