#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

#include "http_server.h" /* str_buffer_free() from the build's src/apps/relay/http_server.c */

int main(void) {
    pid_t pid = fork();
    if (pid == 0) {
        /* child: call the function with NULL */
        str_buffer_free(NULL);
        /* if returned normally */
        _exit(0);
    } else if (pid > 0) {
        int status = 0;
        waitpid(pid, &status, 0);
        if (WIFSIGNALED(status)) {
            printf("EXPLOIT_TRIGGERED\n");
            return 77;
        } else if (WIFEXITED(status)) {
            int ec = WEXITSTATUS(status);
            if (ec != 0) {
                printf("EXPLOIT_TRIGGERED\n");
                return 77;
            } else {
                printf("NO_TRIGGER\n");
                return 0;
            }
        } else {
            printf("NO_TRIGGER\n");
            return 0;
        }
    } else {
        perror("fork");
        return 1;
    }
}
