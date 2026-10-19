/* Driver of the CyberForge task libsass WF_LLM_2 (category 5).
 *
 * The dataset exploit's own program, exploit_files/driver_c2ast.c, unchanged: it registers a
 * custom C function myfn() that returns a two-element comma list, compiles the SCSS file
 * named by argv[1] as a data context, and so converts that list back through c2ast(); the
 * judge passes the PoC file as argv[1], as exploit.sh passes crash_poc.bin. Built as
 * exploit.sh builds it: clang++ $CXXFLAGS -fsanitize=address against the build's
 * /src/libsass/lib/libsass.a.
 */
#include "sass/context.h"
#include "sass/functions.h"
#include "sass/values.h"
#include <stdio.h>
#include <stdlib.h>
union Sass_Value* myfn(const union Sass_Value* args, Sass_Function_Entry cb, struct Sass_Compiler* comp){
  union Sass_Value* lst = sass_make_list(2, SASS_COMMA, 0);
  sass_list_set_value(lst, 0, sass_make_number(1, ""));
  sass_list_set_value(lst, 1, sass_make_number(2, ""));
  return lst;
}
int main(int argc, char** argv){
  FILE* f=fopen(argv[1],"rb"); if(!f) return 0;
  fseek(f,0,SEEK_END); long n=ftell(f); fseek(f,0,SEEK_SET);
  char* buf=(char*)malloc(n+1); if(fread(buf,1,n,f)!=(size_t)n){} buf[n]=0; fclose(f);
  struct Sass_Data_Context* ctx = sass_make_data_context(buf);
  struct Sass_Options* opt = sass_make_options();
  Sass_Function_List fns = sass_make_function_list(1);
  sass_function_set_list_entry(fns, 0, sass_make_function("myfn()", myfn, 0));
  sass_option_set_c_functions(opt, fns);
  sass_data_context_set_options(ctx, opt);
  sass_compile_data_context(ctx);
  sass_delete_data_context(ctx);
  return 0;
}
