#include <webots/Supervisor.hpp>
#include <iostream>

int main() {
  webots::Supervisor robot;
  for (int i = 0; i < 5; ++i) {
    if (robot.step(4) == -1)
      return 1;
    std::cout << "smoke t=" << robot.getTime() << std::endl;
  }
  robot.simulationQuit(0);
  robot.step(2);
}
