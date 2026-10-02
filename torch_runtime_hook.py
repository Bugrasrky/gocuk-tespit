import os
import sys


if getattr(sys, "frozen", False):
    internal_dir = sys._MEIPASS
    torch_lib = os.path.join(sys._MEIPASS, "torch", "lib")
    os.add_dll_directory(internal_dir)
    os.environ.setdefault("PATH", internal_dir + os.pathsep + os.environ.get("PATH", ""))
    if os.path.isdir(torch_lib):
        os.add_dll_directory(torch_lib)
        os.environ.setdefault("PATH", torch_lib + os.pathsep + os.environ.get("PATH", ""))

    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
