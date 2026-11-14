CXX_SOURCES = balance.cpp
CXXFLAGS = -std=c++17
ifeq ($(OPEN_LOOP_ONLY),1)
CFLAGS += -DOPEN_LOOP_ONLY
endif
include $(WEBOTS_HOME)/resources/Makefile.include
