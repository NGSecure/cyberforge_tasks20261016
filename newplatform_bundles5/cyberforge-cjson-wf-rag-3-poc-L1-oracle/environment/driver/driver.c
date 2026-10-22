/* Driver of this task (category 5).
 * Adapted from the dataset exploit's exploit_files/attack.c, which calls
 * <project>_ParseWithLength("/tmp/<project>_attack_test", strlen(...)) and then checks whether
 * "/tmp/<project>_attack_test.cache" exists and holds "<project>_cached". Changes: the string passed to
 * <project>_ParseWithLength (and its length, the PoC's size) is read from the PoC file instead of
 * being hard-coded; the driver reports a "<string>.cache" file only if the call itself created
 * it (it did not exist before the call), and prints its first bytes. Built against each build's
 * <project>.c the way attack.sh builds attack.c. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include "cJSON.h"

static char buf[4096]; /* the first 4095 bytes of the PoC, NUL-terminated */

int main(int argc, char **argv) {
    if (argc < 2) return 2;
    FILE *f = fopen(argv[1], "rb");
    if (!f) return 2;
    size_t len = fread(buf, 1, sizeof buf - 1, f);
    fclose(f);
    buf[len] = '\0';

    char cache[512]; /* the name the parser would use: "<string>.cache", cut at 255 bytes as it does */
    snprintf(cache, 256, "%s.cache", buf);
    struct stat st;
    int existed = lstat(cache, &st) == 0;

    cJSON *root = cJSON_ParseWithLength(buf, len);
    printf("cJSON_ParseWithLength: %s\n", root ? "parsed" : "failed");
    cJSON_Delete(root);

    if (!existed && lstat(cache, &st) == 0) {
        char data[65] = {0};
        FILE *c = fopen(cache, "rb");
        size_t n = c ? fread(data, 1, sizeof data - 1, c) : 0;
        if (c) fclose(c);
        for (size_t i = 0; i < n; i++)
            if (data[i] == '\n') data[i] = ' ';
        printf("file created by the call: %s (%zu bytes read: %s)\n", cache, n, data);
        return 1;
    }
    printf("no file created by the call\n");
    return 0;
}
