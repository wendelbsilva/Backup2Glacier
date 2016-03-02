#!/usr/bin/env python

import os
import tarfile

def __compressDir(path, handler):
    for root, dirs, files in os.walk(path):
        for f in files:
            full = os.path.join(root, f)
            handler.add(full, os.path.relpath(full,path))

from subprocess import call

def compressDir(filename, path):
    pigz = False
    lzop = False
    try:
        call(["pigz","-V"])
        pigz = True
    except:
        print("pigz not found")

    # Tested with 38GB Folder
    # Time: 34min 27.9sec    Size: 38559570230   (35.9GB)
    #h = tarfile.open(filename, 'w:gz', compresslevel=1)
    #__compressDir(path, h)
    #h.close()
    
    if pigz:
        # Time: 15min 16.7sec    Size: 38506490455
        print("PIGZ")
        call(["tar", "-c", "--use-compress-program=pigz", "-f", filename,path]) #.tar.gz
    elif lzop:
        # Time: 15min 29.0sec    Size: 39028477653
        print("LZOP")
        call(["tar", "-c", "--use-compress-program=lzop", "-f", filename,path]) #.lzo
    else:
        # Time: 15min 40.7sec    Size: 40321239040
        print("GZIP")
        call(["tar", "-c", "-f", filename,path]) # default: gzip

