#!/usr/bin/env python

import os
import tarfile

def __compressDir(path, handler):
    for root, dirs, files in os.walk(path):
        for f in files:
            full = os.path.join(root, f)
            handler.add(full, os.path.relpath(full,path))

def compressDir(filename, path):
    h = tarfile.open(filename, 'w:gz')
    __compressDir(path, h)
    h.close()

