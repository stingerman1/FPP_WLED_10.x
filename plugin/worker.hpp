#pragma once
#include <atomic>
#include <thread>
#include <utility>

namespace ambient {
// FPP polls readiness before destroying the plugin. Requesting stop must never
// wait on the worker; joining belongs to destruction after readiness is true.
class Worker {
  std::atomic<bool> stopping{false};
  std::atomic<bool> finished{true};
  std::thread thread;
public:
  template<class Work> void start(Work work) {
    finished = false;
    try {
      thread = std::thread([this, work = std::move(work)] {
        work();
        finished = true;
      });
    } catch (...) {
      finished = true;
      throw;
    }
  }
  void requestStop() { stopping = true; }
  bool stopRequested() const { return stopping.load(); }
  bool ready() const { return finished.load(); }
  void join() {
    requestStop();
    if (thread.joinable()) thread.join();
  }
  ~Worker() { join(); }
};
}
