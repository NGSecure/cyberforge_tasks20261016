// Category-5 driver for this task.
//
// Adapted from tests/gtest_factory.cpp, TEST(BehaviorTreeFactory, CreateTreeFromFile) (the unit test
// the exploit runs): BehaviorTreeFactory factory; Tree tree = factory.createTreeFromFile(path);
// tree.tickWhileRunning() must return SUCCESS. What changed: the path is the PoV file (argv[1],
// an absolute path the judge chooses) instead of tests/trees/parent_no_include.xml, and the
// result is printed instead of checked: "tick=<status>" or, if loading throws,
// "load-error: <message>".
// Added: before that, the PoV's text is checked with createTreeFromText on a separate factory
// (the same parser, without a file path); if that fails the driver prints "invalid-tree: ..." and
// stops, so a PoV that is not a usable tree shows nothing about createTreeFromFile.
#include "behaviortree_cpp/bt_factory.h"

#include <cstdio>
#include <exception>
#include <fstream>
#include <iterator>
#include <string>

int main(int argc, char** argv)
{
  if(argc != 2)
  {
    std::fprintf(stderr, "usage: %s <tree.xml>\n", argv[0]);
    return 2;
  }
  std::ifstream in(argv[1], std::ios::binary);
  if(!in)
  {
    std::printf("cannot open the PoV\n");
    return 1;
  }
  std::string text((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
  if(text.size() > (16u << 20))
  {
    std::printf("the PoV is larger than 16 MiB\n");
    return 1;
  }
  {
    BT::BehaviorTreeFactory check;
    try
    {
      BT::Tree checked = check.createTreeFromText(text);
      (void)checked;
    }
    catch(const std::exception& e)
    {
      std::printf("invalid-tree: %s\n", e.what());
      return 0;
    }
  }
  BT::BehaviorTreeFactory factory;
  try
  {
    BT::Tree tree = factory.createTreeFromFile(argv[1]);
    BT::NodeStatus status = tree.tickWhileRunning();
    std::printf("tick=%s\n", BT::toStr(status).c_str());
  }
  catch(const std::exception& e)
  {
    std::printf("load-error: %s\n", e.what());
  }
  return 0;
}
