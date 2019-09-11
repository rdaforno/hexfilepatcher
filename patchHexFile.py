#!/usr/bin/python

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

xmlFile = 'fwConfig.xml'    # default filename


# Intel HEX file parser
class hexFileParser:
  lines = []

  def __init__(self, fileName):
    self.loadFromFile(fileName)

  def loadFromFile(self, fileName):
    with open(fileName) as fp:
      for line in fp:
        if line[0] != ':':
          print("line '%s' skipped.." % line)
          continue
        line = line[1:].strip()
        l = int(line[0:2], 16)
        addr = int(line[2:6], 16)
        t = int(line[6:8], 16)
        data = line[8:-2]
        if len(data) != (l * 2):
          print("invalid data length! line '%s' skipped.." % line)
          continue
        crc = int(line[-2:], 16)
        if self.calcCRC(line[:-2]) != crc:
          print("invalid hex file, CRC doesn't match!")
          break
        self.lines.append({ 'len':l, 'addr':addr, 'type':t, 'data':data, 'crc':crc })
    print("%u lines loaded from %s" % (len(self.lines), fileName))

  def printLines(self):
    for line in self.lines:
      print("length: %u, address: 0x%02x, type: %u, data: %s, crc: %02x" % (line['len'], line['addr'], line['type'], line['data'], line['crc']))

  def saveAsFile(self, fileName):
    fp = open(fileName, "w")
    if fp:
      for line in self.lines:
        fp.write(":%02X%04X%02X%s%02X\n" % (line['len'], line['addr'], line['type'], line['data'], line['crc']))
      print("hex file saved as %s" % fileName)

  def addrToLineNo(self, addr):
    for i in range(len(self.lines)):
      if self.lines[i]['type'] is not 0:    # only look at data records
        continue
      if self.lines[i]['addr'] <= addr and (self.lines[i]['addr'] + self.lines[i]['len']) > addr:
        return i
    return -1

  def replaceData(self, addr, size, data):
    if size != 1 and size != 2 and size != 4:
      print("size %d is not supported" % size)
      return 0
    i = self.addrToLineNo(addr)
    if i >= 0:
      ofs = (addr - self.lines[i]['addr'])
      if (addr + size) > (self.lines[i]['addr'] + self.lines[i]['len']):   # data stretches over 2 lines
        # make sure there is no jump in address to the next line
        if (i+1) == len(self.lines) or ((self.lines[i+1]['addr'] - self.lines[i]['addr']) > self.lines[i]['len']):
          print("out of bound error")
          return 0
        self.lines[i]['data'] = self.insertData(self.lines[i]['data'], ofs, self.lines[i]['len'] - ofs, data)
        self.lines[i+1]['data'] = self.insertData(self.lines[i+1]['data'], 0, size - (self.lines[i]['len'] - ofs), data)
        self.updateCRC(i+1)
      else:
        self.lines[i]['data'] = self.insertData(self.lines[i]['data'], (addr - self.lines[i]['addr']), size, data)
      self.updateCRC(i)
      return 1

  def insertData(self, line, ofs, size, data):  # inserts 'data' of length 'size' into 'line' at offset 'ofs'
    if size == 1:
      return line[:ofs*2] + ("%02X" % (data % 256)) + line[(ofs+size)*2:]
    elif size == 2:
      return line[:ofs*2] + ("%04X" % (data % 65536)) + line[(ofs+size)*2:]
    elif size == 4:
      return line[:ofs*2] + ("%08X" % (data % (2^32))) + line[(ofs+size)*2:]
    return line

  def updateCRC(self, idx):
    if idx < len(self.lines):
      self.lines[idx]['crc'] = self.calcCRC("%02X%04X%02X%s" % (self.lines[idx]['len'], self.lines[idx]['addr'], self.lines[idx]['type'], self.lines[idx]['data']))

  def calcCRC(self, data):
    crc = 0
    l = 0
    while l < len(data) - 1:
      crc = crc + int(data[l:l+2], 16)
      l = l + 2
    crc = (~crc + 1) % 256
    return crc


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
        try:
          val = int(var.text)
          print("replacing %u bytes at address 0x%04X with value %d" % (size, ofs, val))
          hexFile.replaceData(ofs, size, val)
        except:
          print("invalid int value %s" % var.text)


if __name__== "__main__":
  if len(sys.argv) < 2:
    print("usage:  %s [firmware.hex] [config.xml]" % sys.argv[0])
    sys.exit(1)
  hexFileName = sys.argv[1]      # first argument is the hex filename
  if not os.path.isfile(hexFileName) or not hexFileName.lower().endswith('hex'):
    print("invalid file '%s'" % hexFileName)
    sys.exit(1)
  if len(sys.argv) > 2:
    xmlFile = sys.argv[2]   # second argument is the config filename
  if not os.path.isfile(xmlFile) or not xmlFile.lower().endswith('xml'):
    print("invalid file '%s'" % xmlFile)
    sys.exit(1)
  # load the hex file
  hexFile = hexFileParser(hexFileName)
  # parse and apply the XML config
  parseXML(xmlFile, hexFile)
  hexFile.saveAsFile("parsed_" + hexFileName)

