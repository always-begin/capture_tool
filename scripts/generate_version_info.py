import sys
from PyInstaller.utils.win32.versioninfo import (
    VSVersionInfo, FixedFileInfo, StringFileInfo,
    StringTable, StringProperty, VarFileInfo, VarStruct
)

version = sys.argv[1]  # 例: "1.0.2"
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
                StringProperty("CompanyName",      "always-begin"),
                StringProperty("FileDescription",  "Screen Capture and Practical Utility Tool"),
                StringProperty("FileVersion",      version),
                StringProperty("InternalName",     "CapTool"),
                StringProperty("LegalCopyright",   "Copyright (c) 2026 Tatan"),
                StringProperty("OriginalFilename", "CapTool.exe"),
                StringProperty("ProductName",      "CapTool"),
                StringProperty("ProductVersion",   version),
            ])
        ]),
        VarFileInfo([VarStruct("Translation", [0x0409, 1200])])
    ]
)

with open("version_info_generated.txt", "w") as f:
    f.write(str(version_info))