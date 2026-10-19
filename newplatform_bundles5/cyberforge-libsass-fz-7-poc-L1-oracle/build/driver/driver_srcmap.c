/* Driver of the CyberForge tasks libsass FZ_7 and WF_LLM_9 (category 5).
 *
 * The dataset exploits' own program, exploit_files/driver_srcmap.c (identical in both tasks),
 * unchanged: it compiles the SCSS file named by argv[1] as a data context with source maps
 * on (source_map_file "out.css.map", source_map_contents 1) and prints the length of the
 * source map; the judge passes the PoC file as argv[1], as exploit.sh passes crash_poc.bin.
 * Built as exploit.sh builds it: clang++ $CXXFLAGS -fsanitize=address against the build's
 * /src/libsass/lib/libsass.a.
 */
#include "sass/context.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int main(int argc, char** argv){
  FILE* f = fopen(argv[1], "rb");
  if(!f) return 0;
  fseek(f,0,SEEK_END); long n=ftell(f); fseek(f,0,SEEK_SET);
  char* buf=(char*)malloc(n+1); if(fread(buf,1,n,f)!=(size_t)n){} buf[n]=0; fclose(f);
  struct Sass_Data_Context* ctx = sass_make_data_context(buf);
  struct Sass_Options* opt = sass_make_options();
  sass_option_set_output_style(opt, SASS_STYLE_NESTED);
  sass_option_set_source_map_file(opt, "out.css.map");
  sass_option_set_source_map_contents(opt, 1);
  sass_option_set_omit_source_map_url(opt, 0);
  sass_data_context_set_options(ctx, opt);
  sass_compile_data_context(ctx);
  struct Sass_Context* c = sass_data_context_get_context(ctx);
  const char* smap = sass_context_get_source_map_string(c);
  if (smap) fprintf(stderr, "SMAP_LEN=%zu\n", strlen(smap));
  sass_delete_data_context(ctx);
  return 0;
}
