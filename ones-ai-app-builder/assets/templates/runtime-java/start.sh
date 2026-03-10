#!/bin/sh
set -eu
cd /workspace
javac Main.java
exec java Main
