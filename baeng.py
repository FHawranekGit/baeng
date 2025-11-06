import sys
import json
from typing import Literal
import numpy as np
from scipy.io import wavfile


class ImpulseResponse:
    def __init__(self, fs: int, duration: int | float):
        pass

    def __getitem__(self, index: int | float) -> np.float32:
        pass

    def __setitem__(self, index: int | float, value: float):
        pass

    def to_numpy(self) -> np.ndarray:
        pass


class Baeng:
    def __init__(self, script: dict):
        self.script = script

        self.global_vars = dict()

        self.IR = ImpulseResponse(*self.script["IR"])

        self.functions = script.copy()
        self.functions.pop("IR")
        self.functions.pop("CODE")

        self.operators = {
            "if": self._if_op,
            "while": self._while_op,
            "define": self._define_op,
            "setSample": self._set_sample_op,
            "readSample": self._read_sample_op
        }

    def _if_op(self):
        pass

    def _while_op(self):
        pass

    def _define_op(self):
        pass

    def _set_sample_op(self):
        pass

    def _read_sample_op(self):
        pass


    def _interpret_codeblock(self, codeblock: list, local_vars: dict, scope: Literal["global", "local"]):
        for code_line in codeblock:
            pass


    def run(self):
        self._interpret_codeblock(self.script["CODE"], local_vars=dict(), scope="global")


if __name__ == "__main__":
    pass
