# Intel HEX File Patcher

Patch an Intel HEX file, i.e. overwrite variable contents in the compiled firmware.

## How to set the memory location
To place a variable/struct at a certain memory location with gcc:
"""
volatile mystruct_t  __attribute((section (".fwConfigSection"))) mystruct = { 0 };
"""
and register the section with the linker:
"""
   LDFLAGS += -Wl,--section-start -Wl,.fwConfigSection=[address]
"""

## How to use the script
The main script is *patchHexFile.py*. Usage:
"""  
./patchHexFile.py [firmware] [config]

  firmware 	 filename of the firmware (Intel hex format)
  config 	 (optional) filename of the XML config; if not provided, 'fwConfig.xml' will be used
"""

## XML config file structure
A basic example:
"""
<?xml version="1.0"?>
<firmwareconfig>
  <section name="firmwareconfig" address="0xd000">
    <int bytes="2" offset="0x0" name="node_id">1</int>
    <int bytes="2" offset="0x2" name=>parameter2value</int>
  </section>
</firmwareconfig>
"""
The attribute *name* is optional, but makes reading the config file easier.
The *bytes* attribute can be either 1, 2 or 4 bytes.
The value itself can be given in dec or hex.

## Generate XML config from C struct
The helper script *generateXmlConfig.py* can automatically generate an XML config file from a C struct.
Usage:
"""
./generateXmlConfig.py [struct] [address] [values] ([filename])

  struct 	 the name of the C struct to parse, or the full struct enclosed in quotation marks
  address 	 target address in the hex file
  values 	 a list of values to fill into the struct, enclosed in quotation marks
  filename 	 (optional) name of the file where the C struct is stored; if not provided, script will automatically search for the struct in the current directory
"""
Example:
"""
./generateXmlConfig.py mystruct_t 0xd000 "0,1,2,3"
"""
The script will then look for the definition of the struct 'mystruct_t' in all header and source code files within the current working directory and its subfolders. If found, the struct is parsed and an Xml config file will be generated.  
Example 2:  
"""
./generateXmlConfig.py "typedef struct { uint16_t node_id; uint32_t rand_seed; } mystruct_t;" 0xd000 "0,1,2,3"
"""
It is possible to directly pass the struct as an argument to the script.

Notes:
- struct must be stored in a *.h* or *.c* file
- struct needs to be defined in the following form: *typedef struct { ... } mystruct_t;*
- supported data types: int8_t, uint8_t, char, int16_t, uint16_t, int32_t, uint32_t
- arrays are allowed
