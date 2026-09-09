.DEFAULT_GOAL := all
SRCDIR ?= /opt/fpp/src
include $(SRCDIR)/makefiles/common/setup.mk

LINK_FPP ?= 1
ifeq ($(LINK_FPP),1)
FPP_LIBS := -L$(SRCDIR) -Wl,-rpath,$(SRCDIR) -lfpp
endif

.PHONY: all clean
all: build/libFPP_WLED_10.x.so
	python3 scripts/verify-abi.py "$(SRCDIR)" $<
	# Replace the loader entry atomically, including when it was a release symlink.
	cp $< libFPP_WLED_10.x.so.new
	mv -f libFPP_WLED_10.x.so.new libFPP_WLED_10.x.so

build/libFPP_WLED_10.x.so: plugin/plugin.cpp Makefile $(wildcard plugin/*.hpp) $(SRCDIR)/Plugin.h $(wildcard $(SRCDIR)/libfpp.so)
	mkdir -p build
	$(CCACHE) $(CXXCOMPILER) $(CFLAGS) $(CXXFLAGS) -O2 -Wall -Wextra -Wno-unused-parameter -fPIC -shared -pthread -I$(SRCDIR) -MMD -MP -MF build/plugin.d $< $(LDFLAGS) $(FPP_LIBS) -o $@.new
	mv -f $@.new $@

clean:
	rm -f build/libFPP_WLED_10.x.so build/plugin.d libFPP_WLED_10.x.so
