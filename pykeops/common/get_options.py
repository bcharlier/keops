import re
import numpy as np
from collections import OrderedDict

############################################################
#              Search for GPU
############################################################

# is there a working GPU around ?
import GPUtil
try:
    gpu_available = len(GPUtil.getGPUs()) > 0
except:
    gpu_available = False

# is torch installed ?
try:
    import torch
    torch_found = True
    gpu_available = torch.cuda.is_available() # if torch is found, we use it to detect the gpu
    from torch.utils import cpp_extension
    torch_include_path = torch.utils.cpp_extension.include_paths()[0]
except:
    torch_found = False
    torch_include_path = "0"

############################################################
#     define backend
############################################################

class pykeops_backend():
    """
    This class is  used to centralized the options used in PyKeops.
    """

    dev = OrderedDict([("CPU",0),("GPU",1)])
    grid = OrderedDict([("1D",0),("2D",1)])
    memtype = OrderedDict([("host",0), ("device",1)])

    possible_options_list = ["auto",
                             "CPU",
                             "GPU",
                             "GPU_1D", "GPU_1D_device", "GPU_1D_host",
                             "GPU_2D", "GPU_2D_device", "GPU_2D_host"
                             ]

    def define_tag_backend(self, backend, variables):
        """
        Try to make a good guess for the backend...  available methods are: (host means Cpu, device means Gpu)
           CPU : computations performed with the host from host arrays
           GPU_1D_device : computations performed on the device from device arrays, using the 1D scheme
           GPU_2D_device : computations performed on the device from device arrays, using the 2D scheme
           GPU_1D_host : computations performed on the device from host arrays, using the 1D scheme
           GPU_2D_host : computations performed on the device from host data, using the 2D scheme

        :param backend (str), variables (tuple)

        :return (tagCPUGPU, tag1D2D, tagHostDevice)
        """

        # check that the option is valid
        if (backend not in self.possible_options_list):
            raise ValueError('Invalid backend. Should be one of ', self.possible_options_list)

        # auto : infer everything
        if backend == "auto":
            return int(gpu_available), self._find_grid(), self._find_mem(variables)

        split_backend = re.split('_',backend)
        if len(split_backend) == 1:     # CPU or GPU
            return self.dev[split_backend[0]], self._find_grid(), self._find_mem(variables)
        elif len(split_backend) == 2:   # GPU_1D or GPU_2D
            return self.dev[split_backend[0]], self.grid[split_backend[1]], self._find_mem(variables)
        elif len(split_backend) == 3:   # the option is known
            return self.dev[split_backend[0]], self.grid[split_backend[1]], self.memtype[split_backend[2]]

    def define_backend(self, backend, variables):
        tagCPUGPU, tag1D2D, tagHostDevice  = self.define_tag_backend(backend, variables)
        return self.dev[tagCPUGPU], self.grid[tag1D2D], self.memtype[tagHostDevice]

    @staticmethod
    def _find_dev():
            return int(gpu_available)

    @staticmethod
    def _find_mem( variables):
        if all([type(var) is np.ndarray for var in variables ]): # Infer if we're working with numpy arrays or torch tensors:
            MemType = 0
        elif torch_found and all([type(var) is torch.Tensor for var in variables ]):

            from pykeops.torch.utils import is_on_device
            VarsAreOnGpu = tuple(map(is_on_device, tuple(variables)))

            if all(VarsAreOnGpu):
                MemType = 1
            elif not any(VarsAreOnGpu):
                MemType = 0
            else:
                raise ValueError("At least two input variables have different memory locations (Cpu/Gpu).")
        else:
            raise TypeError("All variables should either be numpy arrays or torch tensors.")

        return MemType

    @staticmethod
    def _find_grid():
        return 0


def get_tag_backend(backend, variables, str = False):
    """
    entry point to get the correct backend
    """
    res = pykeops_backend()
    if not str:
        return res.define_tag_backend(backend, variables)
    else:
        return res.define_backend(backend, variables)