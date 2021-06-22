from keops.python_engine.formulas.Operation import Operation
from keops.python_engine.utils.code_gen_utils import c_zero_float, c_for_loop

#/////////////////////////////////////////////////////////////////////////
#////      ComplexSum                           ////
#/////////////////////////////////////////////////////////////////////////

class ComplexSum(Operation):
    string_id = "ComplexSum"

    def __init__(self, f):
        if f.dim % 2 != 0:
            raise ValueError("Dimension of F must be even")
        self.dim = 2
        super().__init__(f)
    
    def Op(self, out, table, inF):
        f = self.children[0]
        string = out[0].assign(c_zero_float)
        string += out[1].assign(out[0])
        forloop, i = c_for_loop(0, f.dim, 2, pragma_unroll=True)
        body = out[0].add_assign(inF[i])
        body += out[1].add_assign(inF[i+1])
        string += forloop(body)
        return string

    def DiffT(self, v, gradin):
        from keops.python_engine.formulas.complex.ComplexSumT import ComplexSumT
        f = self.children[0]
        return f.DiffT(v, ComplexSumT(gradin, f.dim))


