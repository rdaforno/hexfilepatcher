#!/usr/bin/python3

######################################################################################
#
# Intel HEX file parser
#
# 2020, rdaforno
#
######################################################################################


import binascii


# Intel HEX file parser
class HexFileParser:
  lines = []

  def __init__(self, filename):
    self.lines.clear()
    self.load(filename)

  def load(self, filename):
    self.lines.clear()
    with open(filename) as fp:
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
        if self.calc_line_crc(line[:-2]) != crc:
          print("invalid hex file, CRC doesn't match!")
          break
        self.lines.append({ 'len':l, 'addr':addr, 'type':t, 'data':data, 'crc':crc })
    print("%u lines loaded from %s" % (len(self.lines), filename))

  def print_lines(self):
    for line in self.lines:
      print("length: %u, address: 0x%02x, type: %u, data: %s, crc: %02x" % (line['len'], line['addr'], line['type'], line['data'], line['crc']))

  def save(self, filename):
    fp = open(filename, "w")
    if fp:
      for line in self.lines:
        fp.write(":%02X%04X%02X%s%02X\n" % (line['len'], line['addr'], line['type'], line['data'], line['crc']))
      fp.close()
      print("hex file saved as %s" % filename)

  def save_as_c_var(self, filename):
    fp = open(filename, "w")
    if fp:
      fp.write("const char hex_image[] = {\n  \"")
      fp.write("\"\n  \"".join(self.serialize_data()))
      fp.write("\"\n};\n")
      fp.close()
      print("hex file saved as %s" % filename)

  def save_as_binary(self, filename):
    fp = open(filename, "wb")
    if fp:
      fp.write(bytes.fromhex("".join(self.serialize_data())))
      fp.close()
      print("binary file saved as %s" % filename)

  def calc_crc32(self):
    return "0x%x" % binascii.crc32(bytes.fromhex("".join(self.serialize_data())))

  def serialize_data(self, start_addr=0, line_width=64):
    serialized_data = []
    curr_ofs = 0
    for line in self.lines:
      if line['type'] == 0:
        curr_addr = curr_ofs + line['addr']
        if curr_addr > start_addr:
          serialized_data.append('00'*(curr_addr - start_addr))  # fill gap with zeros
          print("added %d padding bytes at address 0x%x" % (curr_addr - start_addr, curr_addr))
        serialized_data.append(line['data'])
        start_addr = curr_addr + line['len']
      elif line['type'] == 4 or line['type'] == 2:
        if line['type'] == 4:
          curr_ofs = int(line['data'][0:4], 16) * 65536
        else:
          curr_ofs = int(line['data'][0:4], 16) << 4
        if start_addr == 0:
          # if this is the first line and start_addr is not given, then use this offset as the start address
          start_addr = curr_ofs
          print("start address set to 0x%x" % start_addr)
        else:
          print("address offset found: 0x%x" % curr_ofs)
        if curr_ofs < start_addr:
          print("invalid address offset")
          return None
      elif line['type'] == 1:
        pass  # marks the EOF
      elif line['type'] == 3:
        # defines the start address
        pass
      else:
        print("skipping line of type %u" % line['type'])
    serialized_str = "".join(serialized_data)
    print("binary size is %u bytes" % (len(serialized_str) / 2))
    if line_width == 0:
      return serialized_str
    else:
      return [serialized_str[i:i+line_width] for i in range(0, len(serialized_str), line_width)]

  # returns a tuple of line index and line address
  def addr_to_lineno(self, addr):
    addr_ofs = 0
    for i in range(len(self.lines)):
      if self.lines[i]['type'] == 4:    # extended linear address record
        addr_ofs = int(self.lines[i]['data'][0:4], 16) * 65536
      elif self.lines[i]['type'] == 2:  # extended segment address record (bits 4–19)
        addr_ofs = int(self.lines[i]['data'][0:4], 16) << 4
      elif self.lines[i]['type'] == 0:
        if (addr_ofs + self.lines[i]['addr']) <= addr and (addr_ofs + self.lines[i]['addr'] + self.lines[i]['len']) > addr:
          return (i, addr_ofs + self.lines[i]['addr'])
    return (-1, -1)

  def replace_data(self, addr, size, data):
    if size != 1 and size != 2 and size != 4:
      print("size %d is not supported" % size)
      return False
    (i, line_addr) = self.addr_to_lineno(addr)
    if i >= 0:
      ofs = (addr - line_addr)
      if (addr + size) > (line_addr + self.lines[i]['len']):   # data stretches over 2 lines
        # make sure there is no jump in address to the next line
        if (i+1) == len(self.lines) or self.lines[i]['type'] != 6 or ((self.lines[i+1]['addr'] - self.lines[i]['addr']) > self.lines[i]['len']):
          print("out of bound error")   # trying to overwrite an address that is not present in the hex file
          return False
        self.lines[i]['data'] = self.insert_data(self.lines[i]['data'], ofs, self.lines[i]['len'] - ofs, data)
        self.lines[i+1]['data'] = self.insert_data(self.lines[i+1]['data'], 0, size - (self.lines[i]['len'] - ofs), data)
        self.update_line_crc(i+1)
      else:
        self.lines[i]['data'] = self.insert_data(self.lines[i]['data'], (addr - line_addr), size, data)
      self.update_line_crc(i)
      return True
    return False

  def insert_data(self, line, ofs, size, data):  # inserts 'data' of length 'size' into 'line' at offset 'ofs'
    if size == 1:
      return line[:ofs*2] + ("%02X" % (data % 256)) + line[(ofs+size)*2:]
    elif size == 2:
      return line[:ofs*2] + ("%02X%02X" % (data % 256, (data >> 8) % 256)) + line[(ofs+size)*2:]             # little endian!
    elif size == 4:
      return line[:ofs*2] + ("%02X%02X%02X%02X" % (data % 256, (data >> 8) % 256, (data >> 16) % 256, (data >> 24) % 256)) + line[(ofs+size)*2:]    # little endian!

  def update_line_crc(self, idx):
    if idx < len(self.lines):
      self.lines[idx]['crc'] = self.calc_line_crc("%02X%04X%02X%s" % (self.lines[idx]['len'], self.lines[idx]['addr'], self.lines[idx]['type'], self.lines[idx]['data']))

  def calc_line_crc(self, line):
    crc = 0
    l = 0
    while l < len(line) - 1:
      crc = crc + int(line[l:l+2], 16)
      l = l + 2
    crc = (~crc + 1) % 256
    return crc
