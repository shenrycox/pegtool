#!/usr/bin/env python
# 
# Copyright 2009 Tim Dedischew, released under the GPL v2
#
"""Python wrapper for interfacing with Pegasus Digital Pen over USB"""

VERSION = "0.02"
import pegtool_hidwrap as hidwrap # use tweaked local hidwrap, may be replaced in future with official python-hid hidwrap.py?
import sys
import time

import logging
dbg = logging.getLogger('pegtool.pegasus')

from struct import pack, unpack
from pegtool_namedtuple import namedtuple

### TODO: put ths in a utility module?  flash2svg references
def depackable(typename, field_names, _unpack):
	"""a small utility function to make byte twiddling a bit easier
	typename: human-friendly typename
	field_names: space separated (to be mapped) field names
	_unpack: string directly fed to unpack() function

	returned class can be used to simultaneously instantiate and parse a byte array
	example:
	>>> PENDATAXY = depackable('PENDATAXY', 'status color x y', '>ccHH')
	>>> pdxy = PENDATAXY('\x01\x01\x12\x34\x56\x78')
	>>> pdxy.x
	4660
	>>> print pdxy
	PENDATAXY(status='\\x01', color='\\x01', x=4660, y=22136)
	"""
	tmp = namedtuple(typename, field_names)
	class _depackable(tmp):
		_bytes = None
		_tmp = tmp
		def __new__(cls, bytes):
			ret = tmp.__new__(cls, *unpack(_unpack, bytes))
			ret._bytes = bytes
			return ret		
	return _depackable

def dump_bytes(bytes):
	return " ".join(hex(ord(b)) for b in bytes) + " "

control = 0
digitizer = 0
def init():
	global control, digitizer
	try: ###FIXME: init() can be called multiple times, not sure of side effects
		if (control):
			clearEP(False)
		hidwrap.cleanup()
	except:
		pass
	hidwrap.init()
	control = hidwrap.Interface(vendor_id=0x0e20, product_id=0x0101,interface_number=0)
	digitizer = hidwrap.Interface(vendor_id=0x0e20, product_id=0x0101,interface_number=1)

def connect():
	dbg.debug("pegasus.connect")
	try:
		init()
		control.set_output_report(VPATH, VINFOCOMMAND) ##FIXME: needed? resetting via version request seems to make more reliable
		clearEP()
	except hidwrap.HIDError, e:
		dbg.critical('hidwrap.init() error: %s', e)
		raise

def disconnect():
	global control, digitizer
	dbg.debug("pegasus.disconnect (control=%s,digitizer=%s)", control, digitizer)
	try:
		if (control):
			control = 0
			digitizer = 0
		hidwrap.cleanup()
		#hidwrap.init()
	except Exception, e:
		dbg.warn("disconnect: %s", e)
		pass


def pack_path(longs):
	tmp = longs + []
	tmp.reverse()
	#FIXME: what's the right way to encode as int array in python??
	return [ord(i) for i in pack(">%dI" % len(tmp), *tmp)] 

VPATH = pack_path([0xffa00001, 0xffa00002])
VINFOCOMMAND = "\x02\x01\x95"
ULERASE = "\x02\x01\xB0"
ULSTART = "\x02\x01\xB5"
ULRESP = depackable('ULSTART', 'a b c d e packets f g', ">cccccHcc")
ULACK = "\x02\x01\xB6"
ULNACK = "\x02\x01\xB7"
ULPACKNUM = depackable('ULPACKNUM', 'n', ">H")

def VINFO(bytes):
	"""pseudo-class to calculate a better representation of the firmware/analog version data (guessed -- not in specs)"""
	_VINFO = depackable('VINFO', 'firmware analog pad mode', ">xxxHHHxc")
	tmp = _VINFO(bytes)
	tmp = tmp._tmp._replace(tmp,
							firmware="%d.%d"%((tmp.firmware & 0xff00)>>8,(tmp.firmware & 0x00ff)),
							analog="%d.%d"%((tmp.analog & 0xff00)>>8,(tmp.analog & 0x00ff))
							)
	return tmp

def SOCOMMAND(scale=0, orient=0x00): # ['Top','Left','Right']
	"""Scale &Orientation command
	-- From M210 protocol doc-- 
	Scale (active area size):
	0 (largest) - 9 (smallest)

	Orientation:
	0x00 Top
	0x01 Left
	0x02 Right
	"""
	return "\x02\x04\x80\xb6"+chr(scale)+chr(orient)

SOCOMMAND.scaleLARGEST = 0
SOCOMMAND.scaleSMALLEST = 9
SOCOMMAND.orientTOP = 0x00
SOCOMMAND.orientLEFT = 0x01
SOCOMMAND.orientRIGHT = 0x02

def OMCOMMAND(led=0, mode=0):
	"""Operation mode command
	-- From M210 protocol doc --
	P/M LED:
	0x00 N.C.
	0x01 Pen LED
	0x02 Mouse LED
	
	Mode :
	0x00 N.C.
	0x01 XY
	0x02 Tablet
"""
	lc = [0x02,0x04,0x80,0xB5,
		  led, #LED: 0 NC, 1 PEN, 2 MOUSE
		  mode] #MODE: 0 NC, 1 XY, 2 TAB
	return "".join([chr(x) for x in lc])

OMCOMMAND.ledPEN = 0x01
OMCOMMAND.ledMOUSE = 0x02
OMCOMMAND.modeXY = 0x01
OMCOMMAND.modeTAB = 0x02

PENDATAXY = depackable('PENDATAXY', 'status color x y', ">ccHH")
PENDATATAB = depackable('PENDATATAB', 'x y state pressure', "<xHHcH")

def dbgIdentification(writefunc):
	"""send libhid's write_identification() output to writefunc(each line passed in order)"""
	import tempfile
	t = tempfile.TemporaryFile()
	control.write_identification(t)
	t.seek(0)
	for l in t:
		writefunc(l)
	t.close()
	
def clearEP(bAll=True):
	"""clear endpoint buffers (or try to anyway).  seems to make subsequent operations more consistent"""
	rpt = 0
	try:
		dbg.debug("Clearing EP 2 digitizer buffer...")
		while(True):
			rpt = digitizer.interrupt_read(0x82, 6, 100)
			dbg.debug("(digitizer discardind %d bytes)"%len(rpt))#+dump_bytes(rpt) + "\n")
			#if (not bAll):
				#break
	except:
		dbg.debug("buffer looks empty")

	try:
		dbg.debug("Clearing EP 1 buffer...")
		while(True):
			rpt = control.interrupt_read(0x81, 64, 100)
			dbg.debug("(discardind %d bytes)"%len(rpt))
			if (not bAll):
				break
	except:
		dbg.debug("buffer looks empty")

def watchXY(cb):
	dbg.info("watchXY started for cb: %s",cb)
	while(True):
		try:
			rpt = control.interrupt_read(0x81, 64, 1000)
			rpt = rpt[:6]
			if not cb(PENDATAXY(rpt)):
				return
		except hidwrap.HIDError, err:
			if err.code != 21:
				raise


def pollXY(cb):
	#TODO: fetch current mode, restore afterwards??
	control.set_output_report(VPATH, OMCOMMAND(led=OMCOMMAND.ledMOUSE,mode=OMCOMMAND.modeXY))
	control.set_output_report(VPATH, SOCOMMAND(orient=SOCOMMAND.orientTOP))
	watchXY(cb)

def watchTAB(cb):
	dbg.info("watchTAB started for cb: %s",cb)
	while(True):
		try:
			rpt = digitizer.interrupt_read(0x82, 6, 1000)
			rpt += digitizer.interrupt_read(0x82, 2, 1000)
			if (not cb(PENDATATAB(rpt[:8]))):
				return False
		except hidwrap.HIDError, err:
			if err.code != 21:
				raise

def pollTAB(cb):
	#TODO: fetch current mode, restore afterwards??
	control.set_output_report(VPATH, OMCOMMAND(led=OMCOMMAND.ledPEN,mode=OMCOMMAND.modeTAB))
	control.set_output_report(VPATH, SOCOMMAND(scale=SOCOMMAND.scaleLARGEST, orient=SOCOMMAND.orientTOP))
	watchTAB(cb)
	
def echo(x):
	print x
	return True

def watchINFO(cb):
	while (True):
		try:
			rpt = control.interrupt_read(0x81, 64, 1000)
			return cb(VINFO(rpt[:11]))
			break
		except hidwrap.HIDError, err:
			print "watchINFO", err
			if err.code != 21:#hidwrap.HID_RET_TIMEOUT:
				raise
		#init()
		time.sleep(.5);

def getDeviceVersion(retry=1):
	control.set_output_report(VPATH, VINFOCOMMAND)
	while (retry > 0):
		try:
			rpt = control.interrupt_read(0x81, 64, 1000)
			return VINFO(rpt[:11])
		except hidwrap.HIDError, err:
			dbg.warn("getDeviceVersion: %s", err)
			if err.code != 21:#hidwrap.HID_RET_TIMEOUT:
				raise
		retry -= 1
	return False

def downloadDeviceData(output="flash.bin", dryrun=False, erase=False, verbose=False):
	control.set_output_report(VPATH, ULSTART)
	try:
		### FIXME: this seems to timeout if no pages available -- better way to detect
		rpt = control.interrupt_read(0x81, 64, 1000)
	except hidwrap.HIDError, err:
		dbg.warn("downloadDeviceData: %s", err)
		if err.code != 21:#hidwrap.HID_RET_TIMEOUT:
			raise
		if (getDeviceVersion()): # if version comes back, assume just no data available
			return 0
	rpt = rpt[:9]
	dbg.info("header: %s",dump_bytes(rpt))
	assert rpt[-2:] == '\x55\x55' and rpt[0:5] == "\xAA\xAA\xAA\xAA\xAA", "bad signature 0x%x 0x%x" % (ord(rpt[0]),ord(rpt[-1]))
	np = sz = ULRESP(rpt).packets
	dbg.info("there are %d packets", sz)
	if (dryrun or sz <= 0):
		dbg.info("NACKing to cancel download (dryrun requested).")
		control.set_output_report(VPATH, ULNACK)
		return sz
	try:
		dbg.info("dumping device data to %s", output)
		if (output == "-"):
			mem = sys.stdout
		else:
			mem = file(output, "wb")
		control.set_output_report(VPATH, ULACK)
		ss = ""
		while (sz > 0):
			rpt = control.interrupt_read(0x81, 64, 1000)
			n = ULPACKNUM(rpt[:2]).n
			if (verbose):
				print "\b"*(len(ss)+2),
			ss = "%d/%d [%3d]%%" % (n,np,100.0*n/np)
			if (verbose):
				print ss,
			sz -= 1
			mem.write(rpt[2:])
		else:
			if (verbose):
				print ""
				print "saved to",mem.name
			dbg.info("done.")
			control.set_output_report(VPATH, ULACK)
			if (erase):
				dbg.warn("ULERASE!!!!")
				control.set_output_report(VPATH, ULERASE)
	except Exception, e:
		if (verbose):
			print ""
		raise
	finally:
		if (mem is not sys.stdout):
			mem.close()
	return True

__all__ = ["connect","disconnect","getDeviceVersion","downloadDeviceData","pollTAB","pollXY"]

if __name__ == "__main__":
    import doctest
    doctest.testmod()
