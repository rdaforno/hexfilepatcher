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
import binascii


xmlFile = 'fwConfig.xml'    # default filename


def usage():
  print("\r\nusage:  %s [firmware] [config]\r\n\r\n"
        "  firmware \t filename of the firmware (Intel hex format)\r\n"
        "  config \t (optional) filename of the XML config; if not provided, 'fwConfig.xml' will be used\r\n" % sys.argv[0])

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
        if self.calcLineCRC(line[:-2]) != crc:
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
      fp.close()
      print("hex file saved as %s" % fileName)

  def saveAsCVariable(self, fileName):
    fp = open(fileName, "w")
    if fp:
      fp.write("const char hex_image[] = {\n  \"")
      fp.write("\"\n  \"".join(self.serializeData()))
      fp.write("\"\n};\n")
      fp.close()
      print("hex file saved as %s" % fileName)

  def calcDataCRC32(self):
    return "0x%x" % binascii.crc32(bytes.fromhex("".join(self.serializeData())))

  def serializeData(self, start_addr=0, line_width=64):
    serialized_data = []
    for line in self.lines:
      if line['addr'] > start_addr:
        # fill gap with zeros
        num_padding_bytes = (line['addr'] - start_addr)
        serialized_data.append('00'*(num_padding_bytes))
        print("added %d padding bytes at address %x" % (num_padding_bytes, line['addr']))
      serialized_data.append(line['data'])
      start_addr = line['addr'] + line['len']
    serialized_str = "".join(serialized_data)
    if line_width == 0:
      return serialized_str
    else:
      return [serialized_str[i:i+line_width] for i in range(0, len(serialized_str), line_width)]

  def addrToLineNo(self, addr):
    for i in range(len(self.lines)):
      if self.lines[i]['type'] != 0:    # only look at data records
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
        self.updateLineCRC(i+1)
      else:
        self.lines[i]['data'] = self.insertData(self.lines[i]['data'], (addr - self.lines[i]['addr']), size, data)
      self.updateLineCRC(i)
      return 1
    else:
      return 0

  def insertData(self, line, ofs, size, data):  # inserts 'data' of length 'size' into 'line' at offset 'ofs'
    if size == 1:
      return line[:ofs*2] + ("%02X" % (data % 256)) + line[(ofs+size)*2:]
    elif size == 2:
      return line[:ofs*2] + ("%02X%02X" % (data % 256, (data >> 8) % 256)) + line[(ofs+size)*2:]             # little endian!
    elif size == 4:
      return line[:ofs*2] + ("%02X%02X%02X%02X" % (data % 256, (data >> 8) % 256, (data >> 16) % 256, (data >> 24) % 256)) + line[(ofs+size)*2:]    # little endian!

  def updateLineCRC(self, idx):
    if idx < len(self.lines):
      self.lines[idx]['crc'] = self.calcLineCRC("%02X%04X%02X%s" % (self.lines[idx]['len'], self.lines[idx]['addr'], self.lines[idx]['type'], self.lines[idx]['data']))

  def calcLineCRC(self, line):
    crc = 0
    l = 0
    while l < len(line) - 1:
      crc = crc + int(line[l:l+2], 16)
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
          if "0x" in var.text:
            val = int(var.text, 16)
          else:
            val = int(var.text)
          if hexFile.replaceData(ofs, size, val):
            print("%u bytes at address 0x%04X overwritten with value %d" % (size, ofs, val))
          else:
            print("failed to write to address 0x%04X" % (ofs))
        except:
          print("invalid int value %s" % var.text)


if __name__== "__main__":
  if len(sys.argv) < 2:
    usage()
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

