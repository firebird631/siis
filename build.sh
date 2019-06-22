#!/bin/bash
cython siis.py --embed
gcc -O3 -fPIC siis.c -I /usr/include/python3.7/ -o siis $(python3.7-config --ldflags) $(python3.7-config --cflags)
