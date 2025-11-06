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


global_vars = dict()


def interpret_codeblock(codeblock: list, local_vars: dict, scope: Literal["global", "local"]):
    pass

class Baeng:
    def __init__(self, code: list):
        self.code = code

if __name__ == "__main__":
    pass
