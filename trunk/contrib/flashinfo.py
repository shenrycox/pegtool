#!/usr/bin/env python
# 
# Copyright 2009 Tim Dedischew, released under the GPL v2
#
"""Pegasus Digital Pen flash info tool"""

VERSION = "0.00"

import sys

# allow this to be run right out of the svn dir:
import os,sys
libsdir = os.path.realpath(os.getcwd() + '/../src')
if os.path.isdir(libsdir) and os.path.isfile(libsdir + '/pegasus.py'):
	sys.path.insert(0, libsdir)
else:
	libsdir = os.path.realpath(os.getcwd() + '/src')
	if os.path.isdir(libsdir) and os.path.isfile(libsdir + '/pegasus.py'):
		sys.path.insert(0, libsdir)

from pegasus import depackable
if (sys.argv[1] == '-'):
	mem = sys.stdin
else:
	mem = file(sys.argv[1], "rb")
bin = mem.read()
assert not mem.read()
_NOTEHEADER = depackable('NOTEHEADER', 'a b c flags notenum total d e f g h i j addr', "<cccccccccccccc")
DATAXY = depackable('DATAXY', 'x y', "<hh")

def dump_bytes(bytes):
	return " ".join(hex(ord(b)) for b in bytes) + " "

def NOTEHEADER(bytes):
	tmp = _NOTEHEADER(bytes[:14])
	tmp = tmp._tmp._replace(tmp, addr=(ord(tmp.c)<<16) + (ord(tmp.b) <<8) + ord(tmp.a))
	return tmp

i = 0
while (i < (len(bin)) and bin[i:3] != '\x00\x00\x00'):
	assert (len(bin)-i) >= 14
	tmp = NOTEHEADER(bin[i:])
	nn = str(ord(tmp.notenum) - 1)
 	i += 14
	data = bin[i:tmp.addr]
	i = tmp.addr
	ndata = len(data)
	if (not data):
		break

	minx = miny = sys.maxint
	maxx = maxy = -sys.maxint
	npoints = 0
	nstrokes = 0
	while data:
		xy = DATAXY(data[:4])
		npoints += 1
		data = data[4:]
		if (xy.y == -32768):
			nstrokes += 1
			# EOSTROKE handling
		else:
			if (xy.x < minx):
				minx = xy.x
			if (xy.y < miny):
				miny = xy.y
			if (xy.x > maxx):
				maxx = xy.x
			if (xy.y > maxy):
				maxy = xy.y

	sys.stderr.write("note #%s\n\tbytes: %d\t\n\tstrokes: %d\n\tpoints: %d\n"%(nn, ndata, nstrokes, npoints))
