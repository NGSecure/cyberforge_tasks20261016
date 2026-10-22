// Driver of this task (category 5).
// Adapted from exploit.cpp, the program exploit_files/attack.py writes and compiles: it looks up
// key "pwn" through operator[](std::string_view) on a const, default-constructed (null)
// Json::Value, binds the result to a non-const Value& and assigns 12345, then prints VULN if the
// const value changed. That program does not compile against the fixed header (the const
// operator returns const Value&), so here: the document (first line of the PoC, parsed with
// Json::CharReaderBuilder; "null" is the exploit's default value) and the keys (one per
// following line) are read from the PoC; each key is looked up through a const reference with
// operator[](std::string_view), the result is bound to a const reference only, and the driver
// prints what the lookups returned and the whole document afterwards. Built with C++17
// (<project>_HAS_STRING_VIEW) against each build's lib/lib<project>.a.
#include <json/json.h>

#include <exception>
#include <fstream>
#include <iostream>
#include <memory>
#include <sstream>
#include <string>
#include <string_view>
#include <vector>

static std::string compact(const Json::Value& v) {
  Json::StreamWriterBuilder w;
  w["indentation"] = "";
  return Json::writeString(w, v);
}

int main(int argc, char** argv) {
  if (argc < 2) return 2;
  std::ifstream in(argv[1], std::ios::binary);
  if (!in) return 2;
  std::vector<std::string> lines;
  for (std::string line; std::getline(in, line);) {
    if (!line.empty() && line.back() == '\r') line.pop_back();
    lines.push_back(line);
  }
  if (lines.empty()) {
    std::cout << "no document\n";
    return 0;
  }

  Json::Value root;
  Json::CharReaderBuilder b;
  std::unique_ptr<Json::CharReader> reader(b.newCharReader());
  std::string errs;
  const std::string& doc = lines[0];
  if (!reader->parse(doc.data(), doc.data() + doc.size(), &root, &errs)) {
    std::cout << "document does not parse: " << errs << "\n";
    return 0;
  }
  std::cout << "document: " << compact(root) << "\n";

  const Json::Value& croot = root;
  for (size_t i = 1; i < lines.size(); i++) {
    std::string_view key(lines[i]);
    try {
      const Json::Value& v = croot[key];
      std::cout << "lookup \"" << lines[i] << "\": " << compact(v) << "\n";
    } catch (const std::exception& e) {
      std::cout << "lookup \"" << lines[i] << "\": exception: " << e.what() << "\n";
    }
  }
  std::cout << "document after the lookups: " << compact(root) << "\n";
  return 0;
}
