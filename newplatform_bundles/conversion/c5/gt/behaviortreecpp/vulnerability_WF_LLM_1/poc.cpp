// Ground truth for behaviortreecpp WF_LLM_1: tests/gtest_loggers.cpp, the LoggerTest fixture
// (SetUp, createSimpleTree, TearDown) and TEST_F(LoggerTest, FileLogger2_MultipleTicks) -- the test
// exploit.sh runs -- copied into main() without gtest. Unchanged otherwise: the same XML, the same
// FileLogger2 file under temp_directory_path()/bt_logger_test, three tickWhileRunning()/haltTree()
// cycles and flush().
#include "behaviortree_cpp/bt_factory.h"
#include "behaviortree_cpp/loggers/bt_file_logger_v2.h"

#include <cstdio>
#include <filesystem>
#include <string>

using namespace BT;

int main()
{
  BT::BehaviorTreeFactory factory;
  std::string test_dir = std::filesystem::temp_directory_path().string() + "/bt_logger_test";
  std::filesystem::create_directories(test_dir);

  const std::string xml_text = R"(
      <root BTCPP_format="4">
         <BehaviorTree>
            <Sequence>
              <AlwaysSuccess name="ActionA"/>
              <AlwaysSuccess name="ActionB"/>
            </Sequence>
         </BehaviorTree>
      </root>)";
  auto tree = factory.createTreeFromText(xml_text);
  std::string filepath = test_dir + "/multi_tick.btlog";

  {
    FileLogger2 logger(tree, filepath);

    // Multiple tick cycles
    for(int i = 0; i < 3; i++)
    {
      tree.tickWhileRunning();
      tree.haltTree();
    }
    logger.flush();
  }

  std::printf("log written: %s\n", std::filesystem::exists(filepath) ? "yes" : "no");
  std::filesystem::remove_all(test_dir);
  return 0;
}
