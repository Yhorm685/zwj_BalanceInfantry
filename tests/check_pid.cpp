#include "../controllers/balance/cascade_pid.hpp"

#include <cmath>
#include <iostream>
#include <stdexcept>

void expect_near(double value, double expected) {
  if (std::abs(value - expected) > 1e-8)
    throw std::runtime_error("PID output differs from expected value");
}

int main() {
  CascadePid pid;
  // A reference beyond the lean limit must not accumulate integral.
  for (int k = 0; k < 5000; ++k)
    expect_near(pid.step(0, 0, 0, 0, 2), -55.0 * 0.16);
  expect_near(pid.step(0, 0, 0, 0, 0), 0);
  // Saturate the force with a lean error, while reference remains within limits.
  for (int k = 0; k < 5000; ++k)
    expect_near(pid.step(0, 0, 0.3, 0, -0.1), 10.0);
  expect_near(pid.step(0, 0, 0, 0, 0), 0);
  // Away from saturation the integral must build up and reset.
  for (int k = 0; k < 5000; ++k)
    pid.step(0, 0, 0, 0, 0.02);
  expect_near(pid.step(0, 0, 0, 0, 0), -55.0 * 0.002 * 0.004 * 0.02 * 5000);
  pid.reset();
  expect_near(pid.step(0, 0, 0, 0, 0), 0);
  std::cout << "angle limit, force limit, integration and reset passed\n";
}
