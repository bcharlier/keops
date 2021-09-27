from keops.utils.code_gen_utils import get_hash_name
from keops.get_keops_dll import get_keops_dll
import time
import cppyy
from array import array


class create_or_load:
    library = {}

    @staticmethod
    def __call__(cls, *args):
        
        cls_id = str(cls)
        if cls_id not in create_or_load.library:
            create_or_load.library[cls_id] = {}
        cls_library = create_or_load.library[cls_id]
        hash_name = get_hash_name(*args)
        
        if hash_name in cls_library:
            res = cls_library[hash_name]
        else:
            obj = cls(*args)
            cls_library[hash_name] = obj
            res = obj
        
        return res

class get_keops_routine_class:
    def __init__(self, map_reduce_id, *args):

        start = time.time()
        
        print("ok 1")
        input()
            
        (
            self.dllname,
            self.low_level_code_file,
            self.tagI,
            self.tagZero,
            self.use_half,
            self.cuda_block_size,
            self.use_chunk_mode,
            self.tag1D2D,
            self.dimred,
            self.dim,
            self.dimy,
            indsi,
            indsj,
            indsp,
            dimsx,
            dimsy,
            dimsp,
        ) = get_keops_dll(map_reduce_id, *args)
        
        print("ok 2")
        input()
        
        if self.low_level_code_file == "none":
            raise ValueError("not implemented yet")
            cppyy.load_library(self.dllname)
        else:
            self.dll = cppyy.gbl.context["float"](self.low_level_code_file)
        
        print("ok 3")
        input()
        
        end = time.time()
        print("get_keops_routine_class init, part 1 (get_keops_dll call) :", end-start)
        start = time.time()
        
        print("ok 4")
        input()
            
        # now we switch indsi, indsj and dimsx, dimsy in case tagI=1.
        # This is to be consistent with the convention used in the old
        # bindings (see functions GetIndsI, GetIndsJ, GetDimsX, GetDimsY
        # from file binder_interface.h. Clearly we could do better if we
        # carefully rewrite some parts of the code
        if self.tagI == 1:
            indsi, indsj = indsj, indsi
            dimsx, dimsy = dimsy, dimsx
        
        print("ok 5")
        input()
        
        self.indsi = array("i", (len(indsi),) + indsi)
        self.indsj = array("i", (len(indsj),) + indsj)
        self.indsp = array("i", (len(indsp),) + indsp)
        self.dimsx = array("i", (len(dimsx),) + dimsx)
        self.dimsy = array("i", (len(dimsy),) + dimsy)
        self.dimsp = array("i", (len(dimsp),) + dimsp)
        
        end = time.time()
        print("get_keops_routine_class init, part 2 :", end-start)

    def __call__(
        self,
        c_dtype,
        nx,
        ny,
        tagHostDevice,
        device_id,
        ranges,
        outshape,
        out,
        args,
        argshapes,
    ):
        
        start = time.time()
        
        print("ok 6")
        input()

        nargs = len(args)
        if c_dtype == "float":
            launch_keops = self.dll.launch_keops
        elif c_dtype == "double":
            launch_keops = self.dll.launch_keops_double
        elif c_dtype == "half2":
            launch_keops = self.dll.launch_keops_half
        else:
            raise ValueError(
                "dtype", c_dtype, "not yet implemented in new KeOps engine"
            )
            
        launch_keops_dumb1 = self.dll.launch_keops_dumb1
        launch_keops_dumb2 = self.dll.launch_keops_dumb2
        
        print("ok 7")
        input()
        
        end = time.time()
        print("get_keops_routine_class call, part 1 :", end-start)
        print("**************")
        start = time.time()
        
        launch_keops_dumb1()
        
        end = time.time()
        print("launch keops dumb 1:", end-start)
        start = time.time()
        
        launch_keops_dumb2(
            tagHostDevice,
            self.dimy,
            nx,
            ny,
            device_id,
            self.tagI,
            self.tagZero,
            self.use_half,
            self.tag1D2D,
            self.dimred,
            self.cuda_block_size,
            self.use_chunk_mode,
            self.indsi,
            self.indsj,
            self.indsp,
            self.dim,
            self.dimsx,
            self.dimsy,
            self.dimsp,
            ranges,
            outshape,
            out,
            nargs,
            args,
            argshapes
        )
        
        end = time.time()
        print("launch keops dumb 2:", end-start)
        start = time.time()
        
        print("ok 8")
        input()
        
        print(ranges)
        input()
        
        print(args)
        input()
        
        print(argshapes)
        input()
        
        """
        launch_keops(
            tagHostDevice,
            self.dimy,
            nx,
            ny,
            device_id,
            self.tagI,
            self.tagZero,
            self.use_half,
            self.tag1D2D,
            self.dimred,
            self.cuda_block_size,
            self.use_chunk_mode,
            self.indsi,
            self.indsj,
            self.indsp,
            self.dim,
            self.dimsx,
            self.dimsy,
            self.dimsp,
            ranges,
            outshape,
            out,
            nargs,
            args,
            argshapes
        )
        """
        
        print("ok 9")
        input()
        
        end = time.time()
        print("get_keops_routine_class call, part 2 (launch_keops call) :", end-start)
        print("**************")


def get_keops_routine(*args):    
    return create_or_load()(get_keops_routine_class, *args)
