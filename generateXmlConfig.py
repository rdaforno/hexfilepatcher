#!/usr/bin/python

######################################################################################
#
# Generates a config XML file for the Hex File Patcher from a C struct.
#
# Note that the struct needs to be defined in the following form and must be stored
# in a .h or .c file:
#   typedef struct { ... } mystruct_t;
# Supported data types: int8_t, uint8_t, char, int16_t, uint16_t, int32_t, uint32_t
#
# 2019, rdaforno
#
######################################################################################

import sys
import os
import re


outputFilename = "fwConfig.xml"


def usage():
  print("\r\nusage:  %s [struct] [address] [values] ([filename])\r\n\r\n"
        "  struct \t the name of the C struct to parse, or the full struct enclosed in quotation marks\r\n"
        "  address \t target address in the hex file\r\n"
        "  values \t a list of values to fill into the struct, enclosed in quotation marks\r\n"
        "  filename \t (optional) name of the file where the C struct is stored; if not provided, script will automatically search for the struct\r\n" % sys.argv[0])


def findStructInFile(filename):
  # or use sed: sed '/typedef struct/,/mystruct_t;/!d' [filename]
  if os.path.isfile(filename):
    with open(filename, 'r') as textfile:
      data = textfile.read()
      match = re.findall("typedef struct.*%s;" % (struct), data, re.MULTILINE | re.DOTALL)
      if match:
        print("match found in file '%s'" % (os.path.basename(filename)))
        return match[0]
  return None


def findStruct(struct, filename):
  #print("searching for struct '%s' in file '%s'" % (struct, filename))
  if os.path.isfile(filename):
    # file name is provided
    res = findStructInFile(filename)
    if res:
      return res
    else:
      print("struct not found in '%s'" % (filename))
      return None
  elif os.path.isdir(filename):
    # recursively search all files for the struct
    for root, dirs, files in os.walk(filename):
      for f in files:
        if f.endswith(".c") or f.endswith(".h"):
          res = findStructInFile(os.path.join(root, f))
          if res:
            return res
  else:
    print("invalid file '%s'" % (filename))
  return None


def parseStruct(struct):
  res = []
  bytecnt = 0
  s = struct.find("{")
  e = struct.rfind("}")
  struct = struct[s+1:e].strip()
  elements = struct.split(";")
  for elem in elements:
    if len(elem) == 0:
      continue
    parts = elem.strip().split()
    if len(parts) != 2:
      print("can't parse line '%s' (skipped)" % (elem))
      continue
    datatype = parts[0]
    variable = parts[1]
    n_bytes = 0
    if datatype == "int16_t" or datatype == "uint16_t":
      n_bytes = 2
    elif datatype == "int8_t" or datatype == "uint8_t" or datatype == "char":
      n_bytes = 1
    elif datatype == "int32_t" or datatype == "uint32_t":
      n_bytes = 4
    else:
      print("unsupported data type '%s' (skipped)" % (datatype))
      continue
    # expand if it is an array
    if "[" in variable:
      try:
        size = int(variable[variable.find("[")+1:variable.find("]")])
        variable = variable[:variable.find("[")]
        for i in xrange(size):
          res.append([ variable + str(i), n_bytes, bytecnt ])
          bytecnt = bytecnt + n_bytes
          #print("  %s (%d)\t-> %s" % (datatype, n_bytes, variable + str(i)))
      except:
        print("failed to read array index in '%s'" % (variable))
    else:
      res.append([ variable, n_bytes, bytecnt ])
      bytecnt = bytecnt + n_bytes
      #print("  %s (%d)\t-> %s" % (datatype, n_bytes, variable))
  print("struct parsed, total size is %u bytes" % (bytecnt))
  return res


def writeConfig(parsedStruct, values, addr):
  global outputFilename
  values = re.sub('[^0-9a-zA-Z]+', ' ', values).split()
  if len(parsedStruct) != len(values):
    print("not enough values provided!")
    return False
  if "0x" not in addr:
    try:
      addr = "0x%04x" % int(addr)
    except:
      print("failed to parse address, assuming offset 0")
      addr = "0"
  xmlFile = '<?xml version="1.0"?>\r\n<firmwareconfig>\r\n\t<section name="firmwareconfig" address="%s">\r\n' % (addr)
  if len(parsedStruct) == 0:
    print("parsed struct is empty")
    return False
  cnt = 0
  for elem in parsedStruct:
    #print("%s, %u" % (elem[0], elem[1]))
    xmlFile += '\t\t<int bytes="%u" offset="%u" name="%s">%s</int>\r\n' % (elem[1], elem[2], elem[0], values[cnt])
    cnt = cnt + 1
  xmlFile += '\t</section>\r\n</firmwareconfig>'
  f = open(outputFilename, "w")
  f.write(xmlFile)
  f.close()
  print("config stored in %s" % (outputFilename))
  return True


if __name__== "__main__":
  if len(sys.argv) < 4:
    usage()
    sys.exit(1)
  struct = sys.argv[1]
  addr = sys.argv[2]
  values = sys.argv[3]
  infile = ""
  if len(sys.argv) > 4:
    infile = sys.argv[4]
  else:
    infile = os.getcwd()
  res = None
  if "typedef struct" in struct:
    res = struct
  else:
    res = findStruct(struct, infile)
  if res:
    parsed = parseStruct(res)
    if not writeConfig(parsed, values, addr):
      sys.exit(1)
  else:
    sys.exit(1)
