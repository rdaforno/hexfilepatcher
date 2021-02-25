#!/usr/bin/python3

######################################################################################
#
# Patch an Intel HEX file, i.e. overwrite variable contents in the compiled firmware.
#
# Note:
# To place a variable/struct at a certain memory location with gcc, use:
#   volatile mystruct_t  __attribute((section (".fwConfigSection"))) mystruct = { 0 };
# and register the section with the linker:
#   LDFLAGS += -Wl,--section-start -Wl,.fwConfigSection=[address]
#
#
# 2019, rdaforno
#
######################################################################################

import sys
import os.path
import xml.etree.ElementTree as ET
import binascii
import hexFileParser


xmlFile = 'fwConfig.xml'    # default filename


def usage():
  print("\r\nusage:  %s [filename] [config]\r\n\r\n"
        "  filename \t path to an Intel hex file\r\n"
        "  config \t (optional) filename of the XML config; if not provided, 'fwConfig.xml' will be used\r\n" % sys.argv[0])


def parseXML(xmlFile, hexFile):
  tree = ET.parse(xmlFile)
  root = tree.getroot()
  for section in root.iter('section'):
    address = int(section.get("address"), 0)
    print("overwriting config section at address 0x%04X.." % address)
    for var in section:
      if var.tag == "int":
        size = int(var.get("bytes"))
        ofs = address + int(var.get("offset", 0), 0)
        #try:
        if "0x" in var.text:
          val = int(var.text, 16)
        else:
          val = int(var.text)
        if hexFile.replace_data(ofs, size, val):
          print("%u bytes at address 0x%04X overwritten with value %d" % (size, ofs, val))
        else:
          print("failed to write to address 0x%04X" % (ofs))
        #except:
        #  print("invalid int value %s" % var.text)


if __name__== "__main__":
  if len(sys.argv) < 2:
    usage()
    sys.exit(1)
  hex_filename = sys.argv[1]      # first argument is the hex filename
  if not os.path.isfile(hex_filename) or not hex_filename.lower().endswith('hex'):
    print("invalid file '%s'" % hex_filename)
    sys.exit(1)
  if len(sys.argv) > 2:
    xmlFile = sys.argv[2]   # second argument is the config filename
  if not os.path.isfile(xmlFile) or not xmlFile.lower().endswith('xml'):
    print("invalid file '%s'" % xmlFile)
    sys.exit(1)
  # load the hex file
  hf = hexFileParser.HexFileParser(hex_filename)
  hf.serialize_data()
  # parse and apply the XML config
  parseXML(xmlFile, hf)
  hf.save("parsed_" + hex_filename)
