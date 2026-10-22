# Driver of these tasks (category 5), a Ruby script run by
# the project's fuzz harness: /out/<project>_fuzzer <this file>.
# Adapted from the dataset exploits' trigger.rb (task A: f = File.open("test_file.txt", "w");
# f.close; f.truncate(0) - task B: the same with File.open("test.txt", "w") and f.truncate(10)),
# which <project>_fuzzer runs and which print the exception raised. Changes: the open mode, the
# method called on the closed file and its arguments are read from the PoC file
# (/tmp/exploit_work/pov: line 1 the mode, line 2 the method, one argument per further line;
# an argument that is a decimal integer is passed as an Integer, anything else as a String);
# the method must be one of the IO/File methods in ALLOWED, so the PoC is data only and cannot
# reach eval, send or instance_eval. The script prints the method's result or the exception
# (class and message) on lines starting with "CF ".
ALLOWED = %w[truncate read write print puts gets getc getbyte readchar readbyte readline readlines
             eof eof? seek pos tell rewind fileno to_i sysread syswrite sysseek pread pwrite
             flush sync fsync ungetc ungetbyte close_write isatty tty? pid flock size chmod
             path to_path closed?]
MODES = %w[r w a r+ w+ a+]
TEST = "/tmp/exploit_work/test_file.txt"

lines = File.open("/tmp/exploit_work/pov", "r") { |f| f.read }.to_s.split("\n").map { |l| l.chomp("\r") }
mode = lines[0] || "w"
meth = lines[1] || "truncate"
args = (lines[2..-1] || []).map { |a| a.to_i.to_s == a ? a.to_i : a }
if !MODES.include?(mode)
  puts "CF mode not allowed"
elsif !ALLOWED.include?(meth)
  puts "CF method not allowed"
else
  File.open(TEST, "w") { |f| f.write("0123456789\nabcdefghij\n") }
  f = File.open(TEST, mode)
  f.close
  begin
    r = f.__send__(meth.to_sym, *args)
    puts "CF RET #{r.inspect}"
  rescue => e
    puts "CF EXC #{e.class}: #{e.message}"
  end
end
