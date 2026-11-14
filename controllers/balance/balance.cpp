#include <webots/Motor.hpp>
#include <webots/Node.hpp>
#include <webots/PositionSensor.hpp>
#include <webots/Supervisor.hpp>

#ifndef OPEN_LOOP_ONLY
#include "feedback.hpp"
#endif

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>

namespace {
constexpr int physicsMs = 2;
constexpr int controlMs = 4;
constexpr double sampleSeconds = controlMs / 1000.0;
constexpr double pi = 3.141592653589793;

struct Options {
  std::string algorithm = "lqr";
  std::string scenario = "demo";
  double duration = 14.0;
  bool batch = false;
  std::string csv;
  std::string movie;
};

Options parse(int argc, char **argv) {
  Options options;
  for (int i = 1; i < argc; ++i) {
    const std::string arg = argv[i];
    const auto equals = arg.find('=');
    if (equals == std::string::npos)
      throw std::invalid_argument("expected --name=value: " + arg);
    const auto key = arg.substr(0, equals);
    const auto value = arg.substr(equals + 1);
    if (key == "--algorithm")
      options.algorithm = value;
    else if (key == "--scenario")
      options.scenario = value;
    else if (key == "--duration") {
      std::size_t consumed = 0;
      options.duration = std::stod(value, &consumed);
      if (consumed != value.size() || !std::isfinite(options.duration) || options.duration <= 0 ||
          options.duration > 3600 || std::abs(options.duration / sampleSeconds - std::round(options.duration / sampleSeconds)) > 1e-7)
        throw std::invalid_argument("duration must be a positive multiple of 0.004 s, up to 3600 s");
    } else if (key == "--batch" && (value == "0" || value == "1"))
      options.batch = value == "1";
    else if (key == "--csv")
      options.csv = value;
    else if (key == "--movie")
      options.movie = value;
    else
      throw std::invalid_argument("unknown option: " + arg);
  }
  const bool open = options.scenario == "open-force" || options.scenario == "open-tilt";
  if (!open && options.scenario != "demo" && options.scenario != "step" &&
      options.scenario != "pulse" && options.scenario != "initial")
    throw std::invalid_argument("unknown scenario: " + options.scenario);
  if ((open && options.algorithm != "open") ||
      (!open && options.algorithm != "lqr" && options.algorithm != "pid"))
    throw std::invalid_argument("algorithm does not match scenario: " + options.algorithm);
#ifdef OPEN_LOOP_ONLY
  if (!open)
    throw std::invalid_argument("this build supports only open-loop scenarios");
#endif
  return options;
}

void overlay(webots::Supervisor &robot, const Options &options, int ms, double reference,
             double x, double theta, double disturbance, bool failed) {
  std::string phase = options.scenario;
  if (options.scenario == "demo")
    phase = ms < 3000 ? "release from 5 deg" : ms < 8000 ? "position step" : "disturbance recovery";
  if (disturbance != 0)
    phase = "external pulse +2 N";
  if (failed)
    phase = "trial stopped: stability limit";
  std::ostringstream info;
  info << std::fixed << std::setprecision(2) << options.algorithm << "   |   " << phase
       << "   |   t = " << ms / 1000.0 << " s";
  robot.setLabel(0, info.str(), 0.035, 0.035, 0.064, 0xF6F8FA, 0, "Arial");
  std::ostringstream state;
  state << std::fixed << std::setprecision(3) << "target " << reference << " m     x " << x
        << " m     angle " << std::setprecision(2) << theta * 180 / pi << " deg";
  robot.setLabel(1, state.str(), 0.035, 0.10, 0.055, 0xC7DEE5, 0, "Arial");
}

void finishMovie(webots::Supervisor &robot) {
  robot.movieStopRecording();
  const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(90);
  do {
    if (robot.step(physicsMs) == -1)
      throw std::runtime_error("simulator ended while encoding the movie");
    if (robot.movieFailed())
      throw std::runtime_error("Webots movie encoding failed");
    if (robot.movieIsReady())
      return;
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
  } while (std::chrono::steady_clock::now() < deadline);
  throw std::runtime_error("Webots movie encoding timed out");
}

void simulate(webots::Supervisor &robot, const Options &options) {
  auto *motor = robot.getMotor("drive");
  auto *encoder = robot.getPositionSensor("cart_encoder");
  auto *hinge = robot.getPositionSensor("pendulum_encoder");
  auto *cart = robot.getFromDef("CART");
  if (!motor || !encoder || !hinge || !cart || robot.getBasicTimeStep() != physicsMs)
    throw std::runtime_error("expected a 2 ms cart-pole world with both encoders, drive and CART");
  std::ofstream log;
  if (!options.csv.empty()) {
    log.exceptions(std::ios::badbit | std::ios::failbit);
    log.open(std::filesystem::u8path(options.csv));
    log << "time_s,reference_m,x_m,v_m_s,theta_rad,omega_rad_s,force_N,external_N\n";
    log << std::setprecision(12);
  }
#ifndef OPEN_LOOP_ONLY
  Feedback feedback;
  feedback.reset();
#endif
  encoder->enable(physicsMs);
  hinge->enable(physicsMs);
  motor->setForce(0);
  if (robot.step(physicsMs) == -1)
    throw std::runtime_error("simulator ended before the first sensor reading");
  double previousX = encoder->getValue();
  double previousAngle = hinge->getValue();
  const bool recordMovie = !options.movie.empty();
  if (recordMovie)
    robot.movieStartRecording(options.movie, 960, 540, 0, 90, 1, false);
  const int endMs = static_cast<int>(std::lround(options.duration * 1000));
  const int pulseStart = options.scenario == "demo" ? 8000 : 2000;
  const int stepStart = options.scenario == "demo" ? 3000 : 2000;
  const bool hasPulse = options.scenario == "demo" || options.scenario == "pulse";
  const bool hasStep = options.scenario == "demo" || options.scenario == "step";
  const bool finiteRun = options.batch || recordMovie || log.is_open() || options.scenario != "demo";
  for (int ms = 0;; ms += controlMs) {
    const double x = encoder->getValue();
    const double theta = hinge->getValue();
    const double v = (x - previousX) / sampleSeconds;
    const double omega = (theta - previousAngle) / sampleSeconds;
    previousX = x;
    previousAngle = theta;
    const bool failed = !std::isfinite(x) || !std::isfinite(theta) || !std::isfinite(v) || !std::isfinite(omega) ||
                        std::abs(x) >= 1.5 || std::abs(theta) >= pi / 6;
    const bool end = failed || (finiteRun && ms == endMs);
    const double reference = hasStep && ms >= stepStart ? 0.2 : 0.0;
    const double external = !end && hasPulse && ms >= pulseStart && ms < pulseStart + 100 ? 2.0 : 0.0;
    double force = 0;
    if (!end) {
      if (options.scenario == "open-force")
        force = 1.0;
#ifndef OPEN_LOOP_ONLY
      else if (options.algorithm != "open")
        force = std::clamp(feedback.step(options.algorithm, x, v, theta, omega, reference), -10.0, 10.0);
#endif
    }
    if (!std::isfinite(force))
      throw std::runtime_error("controller produced a nonfinite force");
    if (log.is_open())
      log << ms / 1000.0 << ',' << reference << ',' << x << ',' << v << ',' << theta << ','
          << omega << ',' << force << ',' << external << '\n';
    if ((!options.batch || recordMovie) && (ms % 40 == 0 || end))
      overlay(robot, options, ms, reference, x, theta, external, failed);
    if (!finiteRun && !failed && ms == endMs) {
      std::cout << std::setprecision(10) << "BALANCE_DEMO algorithm=" << options.algorithm
                << " time=" << ms / 1000.0 << " target=" << reference << " x=" << x
                << " theta=" << theta << std::endl;
      const char *check = std::getenv("BALANCE_VERIFY_DEFAULT");
      if (check && std::string(check) == "1") {
        robot.simulationQuit(0);
        robot.step(physicsMs);
        return;
      }
    }
    motor->setForce(force);
    if (end) {
      if (log.is_open())
        log.close();
      std::cout << "BALANCE_DONE algorithm=" << options.algorithm << " scenario=" << options.scenario
                << " time=" << ms / 1000.0 << " status=" << (failed ? "limit" : "complete") << std::endl;
      if (recordMovie)
        finishMovie(robot);
      if (options.batch)
        robot.simulationQuit(0);
      else
        robot.simulationSetMode(webots::Supervisor::SIMULATION_MODE_PAUSE);
      robot.step(physicsMs);
      return;
    }
    if (external != 0) {
      // addForce applies only to the next physics step. The motor command is held for 4 ms.
      const double push[] = {external, 0.0, 0.0};
      for (int elapsed = 0; elapsed < controlMs; elapsed += physicsMs) {
        cart->addForce(push, false);
        if (robot.step(physicsMs) == -1)
          return;
      }
    } else if (robot.step(controlMs) == -1)
      return;
  }
}
}  // namespace

int main(int argc, char **argv) {
  webots::Supervisor robot;
  try {
    simulate(robot, parse(argc, argv));
    return 0;
  } catch (const std::exception &error) {
    std::cerr << "balance: " << error.what() << std::endl;
    robot.simulationQuit(1);
    robot.step(physicsMs);
    return 1;
  }
}
