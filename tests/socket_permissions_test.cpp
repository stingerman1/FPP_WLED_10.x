#include "../plugin/socket_permissions.hpp"
#include <cassert>
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <grp.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/wait.h>

int main() {
    assert(geteuid() == 0); // Exercise root FPP -> unprivileged renderer.
    char directory[] = "/tmp/wled-permissions-XXXXXX";
    assert(mkdtemp(directory));
    assert(chown(directory, 0, 65534) == 0 && chmod(directory, 0770) == 0);
    sockaddr_un address{}; address.sun_family = AF_UNIX;
    snprintf(address.sun_path, sizeof(address.sun_path), "%s/frames.sock", directory);
    int server = socket(AF_UNIX, SOCK_DGRAM, 0); assert(server >= 0);
    assert(bind(server, reinterpret_cast<sockaddr*>(&address), sizeof(address)) == 0);
    assert(chmod(address.sun_path, 0755) == 0);
    auto attempt = [&](bool permitted) {
        pid_t child = fork(); assert(child >= 0);
        if(child == 0) {
            if(setgroups(0, nullptr) || setgid(65534) || setuid(65534)) _exit(3);
            int sender = socket(AF_UNIX, SOCK_DGRAM, 0);
            auto count = sendto(sender, "x", 1, 0, reinterpret_cast<sockaddr*>(&address), sizeof(address));
            _exit((permitted ? count == 1 : count == -1 && errno == EACCES) ? 0 : 2);
        }
        int status; assert(waitpid(child, &status, 0) == child);
        assert(WIFEXITED(status) && WEXITSTATUS(status) == 0);
    };
    attempt(false);
    assert(grantFrameSocketAccess(address.sun_path, 65534));
    struct stat info{}; assert(stat(address.sun_path, &info) == 0);
    assert(info.st_uid == 0 && info.st_gid == 65534 && (info.st_mode & 0777) == 0660);
    attempt(true);
    char packet; assert(recv(server, &packet, 1, 0) == 1);
    close(server); unlink(address.sun_path); rmdir(directory);
    puts("Root FPP socket permits only the configured runtime group");
}
