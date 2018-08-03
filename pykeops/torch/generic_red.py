import torch
from torch.autograd import Variable

from pykeops import default_cuda_type
from pykeops.common.utils import axis2cat, cat2axis
from pykeops.common.parse_type import get_type
from pykeops.common.get_options import get_tag_backend
from pykeops.common.keops_io import load_keops


class Genred(torch.autograd.Function):
    """
    This class is the entry point to pytorch auto grad engine.
    """

    @staticmethod
    def forward(ctx, formula, aliases, backend, cuda_type, *args):

        myconv = load_keops(formula, aliases, cuda_type, 'torch')

        # Context variables: save everything to compute the gradient:
        ctx.formula = formula
        ctx.aliases = aliases
        ctx.axis = cat2axis(myconv.tagIJ)
        ctx.backend = backend
        ctx.cuda_type = cuda_type
        ctx.myconv = myconv

        tagCPUGPU, tag1D2D, tagHostDevice = get_tag_backend(backend, args)
        result = myconv.genred_pytorch(tagCPUGPU, tag1D2D, tagHostDevice, *args)

        # relying on the "ctx.saved_variables" attribute is necessary  if you want to be able to differentiate the output
        #  of the backward once again. It helps pytorch to keep track of "who is who".
        ctx.save_for_backward(*args)

        return result

    @staticmethod
    def backward(ctx, G):
        formula = ctx.formula
        aliases = ctx.aliases
        axis = ctx.axis
        backend = ctx.backend
        cuda_type = ctx.cuda_type
        myconv = ctx.myconv
        args = ctx.saved_tensors  # Unwrap the saved variables

        # If formula takes 5 variables (numbered from 0 to 4), then the gradient
        # wrt. the output, G, should be given as a 6-th variable (numbered 5),
        # with the same dim-cat as the formula's output.
        eta = "Var(" + str(myconv.nargs) + "," + str(myconv.dimout) + "," + str(axis2cat(axis)) + ")"

        grads = []  # list of gradients wrt. args;

        for (var_ind, sig) in enumerate(ctx.aliases):  # Run through the arguments
            # If the current gradient is to be discarded immediatly...
            if not ctx.needs_input_grad[var_ind + 4]:  # because of (formula, aliases, backend, cuda_type)
                grads.append(None)  # Don't waste time computing it.

            else:  # Otherwise, the current gradient is really needed by the user:
                # adding new aliases is way too dangerous if we want to compute
                # second derivatives, etc. So we make explicit references to Var<ind,dim,cat> instead.
                _, cat, dim, pos = get_type(sig)
                var = "Var(" + str(pos) + "," + str(dim) + "," + str(cat) + ")"  # V
                formula_g = "Grad(" + formula + "," + var + "," + eta + ")"  # Grad<F,V,G>
                args_g = args + (G,)  # Don't forget the gradient to backprop !

                # N.B.: if I understand PyTorch's doc, we should redefine this function every time we use it?
                genconv = Genred().apply

                if cat == 2:  # we're referring to a parameter, so we'll have to sum both wrt 'i' and 'j'
                    # WARNING !! : here we rely on the implementation of DiffT in files in folder keops/core/reductions
                    # if tagI==cat of V is 2, then reduction is done wrt j, so we need to further sum output wrt i
                    grad = genconv(formula_g, aliases, backend, cuda_type, *args_g)
                    # Then, sum 'grad' wrt 'i' :
                    # I think that ".sum"'s backward introduces non-contiguous arrays,
                    # and is thus non-compatible with Genred: grad = grad.sum(0)
                    # We replace it with a "handmade hack" :
                    grad = Variable(torch.ones(1, grad.shape[0]).type_as(grad.data)) @ grad
                    grad = grad.view(-1)
                else:
                    grad = genconv(formula_g, aliases, backend, cuda_type, *args_g)
                grads.append(grad)

        # Grads wrt. formula, aliases, backend, *args
        return (None, None, None, None, *grads)


class Sum(Genred):
    def __init__(self, formula, aliases, axis=1, backend="auto", cuda_type=default_cuda_type):
        self.formula = "SumReduction(" + formula + "," + str(axis2cat(axis)) + ")"
        self.aliases = aliases
        self.backend = backend
        self.cuda_type = cuda_type

    def __call__(self, *args):
        return self.apply(self.formula, self.aliases, self.backend, self.cuda_type, *args)


class LogSumExp(Genred):
    def __init__(self, formula, aliases, axis=1, backend="auto", cuda_type=default_cuda_type):
        self.formula = "LogSumExpReduction(" + formula + "," + str(axis2cat(axis)) + ")"
        self.aliases = aliases
        self.backend = backend
        self.cuda_type = cuda_type

    def __call__(self, *args):
        return self.apply(self.formula, self.aliases, self.backend, self.cuda_type, *args)

