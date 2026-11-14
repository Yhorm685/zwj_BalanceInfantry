"""Planar cart and uniform rectangular pole. State order: x, v, theta, omega."""

import numpy as np


def derivative(state, force, cart_mass=1.0, rod_mass=0.2, length=0.6):
    _, v, theta, omega = state
    lever = 0.5 * length
    coupling = rod_mass * lever * np.cos(theta)
    inertia = rod_mass * ((length * length + 0.02**2) / 12 + lever**2)
    mass = [[cart_mass + rod_mass, coupling], [coupling, inertia]]
    right_hand = [
        force - 0.05 * v + rod_mass * lever * np.sin(theta) * omega**2,
        rod_mass * 9.81 * lever * np.sin(theta) - 0.002 * omega,
    ]
    acceleration, angular_acceleration = np.linalg.solve(mass, right_hand)
    return np.array([v, acceleration, omega, angular_acceleration])


def linear_model(cart_mass=1.0, rod_mass=0.2, length=0.6):
    lever = length / 2
    inertia = rod_mass * ((length**2 + 0.02**2) / 12 + lever**2)
    coupling = rod_mass * lever
    mass = [[cart_mass + rod_mass, coupling], [coupling, inertia]]
    a = np.zeros((4, 4))
    a[0, 1] = a[2, 3] = 1.0
    a[[1, 3], :] = np.linalg.solve(mass, [[0, -0.05, 0, 0], [0, 0, 9.81 * coupling, -0.002]])
    b = np.zeros((4, 1))
    b[[1, 3], 0] = np.linalg.solve(mass, [1, 0])
    return a, b


def check_jacobian():
    a, b = linear_model()
    h = 1e-6
    zero = np.zeros(4)
    numerical_a = np.column_stack([
        (derivative(axis * h, 0) - derivative(-axis * h, 0)) / (2 * h)
        for axis in np.eye(4)
    ])
    numerical_b = (derivative(zero, h) - derivative(zero, -h)) / (2 * h)
    np.testing.assert_allclose(a, numerical_a, rtol=1e-8, atol=1e-10)
    np.testing.assert_allclose(b[:, 0], numerical_b, rtol=1e-8, atol=1e-10)
    print("A =\n", a, "\nB =\n", b)
    print("Jacobian max |error|:", max(np.abs(a - numerical_a).max(), np.abs(b[:, 0] - numerical_b).max()))


if __name__ == "__main__":
    check_jacobian()
