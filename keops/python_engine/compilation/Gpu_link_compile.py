import os
from keops.python_engine.compilation import link_compile
from keops.python_engine.config import build_path
from ctypes import create_string_buffer, CDLL, c_int, RTLD_GLOBAL
from os import RTLD_LAZY
from keops.python_engine import jit_binary, use_cuda


class Gpu_link_compile(link_compile):

    source_code_extension = "cu"

    low_level_code_extension = "ptx"

    # these were used for command line compiling mode
    # compiler = "nvcc"
    # compile_options = ["-shared", "-Xcompiler -fPIC", "-O3"]

    def __init__(self):
        
        # checking that the system has a Gpu :
        if not use_cuda:
            raise ValueError("[KeOps] Trying to execute Gpu computation but we detected that the system has no properly configured Gpu.")
        
        link_compile.__init__(self)
        # these are used for JIT compiling mode
        # low_level_code_file is filename of low level code generated by the JIT compiler, e.g. 7b9a611f7e.ptx for Cuda
        self.low_level_code_file = (
            build_path
            + os.path.sep
            + self.gencode_filename
            + "."
            + self.low_level_code_extension
        ).encode("utf-8")
        # we load the main dll that must be run in order to compile the code
        CDLL("libnvrtc.so", mode=RTLD_GLOBAL)
        CDLL("libcuda.so", mode=RTLD_GLOBAL)
        CDLL("libcudart.so", mode=RTLD_GLOBAL)
        self.my_c_dll = CDLL(jit_binary, mode=RTLD_LAZY)
        # actual dll to be called is the jit binary
        self.true_dllname = jit_binary
        # file to check for existence to detect compilation is needed
        self.file_to_check = self.low_level_code_file

    def compile_code(self):
        # method to generate the code and compile it
        # generate the code and save it in self.code, by calling get_code method from GpuReduc class :
        self.get_code()
        # write the code in the source file
        self.write_code()
        # we execute the main dll, passing the code as argument, and the name of the low level code file to save the assembly instructions
        self.my_c_dll.Compile(
            create_string_buffer(self.low_level_code_file),
            create_string_buffer(self.code.encode("utf-8")),
            c_int(self.use_half),
            c_int(self.device_id)
        )
        # retreive some parameters that will be saved into info_file.
        self.tagI = self.red_formula.tagI
        self.dim = self.red_formula.dim
        
