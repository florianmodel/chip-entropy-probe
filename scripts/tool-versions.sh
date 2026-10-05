#!/usr/bin/env bash
set -euo pipefail
mkdir -p build
{
    python3 -m librelane --version
    yosys -V
    openroad -version
    klayout -v
    magic --version
    netgen -batch quit
    verilator --version
    python3 -c 'import subprocess; print(subprocess.check_output(["iverilog", "-V"], stderr=subprocess.STDOUT).decode().splitlines()[0])'
    sby --version
} 2>&1 | tee build/tool-versions.txt
