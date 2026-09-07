#pragma once
#include <future>
#include "commands/Commands.h"

// Commands can originate on FPP's output thread. Only enqueue work there;
// the returned Result lets FPP observe completion without blocking the caller.
class AmbientCommand final : public Command {
  std::string operation;
  inline static std::atomic<unsigned> pending{0};
  struct Reply {bool error;std::string text;};
  class AsyncResult final : public Command::Result {
    std::future<Reply> future;
    bool done=false, error=false;
  public:
    explicit AsyncResult(std::future<Reply> f):future(std::move(f)) {}
    bool isDone() override {
      if(!done && future.wait_for(std::chrono::seconds(0))==std::future_status::ready) {
        try {auto reply=future.get();m_result=std::move(reply.text);error=reply.error;}
        catch(...) {m_result="Runtime command worker failed";error=true;}
        done=true;
      }
      return done;
    }
    bool isError() override {isDone();return error;}
    const std::string& get() override {isDone();return m_result;}
  };
public:
  AmbientCommand(const std::string& name,const std::string& op):Command(name),operation(op) {
    if(op=="show-start" || op=="show-end") args.emplace_back("Source","string","Stable show source identifier");
  }
  std::unique_ptr<Result> run(const std::vector<std::string>& values) override {
    bool needsSource=operation=="show-start" || operation=="show-end";
    if(needsSource && (values.size()!=1 || values[0].empty())) return std::make_unique<ErrorResult>("Source is required");
    if(pending.fetch_add(1)>=8) {--pending;return std::make_unique<ErrorResult>("Ambient command queue is full");}
    Json::Value body;body["operation"]=operation;
    if(needsSource) body["source"]=values[0];
    Json::StreamWriterBuilder writer;
    auto json=Json::writeString(writer,body);
    // A packaged-task future has no joining destructor. FPP may discard a
    // Result on its output thread; that must never wait for network completion.
    try {
    auto task=std::make_shared<std::packaged_task<Reply()>>([json] {
      struct Guard {~Guard(){--pending;}} guard;
      int fd=socket(AF_UNIX,SOCK_STREAM|SOCK_CLOEXEC,0);
      if(fd<0) return Reply{true,"Cannot open runtime command socket"};
      struct SocketGuard {int fd;~SocketGuard(){close(fd);}} socketGuard{fd};
      timeval timeout{4,0};setsockopt(fd,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof(timeout));
      setsockopt(fd,SOL_SOCKET,SO_SNDTIMEO,&timeout,sizeof(timeout));
      sockaddr_un address{};address.sun_family=AF_UNIX;strcpy(address.sun_path,"/run/fpp-wled/control.sock");
      if(connect(fd,reinterpret_cast<sockaddr*>(&address),sizeof(address))) return Reply{true,"Runtime is unavailable; show handoff not acknowledged"};
      std::string request="POST /api/command HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\nContent-Type: application/json\r\nContent-Length: "+std::to_string(json.size())+"\r\n\r\n"+json;
      size_t offset=0;
      while(offset<request.size()) {
        auto n=send(fd,request.data()+offset,request.size()-offset,MSG_NOSIGNAL);
        if(n<=0) return Reply{true,"Runtime command send failed"};
        offset+=n;
      }
      std::string response;char buffer[4096];ssize_t n;
      while((n=recv(fd,buffer,sizeof(buffer),0))>0 && response.size()<65536) response.append(buffer,n);
      if(n<0) return Reply{true,"Runtime command timed out"};
      bool ok=response.rfind("HTTP/1.1 200 ",0)==0;
      auto split=response.find("\r\n\r\n");
      return Reply{!ok,split==std::string::npos?"Invalid runtime response":response.substr(split+4)};
    });
    auto result=std::make_unique<AsyncResult>(task->get_future());
    std::thread([task]{(*task)();}).detach();
    return result;
    } catch(...) {--pending;return std::make_unique<ErrorResult>("Cannot start ambient command worker");}
  }
  static bool drained() {return pending.load()==0;}
};
