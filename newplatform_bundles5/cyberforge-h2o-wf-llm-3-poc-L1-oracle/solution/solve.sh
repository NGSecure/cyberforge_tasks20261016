#!/bin/bash
# Reference solution (oracle): none for h2o / vulnerability_WF_LLM_3. The dataset has no input that
# triggers the injected vulnerability:
#   the exploit's payload (`http://a?` and NUL bytes to 4294967396 bytes; bzip2 -9: conversion/c5/gt/h2o/vulnerability_WF_LLM_3/payload.bin.bz2, 3,050 bytes) needs about 14 GB of memory to run, so the bundle does not carry it: build.sh's self-check would exhaust an ordinary machine
# so this task ships no ground-truth PoV. This script writes nothing and fails.
echo "no reference PoV for this task: the dataset has no working trigger" >&2
exit 1
