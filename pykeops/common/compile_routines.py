import os
import shutil
import sys
import subprocess

import pykeops.config
from pykeops.common.parse_type import check_aliases_list
from pykeops.common.utils import c_type
from hashlib import sha256

def run_and_display(args, build_folder, msg=''):
    """
    This function run the command stored in args and display the output if needed
    :param args: list
    :param msg: str
    :return: None
    """
    try:
        proc = subprocess.run(args, cwd=build_folder, stdout=subprocess.PIPE, check=True)
        if pykeops.config.verbose:
            print(proc.stdout.decode('utf-8'))

    except subprocess.CalledProcessError as e:
        print('\n--------------------- ' + msg + ' DEBUG -----------------')
        print(e)
        print(e.stdout.decode('utf-8'))
        print('--------------------- ----------- -----------------')
    

def replace_string_in_file(filename, source_string, target_string):
        # replaces all occurences of source_string by target_string in file named filename
        subprocess.run(['LC_ALL=C sed -i.bak "s/'+source_string+'/'+target_string+'/g" '+filename+' && rm '+filename+'.bak'],shell=True)

    
def get_or_build_pybind11_template(dtype, lang, include_dirs):
    
    command_line = ["cmake", pykeops.config.script_template_folder,
                     "-DCMAKE_BUILD_TYPE=" + "'{}'".format(pykeops.config.build_type),
                     "-DPYTHON_LANG=" + "'{}'".format(lang),
                     "-D__TYPE__=" + "'{}'".format(c_type[dtype]),
                     "-DPYTHON_EXECUTABLE=" + "'{}'".format(sys.executable),
                     "-DPYBIND11_PYTHON_VERSION=" + "'{}'".format(str(sys.version_info.major) + "." + str(sys.version_info.minor)),
                     "-DC_CONTIGUOUS=1",
                    ] + include_dirs
    template_name = 'libKeOps_template_' + sha256(''.join(command_line).encode("utf-8")).hexdigest()[:10]
    
    if not os.path.exists(pykeops.config.bin_folder + template_name + '.o'):
        
        print('Compiling pybind11 template ' + template_name + ' in ' + os.path.realpath(pykeops.config.bin_folder) + '...', flush=True)
        #print('(with dtype=',dtype,', lang=',lang,', include_dirs=',include_dirs,')', flush=True)
        
        template_build_folder = pykeops.config.bin_folder + '/build-' + template_name
        
        os.mkdir(template_build_folder)
        
        command_line += ["-Dshared_obj_name=" + "'{}'".format(template_name)]
        
        run_and_display(command_line + ["-DcommandLine=" + " ".join(command_line)],
                        template_build_folder,
                        msg="CMAKE")
                        
        run_and_display(["cmake", "--build", ".", "--target", template_name, "--", "VERBOSE=1"], template_build_folder, msg="MAKE")
        
        shutil.rmtree(template_build_folder)
        
        print('Done.')
        
    return template_name
    
    
def compile_generic_routine(formula, aliases, dllname, dtype, lang, optional_flags, include_dirs, build_folder):
    
    aliases = check_aliases_list(aliases)

    def process_alias(alias):
        if alias.find("=") == -1:
            return ''  # because in this case it is not really an alias, the variable is just named
        else:
            return 'auto ' + str(alias) + '; '

    def process_disp_alias(alias):
        return str(alias) + '; '

    alias_string = ''.join([process_alias(alias) for alias in aliases])
    alias_disp_string = ''.join([process_disp_alias(alias) for alias in aliases])

    print(
        'Compiling ' + dllname + ' in ' + os.path.realpath(build_folder + os.path.sep + '..' ) + ':\n' + '       formula: ' + formula + '\n       aliases: ' + alias_disp_string + '\n       dtype  : ' + dtype + '\n... ',
        end='', flush=True)

    template_name = get_or_build_pybind11_template(dtype, lang, include_dirs)
    
    template_dllname = 'KeOps_formula'
    
    # creating KeOps include file for formula
    template_include_file = pykeops.config.script_formula_folder + os.path.sep + 'formula.h.in'
    target_include_file = build_folder + os.path.sep + template_dllname + '.h'
    shutil.copyfile(template_include_file,target_include_file)
    
    replace_pairs = [
            ('@__TYPE__@', c_type[dtype]),
            ('@FORMULA_OBJ@', formula),
            ('@VAR_ALIASES@', alias_string),
            ]
            
    for p in replace_pairs:
        replace_string_in_file(target_include_file, p[0], '{}'.format(p[1]))
        
    
    
    if not os.path.exists(build_folder+'/CMakeCache.txt'):
        command_line = ["cmake", pykeops.config.script_formula_folder,
                     "-DCMAKE_BUILD_TYPE=" + "'{}'".format(pykeops.config.build_type),
                     "-Dshared_obj_name=" + "'{}'".format(template_dllname),
                     "-D__TYPE__=" + "'{}'".format(c_type[dtype]),
                     "-DC_CONTIGUOUS=1",
                    ] + optional_flags

        run_and_display(command_line + ["-DcommandLine=" + " ".join(command_line)],
                    build_folder,
                    msg="CMAKE")
                    
    run_and_display(["cmake", "--build", ".", "--", "VERBOSE=1"], build_folder, msg="MAKE")
    
    pykeops_folder = os.path.abspath(pykeops.config.script_template_folder+"/../..")
    subprocess.run(["cp "+build_folder+"/CMakeFiles/"+template_dllname+".dir/"+pykeops_folder+"/keops/core/link_autodiff.*.o "+build_folder], cwd=pykeops.config.script_template_folder, shell=True)
    
    subprocess.run([pykeops.config.script_template_folder+"/mylink "+template_name+" "+build_folder+"/link_autodiff.cpp.o "+dllname], cwd=build_folder+"/..", shell=True)
                    
    print('Done.')


def compile_specific_conv_routine(dllname, dtype, build_folder):
    print('Compiling ' + dllname + ' using ' + dtype + ' in ' + os.path.realpath(build_folder + os.path.sep + '..' ) + '... ', end='', flush=True)
    run_and_display(['cmake', pykeops.config.script_specific_folder,
                     '-DCMAKE_BUILD_TYPE=' + pykeops.config.build_type,
                     '-Ushared_obj_name',
                     '-D__TYPE__=' + c_type[dtype],
                     ],
                    build_folder,
                    msg='CMAKE')

    run_and_display(['cmake', '--build', '.', '--target', dllname, '--', 'VERBOSE=1'], build_folder, msg='MAKE')
    print('Done.')


def compile_specific_fshape_scp_routine(dllname, kernel_geom, kernel_sig, kernel_sphere, dtype, build_folder):
    print('Compiling ' + dllname + ' using ' + dtype + ' in ' + os.path.realpath(build_folder + os.path.sep + '..' ) + '... ', end='', flush=True)
    run_and_display(['cmake', pykeops.config.script_specific_folder,
                     '-DCMAKE_BUILD_TYPE=' + pykeops.config.build_type,
                     '-Ushared_obj_name',
                     '-DKERNEL_GEOM=' + kernel_geom,
                     '-DKERNEL_SIG=' + kernel_sig,
                     '-DKERNEL_SPHERE=' + kernel_sphere,
                     '-D__TYPE__=' + c_type[dtype],
                     ],
                    build_folder,
                    msg='CMAKE')

    run_and_display(['cmake', '--build', '.', '--target', dllname, '--', 'VERBOSE=1'], build_folder, msg='MAKE')
    print('Done.')
