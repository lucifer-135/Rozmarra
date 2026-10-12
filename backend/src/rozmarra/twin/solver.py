"""A fixed-step fourth-order Runge–Kutta solver with a 1-minute step.

The solver is written in NumPy, so that it runs many parameter sets or forecast
windows at the same time (docs/techstack.md, Section 5.5). The inputs stay constant
within each minute, because meals and doses enter the model at the start of the
minute in which they occur. A unit test compares the solver with SciPy solve_ivp.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from rozmarra.twin.model import G_FLOOR, Forcing, Parameters, derivatives


@dataclass
class Trajectory:
    """The states at every minute, with the shape (B, L + 1). Column 0 is the start."""

    G: np.ndarray
    X: np.ndarray
    I: np.ndarray


def integrate(
    G0: np.ndarray, X0: np.ndarray, I0: np.ndarray, p: Parameters, forcing: Forcing
) -> Trajectory:
    if p.P0 is None:
        raise ValueError("Please calibrate P0 before running the solver.")
    length = forcing.length
    # The batch size comes from the starting states, the parameters and the meal input.
    rows = np.zeros(np.atleast_2d(forcing.ra).shape[0])
    G, X, I, _, _ = (
        np.array(a, dtype=float) for a in np.broadcast_arrays(np.atleast_1d(G0), X0, I0, p.P0, rows)
    )
    out = Trajectory(*(np.empty((G.shape[0], length + 1)) for _ in range(3)))
    out.G[:, 0], out.X[:, 0], out.I[:, 0] = G, X, I
    for k in range(length):
        inputs = forcing.column(k)
        g1, x1, i1 = derivatives(G, X, I, p, inputs)
        g2, x2, i2 = derivatives(G + 0.5 * g1, X + 0.5 * x1, I + 0.5 * i1, p, inputs)
        g3, x3, i3 = derivatives(G + 0.5 * g2, X + 0.5 * x2, I + 0.5 * i2, p, inputs)
        g4, x4, i4 = derivatives(G + g3, X + x3, I + i3, p, inputs)
        G = np.maximum(G + (g1 + 2 * g2 + 2 * g3 + g4) / 6, G_FLOOR)
        X = X + (x1 + 2 * x2 + 2 * x3 + x4) / 6
        I = np.maximum(I + (i1 + 2 * i2 + 2 * i3 + i4) / 6, 0.0)
        out.G[:, k + 1], out.X[:, k + 1], out.I[:, k + 1] = G, X, I
    return out
