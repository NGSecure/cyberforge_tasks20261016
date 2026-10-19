/* Driver of the CyberForge tasks wireshark WF_RAG_6, WF_RAG_8 and WF_RAG_10 (category 5).
 * There is no dataset program behind it: the three exploits only grep wiretap/cosine.c or
 * wiretap/file_wrappers.c and run their own copies of the code, and the OSS-Fuzz build makes only
 * the fuzzshark_* dissector fuzzers, which never open a capture file. So this driver reads the PoC
 * with the build's own libwiretap.a the way capinfos and tshark read a capture file:
 * wtap_init() (as fuzz/fuzzshark.c calls it, without plugins), wtap_open_offline() with
 * WTAP_TYPE_AUTO (the file type is detected; gzip, zstd and lz4 files are decompressed by
 * wiretap/file_wrappers.c), a wtap_read() loop and wtap_close(). It prints the detected file type
 * and encapsulation, for every packet record its caplen, len and the number of data bytes read
 * (never the bytes themselves), at most 100000 records, and the final error (wtap_strerror() and
 * err_info). */
#include <stdint.h>
#include <stdio.h>

#include <glib.h>
#include <wiretap/wtap.h>

int main(int argc, char **argv) {
    if (argc < 2) return 2;
    wtap_init(false, "WIRESHARK", NULL, 0);

    int err = 0;
    char *err_info = NULL;
    wtap *wth = wtap_open_offline(argv[1], WTAP_TYPE_AUTO, &err, &err_info, false, "WIRESHARK");
    if (!wth) {
        printf("wtap_open_offline: error %d: %s%s%s\n", err, wtap_strerror(err),
               err_info ? ": " : "", err_info ? err_info : "");
        g_free(err_info);
        return 1;
    }
    printf("file type: %s, encapsulation: %s\n", wtap_file_type_subtype_name(wtap_file_type_subtype(wth)),
           wtap_encap_name(wtap_file_encap(wth)));

    wtap_rec rec;
    wtap_rec_init(&rec, 1514);
    int64_t offset = 0;
    unsigned n = 0;
    while (n < 100000 && wtap_read(wth, &rec, &err, &err_info, &offset)) {
        n++;
        if (rec.rec_type == REC_TYPE_PACKET)
            printf("record %u: packet, caplen %u, len %u, %zu data bytes\n", n,
                   rec.rec_header.packet_header.caplen, rec.rec_header.packet_header.len,
                   (size_t)ws_buffer_length(&rec.data));
        else
            printf("record %u: type %u\n", n, rec.rec_type);
        wtap_rec_reset(&rec);
    }
    if (n == 100000)
        printf("stopped after %u records\n", n);
    else if (err != 0)
        printf("wtap_read: error %d: %s%s%s\n", err, wtap_strerror(err), err_info ? ": " : "",
               err_info ? err_info : "");
    else
        printf("end of file after %u records\n", n);
    g_free(err_info);
    wtap_rec_cleanup(&rec);
    wtap_close(wth);
    return 0;
}
