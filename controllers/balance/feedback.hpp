#pragma once

#include "cascade_pid.hpp"
#include "lqr_gain.hpp"

#include <algorithm>
#include <stdexcept>
#include <string>

class Feedback {
public:
  void reset() { pid_.reset(); }

  double step(const std::string &algorithm, double x, double v, double theta,
              double omega, double reference) {
    if (algorithm == "pid")
      return pid_.step(x, v, theta, omega, reference);
    if (algorithm == "lqr") {
      const double feedback = kLqrGain[0] * (x - reference) + kLqrGain[1] * v +
                              kLqrGain[2] * theta + kLqrGain[3] * omega;
      return std::clamp(-feedback, -10.0, 10.0);
    }
    throw std::invalid_argument("unknown feedback algorithm: " + algorithm);
  }

private:
  CascadePid pid_;
};
