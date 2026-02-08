import Rhino.Geometry as rg
import rhinoscriptsyntax as rs
import math
from typing import Callable, List


def louvers(
    guide,
    spacing_mm: float,
    angle_fn: Callable[[float], float],

    depth_mm: float,
    thickness_mm: float = 20,
    height_mm: float = 2000,

    story_height_mm: float = 3200,
    stories: int = 1,

    wave_amplitude_mm: float = 80,
    wave_frequency: float = 1.0,
    twist_amplitude_rad: float = 0.2
) -> List[rg.Brep]:
    """
    Generate solid louvres along a guide curve using spacing-based logic.

    Parameters
    ----------
    guide : Curve
        Facade reference line (plan or elevation).

    spacing_mm : float
        Target spacing between louvres in millimetres.

    angle_fn : Callable[[float], float]
        Function: t ∈ [0,1] → angle (radians).

    depth_mm : float
        Base louvre depth (mm).

    thickness_mm : float
        Base louvre thickness (mm).

    height_mm : float
        Height of each louvre element (mm).

    story_height_mm : float
        Vertical distance between stories (mm).

    stories : int
        Number of stories.

    wave_amplitude_mm : float
        Amplitude of depth / thickness modulation.

    wave_frequency : float
        Number of waves along the guide.

    twist_amplitude_rad : float
        Additional local twist per louvre (radians).

    Returns
    -------
    List[rg.Brep]
        Solid louvre Breps.
    """

    # --------------------------------------------------
    # Coerce + sanitize
    # --------------------------------------------------
    guide = rs.coercecurve(guide)
    if not guide:
        raise TypeError("guide must be a Curve")

    spacing_mm = float(spacing_mm)
    if spacing_mm <= 0:
        raise ValueError("spacing_mm must be > 0")

    stories = int(stories)

    curve_length = guide.GetLength()
    if curve_length <= 1e-6:
        return []

    # Number of louvres along the curve
    count = max(1, int(round(curve_length / spacing_mm)))

    # Normalized parameters along curve
    params = [i / float(count) for i in range(count + 1)]

    breps: List[rg.Brep] = []

    # --------------------------------------------------
    # Build geometry
    # --------------------------------------------------
    for story in range(stories):
        z_offset = story * story_height_mm

        for t in params:
            # ------------------------------------------
            # Position
            # ------------------------------------------
            pt = guide.PointAtNormalizedLength(t)
            pt.Z += z_offset

            # ------------------------------------------
            # Behaviour (angles)
            # ------------------------------------------
            base_angle = angle_fn(t)

            local_twist = math.sin(
                t * math.pi * 2 * wave_frequency
            ) * twist_amplitude_rad

            angle = base_angle + local_twist

            # ------------------------------------------
            # Shape modulation
            # ------------------------------------------
            wave = math.sin(
                t * math.pi * 2 * wave_frequency
            )

            depth = depth_mm + wave * wave_amplitude_mm
            thickness = thickness_mm + wave * (wave_amplitude_mm * 0.4)

            # ------------------------------------------
            # Geometry
            # ------------------------------------------
            plane = rg.Plane(pt, rg.Vector3d.ZAxis)
            plane.Rotate(angle, plane.ZAxis)

            rect = rg.Rectangle3d(
                plane,
                float(depth),
                float(thickness)
            )

            profile = rect.ToNurbsCurve()

            ext = rg.Extrusion.Create(profile, float(height_mm), True)
            if ext:
                breps.append(ext.ToBrep())

    return breps
