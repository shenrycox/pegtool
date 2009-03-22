#!/usr/bin/env python
# 
# Copyright 2009 Tim Dedischew, released under the GPL v2
#
"""Pegasus Digital Pen USB command-line tool"""

VERSION = "0.01"

# allow this to be run right out of the svn dir:
import os,sys
libsdir = os.getcwd() + '/src'
if os.path.isdir(libsdir) and os.path.isfile(libsdir + '/pegasus.py'):
	sys.path.insert(0, libsdir)

import getopt
import pegasus as pegusb
import logging
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter(fmt='[%(levelname)+7s] %(message)s'))
dbg = logging.getLogger('pegtool.pegasus')
dbg.addHandler(ch)

def usage(full=False):
	help="Usage: %s [-dhvVy] <operation>\n" % sys.argv[0]
	if (full):
		help += """  options:
    -h\tdisplay help (this output)
    -v\tincrease verbosity
    -d\tincrease debugging output
    -y\tyes mode -- force the desired operation, even if dangerous
    -V\tdisplay pegtool version and exit
"""
	help += """  operations:
    test\t\ttest connectivity (connect, disconnect, exit)
    info\t\t(*) display results of device version request
    poll <XY|TAB>\t(*) configure for and poll XY or TABlet mode data
    status\t\t(*) display status, including available data size
    fetch <file.bin|->\t(*) fetch raw device data as save to file.bin
        \t	   (aka: 'upload request')
    erase\t\t(*) clear ALL device data.
(*) == experimental!	
""" 
	if (not full):
		help = "\n".join([x.split('\t')[0].rstrip() for x in help.split("\n")])
		help = help.replace("\n\n","\n")
		help += " (specify -h for full help text)\n"
	sys.stdout.write(help)
	
def main():
	try:
		opts, args = getopt.gnu_getopt(sys.argv[1:], "dhvVy", ["version"])
	except getopt.GetoptError, err:
		# print help information and exit:
		print str(err) # will print something like "option -a not recognized"
		usage()
		sys.exit(2)
	#dbg.debug(opts)
	verbose = False
	op = False
	yes = False
	dbg.setLevel(logging.WARN)
	for o, a in opts:
		if o == "-v":
			verbose = True
		elif o in ("-V", "--version"):
			print "pegtool, version",VERSION,"(TODO:insert SVN rev here)"
			print ""
			print "Copyright (c) 2009 Tim Dedischew"
			print "'pegtool' is open source software, see http://code.google.com/p/pegtool"
			print ""
			sys.exit()
		elif o == "-y":
			yes = True
		elif o in ("-h", "--help"):
			usage(full=True)
			sys.exit()
		elif o in ("-d","--debug",):
			if (dbg.level > 10):
				dbg.level -= 10
			sys.stderr.write("-d: enabled more debug output: %d\n" % dbg.level)
		else:
			assert False, "unhandled option %s"%o
	# ...

	##TODO: FIXME: originally used long options instead of command names, if permanent redo this part...
	o, a = "", ""
	if (args):
		o = "--" + args[0]
		if (len(args) > 1):
			a = args[1]
		
	if o in ("--test",):
		try:
			print "CONNECT:\t",
			pegusb.connect()
			print "OK"
			if (verbose):
				print "    (control): ",pegusb.control
				print "    (digitizer): ", pegusb.digitizer
			print "DISCONNECT:\t",
			pegusb.disconnect()
			print "OK"
			sys.exit()
		except pegusb.hidwrap.HIDError, e:
			print "FAILED"
			if (e.code == 7):
				sys.stderr.write("could not connect to Pegasus USB Device, exiting\n")
			sys.exit(e.code)
		except Exception, e:
			pegusb.disconnect()
			print "UNHANDLED EXCEPTION!!", e
			raise
	elif o in ("--poll",):
		if (a.startswith("XY")):
			op = lambda: pegusb.pollXY(lambda x: sys.stdout.write(str(x)+"\n") or True)
		elif (a.startswith("TAB")):
			op = lambda: pegusb.pollTAB(lambda x: sys.stdout.write(str(x)+"\n") or True)
		else:
			assert False, "Invalid --poll mode: %s" % a
	elif o in ("--status",):
		def dostatus(a=a):
			if (True or verbose):
				vinfo = pegusb.getDeviceVersion()
				sys.stderr.write(str(vinfo) + "\n")
			sz = pegusb.downloadDeviceData("/dev/null", verbose=verbose, dryrun=True)
			sys.stdout.write("Data Packets Available: %d (~%d bytes)\n" % (sz, sz*62 ))
		op = dostatus
	elif o in ("--erase",):
		def doerase(a=a):
			if (not yes):
				sys.stderr.write("erase: sheepishly aborting -- specify -y to force\n")
				sys.exit(3)
			pegusb.downloadDeviceData("erased.bak", verbose=verbose, erase=True)
			sys.stdout.write("... (data saved to erased.bak and device cleared)\n")
		op = doerase
	elif o in ("-f", "--fetch",):
		#TODO: refactor 
		def dofetch(a=a):
			a = a.strip()
			if (not a and len(sys.argv) == 3 and sys.argv[2] == '-'):
				a = "-"
			if (not a):
				print "fetch: must specify filename (or - for STDOUT)!",sys.argv
				sys.exit(2)
			if (not a == "-" and os.path.isfile(a)):
				if (not yes):
					print a, "exists -- not overwriting (specify -y to force)"
					sys.exit(3)
				else:
					dbg.warn("'%s' exists, overwriting since -y specified....", a)
			dbg.info("Fetching FLASH to %s", a)
			pegusb.downloadDeviceData(a, verbose=verbose)
		op = dofetch
	elif o in ("-i","--info", "--version"):
		#TODO: refactor
		def doinfo(a=a):
			if (verbose):
				pegusb.dbgIdentification(sys.stderr.write)
			vinfo = pegusb.getDeviceVersion()
			sys.stdout.write(str(vinfo) + "\n")
		op = doinfo

	else:
		sys.stderr.write("invalid operation: %s\n" % o)
		usage()
		sys.exit()

	try:
		pegusb.connect()
		op()
	except KeyboardInterrupt, e:
		sys.stderr.write("KeyboardInterrupt!\n")
	except pegusb.hidwrap.HIDError, e:
		if (e.code == 7):
			sys.stderr.write("could not connect to Pegasus USB Device, exiting\n")
			sys.exit(e.code)
		raise
	finally:
		pegusb.disconnect()
	#EOmain
if __name__ == "__main__":
	main()

