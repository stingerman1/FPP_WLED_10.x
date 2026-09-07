#pragma once
#include <algorithm>
#include <cstdint>
#include <cstring>
#include <vector>

namespace ambient {
constexpr uint64_t timeoutNs = 500000000;
constexpr uint32_t maxChannels = 8192*1024;
struct Range {uint32_t channel, source, length;};
struct Frame {
  uint64_t serial=0, created=0, nonce=0;
  bool allowed=false;
  std::vector<Range> ranges;
  std::vector<uint8_t> pixels;
};
inline uint64_t little(const uint8_t* p, unsigned n) {
  uint64_t v=0; for(unsigned i=0;i<n;++i) v |= uint64_t(p[i]) << (8*i); return v;
}
inline void put(uint8_t* p,uint64_t v,unsigned n) {
  for(unsigned i=0;i<n;++i) p[i]=v>>(8*i);
}
inline bool fresh(uint64_t created,uint64_t now) {return created<=now && now-created<=timeoutNs;}
inline bool decode(const uint8_t* p,size_t size,uint64_t now,uint64_t nonce,Frame& result) {
  if(size<40 || memcmp(p,"WLF1",4) || little(p+4,2)!=1 || little(p+6,2)>1) return false;
  const auto serial=little(p+8,8), created=little(p+16,8);
  const auto n=little(p+32,4), length=little(p+36,4);
  if(little(p+24,8)!=nonce || !fresh(created,now) || n>256 || length>64000 || size!=40+n*12+length) return false;
  Frame out; out.serial=serial; out.created=created; out.nonce=nonce; out.allowed=little(p+6,2);
  for(unsigned i=0;i<n;++i) {
    const auto r=p+40+i*12;
    Range range{uint32_t(little(r,4)),uint32_t(little(r+4,4)),uint32_t(little(r+8,4))};
    if(!range.length || uint64_t(range.channel)+range.length>maxChannels || uint64_t(range.source)+range.length>length) return false;
    for(const auto& prev:out.ranges)
      if(range.channel<prev.channel+prev.length && prev.channel<range.channel+range.length) return false;
    out.ranges.push_back(range);
  }
  out.pixels.assign(p+40+n*12,p+size);
  result=std::move(out); return true;
}
inline bool apply(const Frame& frame,uint64_t now,bool showOwned,uint8_t* channels) {
  if(showOwned || !frame.allowed || !fresh(frame.created,now)) return false;
  for(const auto& r:frame.ranges) memcpy(channels+r.channel,frame.pixels.data()+r.source,r.length);
  return true;
}
}
