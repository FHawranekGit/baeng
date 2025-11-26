import sys
import json
from typing import Literal
import numpy as np
import re
from scipy.io import wavfile
from itertools import cycle


class ImpulseResponse:
    def __init__(self, fs: int, duration: int | float):
        self.data = np.zeros(int(fs * duration), dtype=np.float32)
        self.fs = fs
        self.duration = duration

    def __getitem__(self, index: int):
        return self.data[index]

    def __setitem__(self, index: int, value: float):
        self.data[index] = value

    def to_numpy(self) -> np.ndarray:
        return self.data


class Baeng:
    def __init__(self, script: dict):
        self.script = script

        self.global_vars = dict()
        self.local_variables = [{}]

        self.IR = ImpulseResponse(self.script["IR"][0], self.script["IR"][1])
        self.SAMPLEPOS = 0
        # self.possible_sample_positions = cycle(list(range(0, self.IR.fs * self.IR.duration - 1)))

        self.user_functions = script.copy()
        self.user_functions.pop("IR")
        self.user_functions.pop("CODE")

        self.operators = {
            "if": self._if_op,
            "while": self._while_op,
            "define": self._define_op,
            "setSample": self._set_sample_op,
            "readSample": self._read_sample_op,
        }

    def _if_op(self, condition, code_block, scope):
        if scope == "local":
            scope = "stay_local"
        if self._fetch_parameter(condition, scope=scope):
            self._interpret_codeblock(code_block, parameters={}, scope=scope)

    def _while_op(self, condition, code_block, scope):
        if scope == "local":
            scope = "stay_local"
        while self._fetch_parameter(condition, scope=scope):
            self._interpret_codeblock(code_block, parameters={}, scope=scope)

    def _define_op(self, name, value, scope):
        evaluated_value = self._fetch_parameter(value, scope=scope)
        if scope == "local":
            self.local_variables[-1].update({name: evaluated_value})
        elif scope == "global":
            self.global_vars.update({name: evaluated_value})

    def _set_sample_op(self, key, value, scope):
        index = self._fetch_parameter(key, scope=scope)
        self.IR[index] = self._fetch_parameter(value, scope=scope)

    def _read_sample_op(self, key, scope) -> float:
        index = self._fetch_parameter(key, scope=scope)
        value = self.IR[index]
        return value

    def _eval_string(self, string):
        all_variables = self.local_variables[-1].copy()
        all_variables.update(self.global_vars)
        all_variables.update({"SAMPLEPOS": self.SAMPLEPOS, "IR": self.IR})
        out = eval(string, {}, all_variables)
        return out

    def _fetch_parameter(self, obj, scope):
        if type(obj) is list:
            return self.operators[obj[0]](*obj[1:], scope=scope)
        elif type(obj) is str:
            return self._eval_string(obj)
        elif type(obj) is int or type(obj) is float:
            return obj
        else:
            raise TypeError

    def _interpret_codeblock(
        self,
        codeblock: list,
        parameters: dict,
        scope: Literal["global", "local", "stay_local"],
    ):
        if scope == "local":
            self.local_variables.append(parameters)
        for code_line in codeblock:
            try:
                self.operators[code_line[0]](*code_line[1:], scope=scope)
            except KeyError:
                if code_line[0] in self.user_functions:
                    for sample_position in range(self.IR.fs * self.IR.duration):
                        self.SAMPLEPOS = sample_position
                        parameter_names = self.user_functions[code_line[0]]["PARAMS"]
                        parameter_values = []
                        for parameter in code_line[1]:
                            parameter_values.append(
                                self._fetch_parameter(parameter, scope=scope)
                            )

                        new_parameters = dict(zip(parameter_names, parameter_values))
                        self._interpret_codeblock(
                            self.user_functions[code_line[0]]["CODE"],
                            parameters=new_parameters,
                            scope="local",
                        )
                else:
                    raise NotImplementedError()
        if scope == "local":
            self.local_variables.pop(-1)

    def run(self):
        self._interpret_codeblock(
            self.script["CODE"], parameters=dict(), scope="global"
        )


if __name__ == "__main__":
    with open("Beispielcode.baeng", "rt") as fh:
        script = json.load(fh)

    Baeng(script).run()
