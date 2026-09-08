#pragma once
#include <sys/stat.h>
#include <unistd.h>

// FPP may run as root; the renderer runs as fpp. Socket write permission is
// independent of its parent directory and must not depend on FPP's umask.
inline bool grantFrameSocketAccess(const char* path, gid_t runtimeGroup) {
    return chown(path, static_cast<uid_t>(-1), runtimeGroup) == 0 && chmod(path, 0660) == 0;
}
