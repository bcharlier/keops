import os.path
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + (os.path.sep + '..')*2)

import numpy as np
import time, timeit

from pykeops.numpy.utils import np_kernel

# size of the test
N = 2000 ; M = 300; D = 3; E = 3

type = 'float32'
# declare numpy variables 
x = np.random.randn(N,D).astype(type)
y = np.random.randn(M,D).astype(type)
b = np.random.randn(M,E).astype(type)
sigma = np.array([2.4]).astype(type)

# declare their torch counterparts
try:
    import torch

    use_cuda = torch.cuda.is_available()
    dtype    = torch.cuda.FloatTensor if use_cuda else torch.FloatTensor

    xc = torch.from_numpy(x.copy()).type(dtype)
    yc = torch.from_numpy(y.copy()).type(dtype)
    bc = torch.from_numpy(b.copy()).type(dtype)
    sigmac = torch.from_numpy(sigma.copy()).type(dtype)

except:
    pass


##############################
# Benchmark
##############################

enable_GC = False # Garbage collection?
GC = 'gc.enable();' if enable_GC else 'pass;'
LOOPS = 200
print("Times to compute ", LOOPS, " convolutions of size {}x{}:".format(N,M))
print("\n",end="")

for k in (["gaussian", "laplacian", "cauchy", "inverse_multiquadric"]):
    print('----------------------------------- kernel: ' + k)
    
    # pure numpy
    gnumpy =  np_kernel(x,y,sigma,kernel=k) @ b
    speed_numpy = timeit.Timer('gnumpy =  np_kernel(x,y,sigma,kernel=k) @ b', 
            GC, globals = globals(),
            timer = time.time).timeit(LOOPS)
    print("Time for Python:              {:.4f}s".format(speed_numpy))

    # keops + pytorch : generic tiled implementation (with cuda if available else uses cpu)
    try:
        from pykeops.torch.utils import torch_kernel
        from pykeops.torch import Kernel, kernel_product

        params = {
            "id"      : Kernel(k+"(x,y)"),
            "gamma"   : 1./torch.autograd.Variable(sigmac, requires_grad=False).type(dtype)**2,
            "backend" : "auto",
        }
        g1 = kernel_product(params,xc,yc,bc,  mode='sum').cpu()
        speed_pykeops_gen = timeit.Timer("g1 = kernel_product( params,xc,yc,bc,  mode='sum').cpu()", GC,  globals = globals(), timer = time.time).timeit(LOOPS)
        print("Time for keops generic:       {:.4f}s".format(speed_pykeops_gen),end="")
        print("   (absolute error:       ", np.max(np.abs(g1.data.numpy() - gnumpy)), ")")
    except:
        print('Time for keops generic:       Not Done')

    # vanilla pytorch (with cuda if available else uses cpu)
    try:
        g0 = torch.mm(torch_kernel(xc,yc,sigmac,kernel=k),bc).cpu().numpy()
        speed_pytorch = timeit.Timer('g0 = torch.mm(torch_kernel(xc,yc,sigmac,kernel=k),bc)#.cpu().numpy()', GC, globals = globals(), timer = time.time).timeit(LOOPS)
        print("Time for Pytorch:             {:.4f}s".format(speed_pytorch),end="")
        print("   (absolute error:       ", np.max(np.abs(g0 - gnumpy)),")")
    except:
        print('Time for Pytorch:             Not Done')

    # specific cuda tiled implementation (if cuda is available)
    try:
        from pykeops.numpy.convolutions.radial_kernel import RadialKernelConv
        my_conv = RadialKernelConv(type)
        g2 = my_conv(x, y, b, sigma, kernel=k)
        speed_pykeops = timeit.Timer('g2 = my_conv(x, y, b, sigma, kernel=k)', GC, globals = globals(), timer = time.time).timeit(LOOPS)
        print("Time for keops cuda specific: {:.4f}s".format(speed_pykeops),end="")
        print("   (absolute error:       ", np.max(np.abs(g2 - gnumpy)),")")
    except:
        print("Time for keops cuda specific: Not Done")
