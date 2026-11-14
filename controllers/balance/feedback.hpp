#pragma once

#include "cascade_pid.hpp"

#include <stdexcept>
#include <string>

class Feedback {
public:
  void reset() { pid_.reset(); }

  double step(const std::string &algorithm, double x, double v, double theta,
              double omega, double reference) {
    if (algorithm == "pid")
      return pid_.step(x, v, theta, omega, reference);
    throw std::invalid_argument("unknown feedback algorithm: " + algorithm);
  }

private:
  CascadePid pid_;
};
