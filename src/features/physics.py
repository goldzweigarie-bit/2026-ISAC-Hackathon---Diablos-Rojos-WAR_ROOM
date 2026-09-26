"""Física del béisbol: corrección de movimiento por densidad del aire.

A 2,240 msnm (Harp Helú) la densidad del aire es ~20% menor que a nivel
del mar, lo que reduce el efecto Magnus y, por tanto, el break inducido
(H1 de la convocatoria; referencia: Coors Field, 1,609 m).

Implementar con el modelo aerodinámico estándar (Alan Nathan):
    rho(h) = rho0 * exp(-h / H),  H ≈ 8,400 m  (aprox. isotérmica)
y la relación break ∝ rho (aproximación de primer orden para el efecto Magnus).
"""

RHO0 = 1.225          # kg/m^3, densidad a nivel del mar
SCALE_HEIGHT = 8400.0  # m
HARP_HELU_ALT = 2240.0  # msnm
SEA_LEVEL = 0.0


def air_density(altitude_m: float) -> float:
    """Densidad del aire aproximada a la altitud dada (modelo exponencial)."""
    return RHO0 * pow(2.718281828, -altitude_m / SCALE_HEIGHT)


def density_ratio(altitude_m: float) -> float:
    """ratio = rho(altitud) / rho(0). En Harp Helú ≈ 0.77 (≈23% menos denso)."""
    return air_density(altitude_m) / RHO0


def estimate_break_at_altitude(break_in: float, from_alt: float, to_alt: float) -> float:
    """Escala pulgadas de break entre dos altitudes (break ∝ rho).

    Nota: solo la componente Magnus (spin-induced) se ve afectada;
    la componente por fuerzas de arrastre gravitacional (drop) se modela
    aparte cuando se tenga tracking data real de LMB.
    """
    return break_in * density_ratio(to_alt) / density_ratio(from_alt)


def magnus_scaling(altitude_m: float) -> float:
    """Factor por el que se multiplica el break Magnus en la altitud dada."""
    return density_ratio(altitude_m)
