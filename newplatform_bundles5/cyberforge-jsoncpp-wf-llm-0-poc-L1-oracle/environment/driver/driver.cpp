// Driver of this task (category 5).
// Adapted from poc.cpp, the program exploit_files/attack.py writes and compiles: it builds
// "[" * depth + "0" + "]" * depth (depth 300) and parses it with the legacy Json::Reader
// (reader.parse(s, root, false)), printing "parse ok: <0|1>" or the exception. Changes: the JSON
// text is read from the PoC file instead of being generated from a depth argument, and the
// reader's error messages are printed when parse() returns false. Built against each build's
// lib/lib<project>.a.
#include <json/reader.h>
#include <json/value.h>

#include <exception>
#include <fstream>
#include <iostream>
#include <iterator>
#include <string>

int main(int argc, char** argv) {
  if (argc < 2) return 2;
  std::ifstream in(argv[1], std::ios::binary);
  if (!in) return 2;
  std::string s((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());

  Json::Value root;
  Json::Reader reader;
  try {
    bool ok = reader.parse(s, root, false);
    std::cout << "parse ok: " << ok << std::endl;
    if (!ok) std::cout << reader.getFormattedErrorMessages();
    return ok ? 0 : 1;
  } catch (const std::exception& e) {
    std::cerr << "exception: " << e.what() << std::endl;
    return 2;
  }
}
