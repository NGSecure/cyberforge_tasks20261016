/* Driver of this task (category 5).
 * Adapted from exploit_files/exploit.sh, which runs /out/<project>_read_fuzzer (the project's own
 * fuzzing/<project>_read_fuzzer.c) on its payload file. This program is linked with that harness
 * source, unchanged, and calls its LLVMFuzzerTestOneInput once on the PoC file. The only
 * change is how the file is read: it is mapped read-only (mmap) instead of being copied into
 * the heap as libFuzzer does, so that the judge's allocation limit applies to <project>'s own
 * allocations rather than to copies of the input. */
#include <fcntl.h>
#include <stddef.h>
#include <stdint.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size);

int main(int argc, char **argv) {
    static const uint8_t empty[1];
    struct stat st;
    void *p;
    int fd;

    if (argc < 2)
        return 2;
    fd = open(argv[1], O_RDONLY);
    if (fd < 0 || fstat(fd, &st) != 0)
        return 2;
    if (st.st_size == 0) {
        LLVMFuzzerTestOneInput(empty, 0);
        close(fd);
        return 0;
    }
    p = mmap(NULL, (size_t)st.st_size, PROT_READ, MAP_PRIVATE, fd, 0);
    close(fd);
    if (p == MAP_FAILED)
        return 2;
    LLVMFuzzerTestOneInput((const uint8_t *)p, (size_t)st.st_size);
    munmap(p, (size_t)st.st_size);
    return 0;
}
