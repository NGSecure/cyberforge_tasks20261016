/* Category-5 driver for this task.
 *
 * Adapted from tests/b2nd/test_b2nd_delete.c (the unit test the exploit runs) and the exploit's own
 * setup: exploit.sh creates the directory test_delete.b2frame/ holding a file "file" ("some data")
 * and runs test_b2nd_delete, whose blosc2_remove_urlpath("test_delete.b2frame") must delete it.
 * What changed: the path handed to blosc2_remove_urlpath is the first line of the PoV's input file
 * (relative to the PoV's directory, which is the working directory) instead of the test's fixed
 * urlpath, and the driver prints the return value and whether the path still exists afterwards
 * instead of the test's own checks. Only blosc2_init, blosc2_remove_urlpath and blosc2_destroy are
 * called.
 *
 * For safety the path must be relative, without "." or ".." components, and no component may be a
 * symbolic link (the driver deletes what the path names); otherwise it prints "bad-path".
 * Output: "rc=<return value> exists=<0|1>".
 */
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>

#include "blosc2.h"

#define MAX_PATH_LEN 1024

static int bad_path(char *path) {
    char prefix[MAX_PATH_LEN + 1];
    size_t len = strlen(path);
    if (len == 0) return 1;
    if (path[0] == '/') return 1;
    /* every component: not empty, not "." or "..", not a symbolic link */
    size_t start = 0;
    while (start <= len) {
        size_t end = start;
        while (end < len && path[end] != '/') end++;
        size_t n = end - start;
        if (n == 0 && end < len) return 1; /* "a//b" */
        if ((n == 1 && path[start] == '.') || (n == 2 && path[start] == '.' && path[start + 1] == '.'))
            return 1;
        if (n > 0) {
            struct stat st;
            memcpy(prefix, path, end);
            prefix[end] = '\0';
            if (lstat(prefix, &st) == 0 && S_ISLNK(st.st_mode)) return 1;
        }
        start = end + 1;
    }
    return 0;
}

int main(int argc, char **argv) {
    if (argc != 2) {
        fprintf(stderr, "usage: %s <input>\n", argv[0]);
        return 2;
    }
    FILE *f = fopen(argv[1], "rb");
    if (!f) {
        printf("bad-path: no input file\n");
        return 0;
    }
    char path[MAX_PATH_LEN + 2];
    if (!fgets(path, sizeof path, f)) path[0] = '\0';
    fclose(f);
    size_t len = strlen(path);
    if (len && path[len - 1] == '\n') path[--len] = '\0';
    if (len && path[len - 1] == '\r') path[--len] = '\0';
    if (len > MAX_PATH_LEN || bad_path(path)) {
        printf("bad-path\n");
        return 0;
    }
    blosc2_init();
    int rc = blosc2_remove_urlpath(path);
    struct stat st;
    int exists = lstat(path, &st) == 0;
    printf("rc=%d exists=%d\n", rc, exists);
    blosc2_destroy();
    return 0;
}
