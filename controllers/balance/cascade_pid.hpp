#pragma once

#include <algorithm>

class CascadePid {
public:
  void reset() { integral_angle_ = 0.0; }

  double step(double x, double v, double theta, double omega, double reference) {
    constexpr double dt = 0.004;
    constexpr double angle_limit = 0.16;
    constexpr double force_limit = 10.0;
    const double error = reference - x;
    const double outer_pd = 0.22 * error - 0.20 * v;
    const double increment = 0.002 * dt * error;
    const double trial_angle = outer_pd + integral_angle_ + increment;
    const auto force_for = [&](double angle) {
      const double demand = std::clamp(angle, -angle_limit, angle_limit);
      return 55.0 * (theta - demand) + 10.0 * omega;
    };
    const double trial_force = force_for(trial_angle);
    // Increasing target lean lowers the immediate force. Accept increments
    // that unwind either limiter, freeze those that push farther into it.
    const bool pushes_angle = (trial_angle > angle_limit && increment > 0.0) ||
                              (trial_angle < -angle_limit && increment < 0.0);
    const bool pushes_force = (trial_force > force_limit && increment < 0.0) ||
                              (trial_force < -force_limit && increment > 0.0);
    if (!pushes_angle && !pushes_force)
      integral_angle_ += increment;
    return std::clamp(force_for(outer_pd + integral_angle_), -force_limit, force_limit);
  }

private:
  double integral_angle_ = 0.0;
};
