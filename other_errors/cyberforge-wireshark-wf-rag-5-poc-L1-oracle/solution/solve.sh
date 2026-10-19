#!/bin/bash
# Reference solution (oracle): none for wireshark / vulnerability_WF_RAG_5. The dataset has no input that
# triggers the injected vulnerability:
#   the exploit runs a copy of getnum cut out of wslua_struct.c with a stub lua_State; its format string is no input for any built program, and no built program contains wslua.
# so this task ships no ground-truth PoV. This script writes nothing and fails.
echo "no reference PoV for this task: the dataset has no working trigger" >&2
exit 1
