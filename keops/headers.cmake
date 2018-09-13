#------------------------------------------------------------------------------------#
#------------------------------- COMPILATOR OPTS ------------------------------------#
#------------------------------------------------------------------------------------#

if (CMAKE_CXX_COMPILER_ID MATCHES "Clang")
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} --std=c++11 -Wall -ferror-limit=2")
else()
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} --std=c++11 -Wall -fmax-errors=2")
endif()

set(CMAKE_CXX_FLAGS_DEBUG "${CMAKE_CXX_FLAGS_DEBUG} -O0 -g")
set(CMAKE_CXX_FLAGS_RELEASE "${CMAKE_CXX_FLAGS_RELEASE} -O3")

set (CUDA_PROPAGATE_HOST_FLAGS ON)

if(APPLE)
    set(CMAKE_SHARED_LIBRARY_SUFFIX ".so")
    set(CMAKE_MACOSX_RPATH TRUE)
endif(APPLE)


#------------------------------------------------------------------------------------#
#------------------------------FIND CUDA AND GPUs------------------------------------#
#------------------------------------------------------------------------------------#

find_package(CUDA QUIET)
if(${CUDA_FOUND})
    message(STATUS "Found Cuda: ${CUDA_TOOLKIT_ROOT_DIR}")
else()
    message(STATUS "Found Cuda: FALSE")
endif()

if(NOT DEFINED USE_CUDA)
    Set(USE_CUDA ${CUDA_FOUND})
endif()

if(CUDA_FOUND AND USE_CUDA)

    # A function for automatic detection of GPUs installed (source: caffe git repo).
    function(caffe_detect_installed_gpus out_variable)
        if(NOT CUDA_gpu_detect_output)
            set(__cufile ${PROJECT_BINARY_DIR}/detect_cuda_archs.cu)

            file(WRITE ${__cufile} ""
                "#include <cstdio>\n"
                "int main()\n"
                "{\n"
                "  int count = 0;\n"
                "  if (cudaSuccess != cudaGetDeviceCount(&count)) return -1;\n"
                "  if (count == 0) return -1;\n"
                "  for (int device = 0; device < count; ++device)\n"
                "  {\n"
                "    cudaDeviceProp prop;\n"
                "    if (cudaSuccess == cudaGetDeviceProperties(&prop, device))\n"
                "      std::printf(\"%d.%d \", prop.major, prop.minor);\n"
                "  }\n"
                "  return 0;\n"
                "}\n")

            execute_process(COMMAND "${CUDA_NVCC_EXECUTABLE}" "--run" "${__cufile}"
                WORKING_DIRECTORY "${PROJECT_BINARY_DIR}/CMakeFiles/"
                RESULT_VARIABLE __nvcc_res OUTPUT_VARIABLE __nvcc_out
                ERROR_QUIET OUTPUT_STRIP_TRAILING_WHITESPACE)

            if(__nvcc_res EQUAL 0)
                string(REPLACE "2.1" "2.1(2.0)" __nvcc_out "${__nvcc_out}")
                set(CUDA_gpu_detect_output ${__nvcc_out} CACHE INTERNAL "Returned GPU architetures from caffe_detect_gpus tool" FORCE)
            endif()
        endif()

        if(NOT CUDA_gpu_detect_output)
            set(${out_variable} FALSE PARENT_SCOPE)

            #if(CUDA_VERSION_MAJOR GREATER 8) # cuda does not support 20 arch after cuda 9
                #set(${out_variable}  "30 35 50 60 61" PARENT_SCOPE)
            #else()
                #set(${out_variable}  "20 21(20) 30 35 50 60 61" PARENT_SCOPE)
            #endif()
        else()
            set(${out_variable} ${CUDA_gpu_detect_output} PARENT_SCOPE)
        endif()
    endfunction()

    # run the detection 
    if(NOT gpu_compute_capability)
        caffe_detect_installed_gpus(gpu_compute_capability)
        if(NOT gpu_compute_capability)
            set(USE_CUDA FALSE)
            message(STATUS "No GPU detected. USE_CUDA set to FALSE.")
        else()
            # remove dots and convert to lists
            string(REGEX REPLACE "\\." "" gpu_compute_capability "${gpu_compute_capability}")
            string(REGEX MATCHALL "[0-9()]+" gpu_compute_capability "${gpu_compute_capability}")
            List(REMOVE_DUPLICATES gpu_compute_capability)
            message(STATUS "Compute capability automatically set to: ${gpu_compute_capability}")
        endif()
    else()
        message(STATUS "Compute capability manually set to ${gpu_compute_capability}")
    endif()

    if(USE_CUDA)
        # Options for nvcc
        # Tell NVCC to add binaries for the specified GPUs
        foreach(__arch ${gpu_compute_capability})
            if(__arch MATCHES "([0-9]+)\\(([0-9]+)\\)")
                # User explicitly specified PTX for the concrete BIN
                List(APPEND CUDA_NVCC_FLAGS "-gencode=arch=compute_${CMAKE_MATCH_2},code=sm_${CMAKE_MATCH_1}")
            else()
                # User didn't explicitly specify PTX for the concrete BIN, we assume PTX=BIN
                List(APPEND CUDA_NVCC_FLAGS "-gencode=arch=compute_${__arch},code=sm_${__arch}")
            endif()
        endforeach()

        List(APPEND CUDA_NVCC_FLAGS "--use_fast_math")
        List(APPEND CUDA_NVCC_FLAGS "--compiler-options=-fPIC")


        if(CUDA_VERSION_MAJOR EQUAL 7) # cuda 7 want gcc4.9 
            List(APPEND CUDA_NVCC_FLAGS -ccbin gcc-4.9)
        endif()
    endif()

else()
    set(USE_CUDA 0)
endif()

# this flag is used in pragma
if(USE_CUDA)
    add_definitions(-DUSE_CUDA=1)
else()
    add_definitions(-DUSE_CUDA=0)
endif()

#------------------------------------------------------------------------------------#
#----------------------------------- KeOps OPTS -------------------------------------#
#------------------------------------------------------------------------------------#

# Shared object name
if(NOT shared_obj_name)
    set(shared_obj_name keops)
endif()

message(STATUS "Using shared_obj_name: ${shared_obj_name}")

# Template macros.
add_definitions(-D_FORCE_INLINES)
add_definitions(-DCUDA_BLOCK_SIZE=192)

# - type for computation. The CACHE option enable to see it in ccmake.
if(NOT __TYPE__)
    Set(__TYPE__ float CACHE STRING "Precision type of the computations (float or double)")
endif()
add_definitions(-D__TYPE__=${__TYPE__})

# - Declare the templates formula if not provided by the user
if(NOT DEFINED USENEWSYNTAX)
    Set(USENEWSYNTAX TRUE)
endif()

if(NOT USENEWSYNTAX)

    if(NOT FORMULA)
        Set(FORMULA "SumReduction<Scal<Square<Scalprod<_X<3,4>,_Y<4,4>>>,GaussKernel<_P<0,1>,_X<1,3>,_Y<2,3>,_Y<5,3>>>>" CACHE STRING "Template formula to be instantiated")
    endif()
    unset(FORMULA_OBJ CACHE)

else()
    
    if(NOT FORMULA_OBJ)
        Set(VAR_ALIASES "auto x=Vx(1,3); auto y=Vy(2,3); auto u=Vx(3,4); auto v=Vy(4,4); auto b=Vy(5,3); auto p=Pm(0,1);")
        Set(FORMULA_OBJ "SumReduction(Square((u|v))*Exp(-p*SqNorm2(x-y))*b,0)")
    endif()
    unset(FORMULA CACHE)

endif()

# We should generate a file to avoid parsing problem with shell: write the macros  in a file which will be included
configure_file(${CMAKE_CURRENT_LIST_DIR}/formula.h.in ${shared_obj_name}.h @ONLY)
