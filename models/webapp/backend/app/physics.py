"""Pitch flight physics used to project how a pitch behaves at a given ballpark.

Model
-----
Trackman's 9-parameter fit describes each pitch with constant acceleration (ax0, ay0, az0) from y = 50 ft.
Apart from gravity, every acceleration on the ball (Magnus lift and drag) scales linearly with air density,
so for the same release (velocity, spin, axis):

    a_non_gravity(park) = a_non_gravity(observed) * rho(park) / rho(observed)

We store every pitch as a sea-level-equivalent acceleration (divide out the density where it was thrown)
and multiply by the target park's density to project it. Humidity is ignored (it moves density by <1%).

Coordinates: feet, x toward the first-base side from the catcher's view (flip in the frontend if the data
uses the other convention), y toward the mound, z up. Plate front is at y = 17/12 ft.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

G_FT_S2 = 32.174
Y_PLATE_FT = 17.0 / 12.0
R_DRY_AIR = 287.05


def air_density(altitude_m, temp_c=25.0):
    """Air density (kg/m^3) from the standard-atmosphere pressure at altitude and the air temperature."""
    altitude_m = np.asarray(altitude_m, dtype=float)
    pressure_pa = 101325.0 * np.power(1.0 - 2.25577e-5 * altitude_m, 5.25588)
    return pressure_pa / (R_DRY_AIR * (np.asarray(temp_c, dtype=float) + 273.15))


@dataclass(frozen=True)
class Environment:
    altitude_m: float
    temp_c: float

    @property
    def rho(self) -> float:
        return float(air_density(self.altitude_m, self.temp_c))


def flight(x0, y0, z0, vx0, vy0, vz0, ax, ay, az):
    """Constant-acceleration flight from y0 to the front of the plate. Works on scalars or arrays.

    Returns dict with time to plate t (s), plate crossing px, pz (ft), plate velocity components,
    plate speed (mph) and vertical approach angle (deg, negative = downward).
    """
    x0, y0, z0, vx0, vy0, vz0, ax, ay, az = (np.asarray(v, dtype=float) for v in (x0, y0, z0, vx0, vy0, vz0, ax, ay, az))
    # y(t) = y0 + vy0 t + 0.5 ay t^2 = Y_PLATE, vy0 < 0, pick the first positive root.
    a = 0.5 * ay
    b = vy0
    c = y0 - Y_PLATE_FT
    disc = np.maximum(b * b - 4 * a * c, 0.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        t_quad = (-b - np.sqrt(disc)) / (2 * a)
    t_lin = -c / b
    t = np.where(np.abs(a) > 1e-9, t_quad, t_lin)
    px = x0 + vx0 * t + 0.5 * ax * t * t
    pz = z0 + vz0 * t + 0.5 * az * t * t
    vxp = vx0 + ax * t
    vyp = vy0 + ay * t
    vzp = vz0 + az * t
    speed_mph = np.sqrt(vxp ** 2 + vyp ** 2 + vzp ** 2) * 3600.0 / 5280.0
    vaa = np.degrees(np.arctan2(vzp, -vyp))
    return {"t": t, "px": px, "pz": pz, "vx": vxp, "vy": vyp, "vz": vzp, "plate_speed": speed_mph, "vaa": vaa}


def to_sea_level(ax0, ay0, az0, rho_observed, rho_ref):
    """Convert observed accelerations to reference-density (sea-level) equivalents.

    Returns (ax_mag, ay_drag, az_mag) with gravity removed from z.
    """
    k = np.asarray(rho_ref, dtype=float) / np.asarray(rho_observed, dtype=float)
    return np.asarray(ax0) * k, np.asarray(ay0) * k, (np.asarray(az0) + G_FT_S2) * k


def at_density(ax_mag_ref, ay_drag_ref, az_mag_ref, rho_target, rho_ref):
    """Accelerations (with gravity) at a target density from reference-density components."""
    k = np.asarray(rho_target, dtype=float) / np.asarray(rho_ref, dtype=float)
    return np.asarray(ax_mag_ref) * k, np.asarray(ay_drag_ref) * k, np.asarray(az_mag_ref) * k - G_FT_S2


def movement_inches(ax_mag, az_mag, t):
    """Spin-induced movement over the flight (Trackman HorzBreak / InducedVertBreak convention)."""
    t = np.asarray(t, dtype=float)
    return 0.5 * np.asarray(ax_mag) * t * t * 12.0, 0.5 * np.asarray(az_mag) * t * t * 12.0


def aim_velocity(x0, y0, z0, vx0, vy0, vz0, ax, ay, az, target_x, target_z):
    """Adjust the lateral and vertical release velocity so the pitch crosses (target_x, target_z).

    Flight time depends only on the y motion, so vx0 and vz0 can be solved directly. Used to aim every pitch
    at the same spot at sea level, then replay the identical release at another park.
    """
    f = flight(x0, y0, z0, vx0, vy0, vz0, ax, ay, az)
    t = f["t"]
    new_vx0 = (np.asarray(target_x) - np.asarray(x0) - 0.5 * np.asarray(ax) * t * t) / t
    new_vz0 = (np.asarray(target_z) - np.asarray(z0) - 0.5 * np.asarray(az) * t * t) / t
    return new_vx0, new_vz0
