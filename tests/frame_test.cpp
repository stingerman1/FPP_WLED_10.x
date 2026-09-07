#include "../plugin/frame.hpp"
#include <cassert>
#include <iostream>
int main() {
  uint8_t packet[58]{};
  memcpy(packet,"WLF1",4);
  ambient::put(packet+4,1,2);ambient::put(packet+6,1,2);
  ambient::put(packet+8,1,8);ambient::put(packet+16,100,8);ambient::put(packet+24,42,8);
  ambient::put(packet+32,1,4);ambient::put(packet+36,6,4);
  ambient::put(packet+40,3,4);ambient::put(packet+44,0,4);ambient::put(packet+48,6,4);
  memset(packet+52,127,6);
  ambient::Frame frame;
  assert(ambient::decode(packet,sizeof(packet),101,42,frame));
  uint8_t channels[12]{};
  assert(!ambient::apply(frame,101,true,channels));
  assert(channels[3]==0); // even an all-black show has ownership
  assert(ambient::apply(frame,101,false,channels));
  assert(channels[3]==127 && channels[9]==0);
  assert(!ambient::apply(frame,500000101,false,channels));
  assert(!ambient::decode(packet,sizeof(packet),99,42,frame));
  assert(!ambient::decode(packet,sizeof(packet),101,41,frame));
  for(size_t size=0;size<sizeof(packet);++size) assert(!ambient::decode(packet,size,101,42,frame));
  ambient::put(packet+40,ambient::maxChannels-1,4);
  assert(!ambient::decode(packet,sizeof(packet),101,42,frame));
  std::cout << "IPC bounds, show takeover, stale/future timestamps and session tests passed\n";
}
