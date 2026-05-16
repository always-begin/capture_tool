import sys
from PyInstaller.utils.win32.versioninfo import (
    VSVersionInfo, FixedFileInfo, StringFileInfo,
    StringTable, StringStruct, VarFileInfo, VarStruct
)

version = sys.argv[1]
parts   = version.split(".")
v1, v2, v3 = int(parts[0]), int(parts[1]), int(parts[2])

version_info = VSVersionInfo(
    ffi=FixedFileInfo(
        filevers=(v1, v2, v3, 0),
        prodvers=(v1, v2, v3, 0),
    ),
    kids=[
        StringFileInfo([
            StringTable("040904b0", [
                StringStruct("CompanyName",      "always-begin"),
                StringStruct("FileDescription",  "Screen Capture and Practical Utility Tool"),
                StringStruct("FileVersion",      version),
                StringStruct("InternalName",     "CapTool"),
                StringStruct("LegalCopyright",   "Copyright (c) 2026 Tatan"),
                StringStruct("OriginalFilename", "CapTool.exe"),
                StringStruct("ProductName",      "CapTool"),
                StringStruct("ProductVersion",   version),
            ])
        ]),
        VarFileInfo([VarStruct("Translation", [0x0409, 1200])])
    ]
)

with open("version_info_generated.txt", "w") as f:
    f.write(str(version_info))