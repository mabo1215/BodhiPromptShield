"""
Differential privacy for IBPPSVM: Laplace mechanism and sensitivity.
Used in paper: ε-differential privacy, noise N_Privacy Noise in SGD.
No DBN or Privacy Boundary (PB); noise is Laplace(0, Δf/ε).
"""
import numpy as np


def laplace_mechanism(value: float, sensitivity: float, epsilon: float) -> float:
    """
    Add Laplace noise for ε-differential privacy.
    θ(X) = f(X) + Y(X), Y ~ Laplace(0, sensitivity/ε).
    """
    scale = sensitivity / epsilon
    return value + np.random.laplace(0, scale)


def laplace_mechanism_vector(vec: np.ndarray, sensitivity: float, epsilon: float) -> np.ndarray:
    """Add i.i.d. Laplace noise to each coordinate (e.g. for document vectors)."""
    scale = sensitivity / epsilon
    return vec + np.random.laplace(0, scale, vec.shape)


def l1_sensitivity_for_mean(dim: int, bound: float = 1.0) -> float:
    """
    L1 sensitivity of the mean of n vectors when one row can change by at most `bound` per coordinate.
    For mean: Δf ≤ 2 * bound / n (one row change).
    """
    return 2 * bound  # per-coordinate; for normalized mean over n samples, scale by 1/n externally
