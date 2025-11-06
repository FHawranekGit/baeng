import sys
import json
from typing import Literal
import numpy as np
import re
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

        self.user_functions = script.copy()
        self.user_functions.pop("IR")
        self.user_functions.pop("CODE")

        self.operators = {
            "if": self._if_op,
            "while": self._while_op,
            "define": self._define_op,
            "setSample": self._set_sample_op,
            "readSample": self._read_sample_op
        }

    def _if_op(self, condition, code_block, scope):
        pass

    def _while_op(self, condition, code_block, scope):
        pass

    def _define_op(self, name, value, scope):
        pass

    def _set_sample_op(self, key, scope):
        pass

    def _read_sample_op(self, key, scope) -> float:
        pass

    def _eval_string(self, string):
        out = None
        exec("out = " + string)
        return out

    def _replace_vars_in_string(self, expr: str, mapping: dict) -> str:
        """assisted by AI"""
        # Regex baut ein Muster aus allen Keys, sortiert nach Länge (wichtig!)
        pattern = re.compile(r'\b(' + '|'.join(sorted(mapping.keys(), key=len, reverse=True)) + r')\b')

        # Ersetzungsfunktion: nimmt den gefundenen Namen und ersetzt ihn durch den Wert
        return pattern.sub(lambda m: str(mapping[m.group(0)]), expr)


    def _interpret_codeblock(self, codeblock: list, local_vars: dict, scope: Literal["global", "local"]):
        for code_line in codeblock:
            try:
                self.operators[code_line[0]](*code_line[1:], scope=scope)
            except KeyError:
                if code_line[0] in self.user_functions:
                    for SAMPLEPOS in range(self.IR.fs):
                        parameter_names = self.user_functions[code_line[0]]["PARAMS"]
                        parameter_values = []
                        for parameter in code_line[1]:
                            if parameter is list:
                                parameter_values.append(self.operators[parameter[0]](*parameter[1:], scope=scope))
                            elif parameter is str:
                                # local variables
                                parameter = self._replace_vars_in_string(parameter, local_vars)
                                #global vars
                                parameter = self._replace_vars_in_string(parameter, self.global_vars)
                                parameter_values.append(self._eval_string(parameter))

                        parameters = dict(zip(parameter_names, parameter_values))
                        self._interpret_codeblock(
                            self.user_functions[code_line[0]]["CODE"],
                            local_vars=parameters,
                            scope="local"
                        )
                else:
                    raise NotImplementedError()


    def run(self):
        self._interpret_codeblock(self.script["CODE"], local_vars=dict(), scope="global")


if __name__ == "__main__":
    pass
