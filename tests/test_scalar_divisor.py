"""Regression: divisor-safe scalar fuzzing excludes 0 from divisor operands.

Guards the lever that unblocked fix16_mod (and the modular/GCD/hash-finalizer
class): a nonzero per-param constraint OR a divide/modulo function shape must
drop 0 from that operand's fuzz pool so the compiled C oracle never SIGFPEs on
`x % 0` / `x / 0` and refuses a trivially-translatable function.
"""
from alchemist.verifier.auto_config import _is_nonzero_constraint, _is_divide_shape


class _Alg:
    def __init__(self, notes="", purpose=""):
        self.algorithm_notes = notes
        self.purpose = purpose


def test_nonzero_constraint_phrasings():
    for t in ["must not be zero", "must not be 0", "nonzero", "non-zero",
              "divisor, must not be equal to zero", "y != 0", "neq 0"]:
        assert _is_nonzero_constraint(t), t
    for t in ["", "any value", "the dividend", "positive integer"]:
        assert not _is_nonzero_constraint(t), t


def test_divide_shape_detection():
    assert _is_divide_shape(_Alg(notes="computes x % y using the modulo operator"))
    assert _is_divide_shape(_Alg(purpose="Computes the remainder of dividing two values"))
    assert _is_divide_shape(_Alg(notes="integer division of a by b"))
    assert not _is_divide_shape(_Alg(notes="adds two fixed-point numbers"))
    assert not _is_divide_shape(_Alg(purpose="linear interpolation"))
