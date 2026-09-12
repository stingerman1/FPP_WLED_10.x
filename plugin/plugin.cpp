#include <atomic>
#include <chrono>
#include <mutex>
#include <thread>
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/random.h>
#include <unistd.h>
#include <poll.h>
#include <grp.h>
#include "Plugin.h"
#include "Sequence.h"
#include "Player.h"
#include "channeloutput/channeloutputthread.h"
#include "frame.hpp"
#include "commands.hpp"
#include "socket_permissions.hpp"
#include "worker.hpp"

static_assert(FPP_PLUGIN_API_VERSION == 6, "Unvalidated FPP ABI; rebuild after adapting the plugin");
static_assert(sizeof(void*) == 8, "Only 64-bit FPP is supported");
namespace {
uint64_t nowNs() {
  return std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();
}
unsigned showFlags() {
  if(!sequence) return 8;
  return (Player::INSTANCE.IsPlaying()?1:0) | (sequence->IsSequenceRunning()?2:0) | (sequence->hasBridgeData()?4:0);
}
class WLEDPlugin final : public FPPPlugins::Plugin, public FPPPlugins::ChannelDataPlugin {
  std::atomic<uint64_t> lastBusy{nowNs()};
  std::atomic<bool> needsClear{false};
  std::mutex frameMutex;
  ambient::Frame frame;
  ambient::Worker worker;
  uint64_t nonce=0;
  int socketFd=-1;
  bool forcing=false;
  std::vector<Command*> commands;
  std::array<ambient::Range,256> previousRanges{};
  size_t previousCount=0;
  const char* framePath="/run/fpp-wled/frames.sock";

  void run() {
    sockaddr_un target{}; target.sun_family=AF_UNIX;
    std::snprintf(target.sun_path,sizeof(target.sun_path),"%s","/run/fpp-wled/observer.sock");
    uint64_t lastCreated=0;
    std::vector<uint8_t> packet(70000);
    while(!worker.stopRequested()) {
      const auto now=nowNs();
      auto flags=showFlags();
      if(flags) lastBusy=now;
      // Retain brief takeovers observed on the output thread between polls.
      if(now-lastBusy.load()<25000000 && !flags) flags=8;
      uint8_t heartbeat[32]{}; memcpy(heartbeat,"FPO1",4);
      {
        std::lock_guard<std::mutex> lock(frameMutex);
        if(frame.allowed) flags|=16;
        ambient::put(heartbeat+24,frame.serial,8);
      }
      ambient::put(heartbeat+4,1,2); ambient::put(heartbeat+6,flags,2);
      ambient::put(heartbeat+8,now,8); ambient::put(heartbeat+16,nonce,8);
      sendto(socketFd,heartbeat,sizeof(heartbeat),MSG_DONTWAIT,reinterpret_cast<sockaddr*>(&target),sizeof(target));
      flags &= 15;
      bool force=false;
      for(unsigned i=0;i<32;++i) {
        const auto size=recv(socketFd,packet.data(),packet.size(),MSG_DONTWAIT|MSG_TRUNC);
        if(size<0) break;
        ambient::Frame next;
        if(size>ssize_t(packet.size()) || !ambient::decode(packet.data(),size,nowNs(),nonce,next)) continue;
        if(next.created<=lastCreated) continue;
        lastCreated=next.created;
        std::lock_guard<std::mutex> lock(frameMutex);
        frame=std::move(next);
      }
      {
        std::lock_guard<std::mutex> lock(frameMutex);
        force=(frame.allowed && ambient::fresh(frame.created,nowNs()) && !flags) || needsClear.load();
      }
      // Balanced reference counting; never change FPP's alwaysTransmit setting.
      if(force && !forcing) {StartForcingChannelOutput(); forcing=true;}
      if(!force && forcing) {StopForcingChannelOutput(); forcing=false;}
      pollfd p{socketFd,POLLIN,0}; poll(&p,1,20);
    }
    if(forcing) {StopForcingChannelOutput(); forcing=false;}
  }
public:
  WLEDPlugin():Plugin("FPP_WLED_10.x") {
    for(const auto& pair:std::vector<std::pair<std::string,std::string>>{
        {"WLED Show Start","show-start"},{"WLED Show End","show-end"},
        {"WLED Ambient Enable","ambient-enable"},{"WLED Ambient Disable","ambient-disable"},{"WLED Status","status"}}) {
      auto* command=new AmbientCommand(pair.first,pair.second);
      CommandManager::INSTANCE.addCommand(command); commands.push_back(command);
    }
    if(getrandom(&nonce,sizeof(nonce),0)!=sizeof(nonce)) return;
    socketFd=socket(AF_UNIX,SOCK_DGRAM|SOCK_NONBLOCK|SOCK_CLOEXEC,0);
    if(socketFd<0) return;
    sockaddr_un addr{}; addr.sun_family=AF_UNIX;
    std::snprintf(addr.sun_path,sizeof(addr.sun_path),"%s",framePath);
    unlink(framePath);
    if(bind(socketFd,reinterpret_cast<sockaddr*>(&addr),sizeof(addr))) {close(socketFd);socketFd=-1;return;}
    const auto* runtimeGroup = getgrnam("fpp");
    if(!runtimeGroup || !grantFrameSocketAccess(framePath, runtimeGroup->gr_gid)) {
      close(socketFd); socketFd=-1; unlink(framePath); return;
    }
    worker.start([this]{run();});
  }
  void modifySequenceData(int,uint8_t* channels) override {
    if(worker.stopRequested()) return;
    const auto now=nowNs();
    if(showFlags()) {lastBusy=now;previousCount=0;needsClear=false;return;}
    for(size_t i=0;i<previousCount;++i) memset(channels+previousRanges[i].channel,0,previousRanges[i].length);
    previousCount=0;
    needsClear=false;
    if(now-lastBusy.load()<2000000000) return;
    // No rendering, socket I/O, allocation or waiting on the output thread.
    std::unique_lock<std::mutex> lock(frameMutex,std::try_to_lock);
    if(lock.owns_lock() && ambient::apply(frame,now,false,channels)) {
      previousCount=frame.ranges.size();
      std::copy(frame.ranges.begin(),frame.ranges.end(),previousRanges.begin());
      needsClear=previousCount>0;
    }
  }
  std::function<bool()> shutdown() override {
    worker.requestStop();
    for(auto* command:commands) {CommandManager::INSTANCE.removeCommand(command);delete command;}
    commands.clear();
    return [this] {return worker.ready() && AmbientCommand::drained();};
  }
  ~WLEDPlugin() override {
    shutdown();
    // Normally already finished when FPP's readiness predicate succeeds. Keep
    // the join as a safety fallback for direct destruction / FPP's timeout.
    worker.join();
    if(socketFd>=0) {close(socketFd);socketFd=-1;unlink(framePath);}
  }
};
}
// Keep the mapping resident: FPP may still own an asynchronous command Result.
extern "C" FPPPlugins::Plugin* createPlugin() {return new WLEDPlugin();}
