#include "../plugin/worker.hpp"
#include <cassert>
#include <chrono>
#include <future>

int main() {
  ambient::Worker empty;
  assert(empty.ready());
  empty.requestStop();
  empty.requestStop();
  empty.join();

  ambient::Worker worker;
  std::promise<void> entered, release;
  auto released = release.get_future();
  worker.start([&] { entered.set_value(); released.wait(); });
  entered.get_future().wait();
  // Hold the worker deliberately. Stop must return before it can finish.
  auto request = std::async(std::launch::async, [&] { worker.requestStop(); });
  const bool nonblocking = request.wait_for(std::chrono::seconds(1)) == std::future_status::ready;
  if (!nonblocking) release.set_value(); // allow a regressed implementation to exit
  request.get();
  assert(nonblocking);
  assert(worker.stopRequested());
  assert(!worker.ready());
  release.set_value();
  worker.join();
  assert(worker.ready());
  worker.join();
}
