#!/usr/bin/env python3

import sys
import json
from typing import Literal
import numpy as np
import wave
import re
from scipy.io import wavfile
from itertools import cycle


class ImpulseResponse:
    """
    This class contains a list which holds individual samples, as well as
    duration and sample frequency of an impulse response.

    Samples can be accessed through their index.
    """

    def __init__(self, fs: int, duration: int | float):
        """
        Initializes an "empty" impulse response, filled with zero values.
        Set parameters are fixed at initialisation.

        Parameters
        ----------
        fs : int
            Sample frequency of the impulse response measured in Hz
        duration : int | float
            Duration of the impulse response at the given sample frequency, measured in seconds
        """

        self.data = np.zeros(int(fs * duration), dtype=np.float32)
        self.fs = fs
        self.duration = duration

    def __getitem__(self, index: int) -> np.float32:
        """
        Reads a sample value from the impulse response.

        Parameters
        ----------
        index : int
            Sample index to be accessed

        Returns
        -------
        out : np.float32
            Sample value of the impulse response at the selected index
        """

        return self.data[index]

    def __setitem__(self, index: int, value: float):
        """
        Changes a sample value of the impulse response.

        Parameters
        ----------
        index : int
            Sample index to be accessed
        value : float
            Value written to the selected sample
        """

        self.data[index] = value

    def to_numpy(self) -> np.ndarray:
        """
        Export the impulse response as a numpy ndarray, containing all sample values.

        Returns
        -------
        out : (N, ) np.ndarray
            Sample values in a ndarray with the earliest sample at [0] and the latest at [N-1]
        """

        return self.data

    def export_wav_16bit(self, path: str):
        """
        Export the impulse response as 16-bit PCM WAV.

        Parameters
        ----------
        path : str
            Output file path
        """

        # TODO: check/handle data out of range [-1, 1] (np.clip?)

        # Scale float32 [-1.0, 1.0] to int16 [-32768, 32767]
        pcm16 = (self.data * 32767).astype(np.int16)

        with wave.open(path, "wb") as w:
            # 1 channel - mono
            w.setnchannels(1)
            # 2 bytes per sample
            w.setsampwidth(2)
            w.setframerate(self.fs)
            w.writeframes(pcm16.tobytes())


class Baeng:
    """
    Interpreter class for the BAENG programming language
    """

    def __init__(self, script: dict):
        """
        Prepares an instance of Baeng to execute the given script

        Parameters
        ----------
        script : dict
            A dictionary compatible with BAENG code, containing the program
        """

        self.script = script

        # init variables
        self.global_vars = dict()
        self.local_variables = [{}]

        # init Impulse Response
        self.IR = ImpulseResponse(self.script["IR"][0], self.script["IR"][1])
        self.SAMPLEPOS = 0
        # self.possible_sample_positions = cycle(list(range(0, self.IR.fs * self.IR.duration - 1)))

        # reading user_functions
        self.user_functions = script.copy()
        self.user_functions.pop("IR")
        self.user_functions.pop("CODE")

        # TODO: make constant attribute
        # dict for mapping baeng code to operators
        self.operators = {
            "if": self._if_op,
            "while": self._while_op,
            "define": self._define_op,
            "setSample": self._set_sample_op,
            "readSample": self._read_sample_op,
            "export": self._export_op,
            "print": self._print_op
        }

    def _if_op(self, condition, code_block, scope):
        """
        Evaluates the condition and executes the codeblock if True

        Parameters
        ----------
        condition : list | string | int | float
            evaluated by bool(self._fetch_parameter)
        code_block : list
            code to be executed if condition is True
        scope : Literal["global", "local", "stay_local"]
            current scope when calling "if"
        """

        if scope == "local":
            # when inside function, no deeper scope layer should be generated
            scope = "stay_local"

        if self._fetch_parameter(condition, scope=scope):
            # interpret code block if condition is True
            self._interpret_codeblock(code_block, parameters={}, scope=scope)

    def _while_op(self, condition, code_block, scope):
        """
        Evaluates the condition and repeatedly executes the codeblock
        until the condition is False

        Parameters
        ----------
        condition : list | string | int | float
            evaluated by bool(self._fetch_parameter)
        code_block : list
            code to be executed while condition is True
        scope : Literal["global", "local", "stay_local"]
            current scope when calling "while"
        """

        if scope == "local":
            # when inside function, no deeper scope layer should be generated
            scope = "stay_local"

        while self._fetch_parameter(condition, scope=scope):
            # repeat the code block while condition is True
            self._interpret_codeblock(code_block, parameters={}, scope=scope)

    def _define_op(self, name, value, scope):
        """
        Set new variables or change the value of existing variables

        Parameters
        ----------
        name : str
            unique name of the variable to be used in expressions
        value : Any
            new value written to the variable
        """

        # evaluate expression to value
        evaluated_value = self._fetch_parameter(value, scope=scope)

        # TODO: remain global if variable already in global
        if scope == "local":
            # add variable to local variables of the deepest scope
            self.local_variables[-1].update({name: evaluated_value})

        elif scope == "stay_local":
            if self.local_variables:
                self.local_variables[-1][name] = evaluated_value
            else:
                self.global_vars[name] = evaluated_value

        elif scope == "global":
            # add variable to the global variables
            self.global_vars.update({name: evaluated_value})

    def _set_sample_op(self, key, value, scope):
        """
        Write a value to a specific sample of the impulse response

        Parameters
        ----------
        key : list | string | int | float
            sample index derived from evaluating key with self._fetch_parameter
        value : float
            new value written at the index (key) of the impulse response
        scope : Literal["global", "local", "stay_local"]
            current scope when calling "setSample"
        """

        # TODO: fix error if index is float (e.g. 1.0)
        # evaluate expression to get index
        index = self._fetch_parameter(key, scope=scope)

        # evaluate expression to get value and write it to the IR at the index
        self.IR[index] = self._fetch_parameter(value, scope=scope)

    def _read_sample_op(self, key, scope) -> np.float32:
        """
        Read the value of a specific sample of the impulse response

        Parameters
        ----------
        key : list | string | int | float
            sample index derived from evaluating key with self._fetch_parameter
        scope : Literal["global", "local", "stay_local"]
            current scope when calling "readSample"

        Returns
        -------
        out : np.float32
            Sample value of the impulse response at the selected key
        """

        # TODO: fix error if index is float (e.g. 1.0)
        # evaluate expression to get index
        index = self._fetch_parameter(key, scope=scope)

        # return sample value at selected index
        value = self.IR[index]
        return value

    def _export_op(self, filepath, scope):
        """
        Exports current IR to a given filename

        Parameters
        ----------
        filepath: str
            The file path to store the IR to, ends with .wav
        """

        self.IR.export_wav_16bit(filepath)

    def _print_op(self, string, scope):
        """
        Prints the given string to the console

        Parameters
        ----------
        string: str
            The string to be printed
        """

        # TODO: evaluate string
        print(string)

    def _eval_string(self, string):
        """
        Evaluates string as python expression with global variables and
        local variables from the deepest scope.
        Global variables are prioritized over local ones.

        Parameters
        ----------
        string : str
            Expression to be evaluated, containing local and global variables

        Returns
        -------
        out : Any
            The value of the given expression
        """

        # assemble dict of local variables from the deepest scope and global variables
        all_variables = self.local_variables[-1].copy()
        all_variables.update(
            self.global_vars
        )  # global variables overwrite local duplicates

        # TODO: add np random variable
        # add SAMPLEPOS and IR as variables
        all_variables.update({"SAMPLEPOS": self.SAMPLEPOS, "IR": self.IR})

        # return evaluated expression
        out = eval(string, {}, all_variables)
        return out

    def _fetch_parameter(self, obj, scope):
        """
        Evaluate any object and return its value

        Parameters
        ----------
        obj : list | string | int | float
            The object containing a command (list, e.g. readSample), expression (string)
            or number to be interpreted.
        scope : Literal["global", "local", "stay_local"]
            current scope when fetching the parameter

        Returns
        -------
        out : Any
            The value of the given object
        """

        if type(obj) is list:
            # LIST: execute the associated operator
            return self.operators[obj[0]](*obj[1:], scope=scope)

        elif type(obj) is str:
            # STR: evaluate the string as a python expression
            return self._eval_string(obj)

        elif type(obj) is int or type(obj) is float:
            # INT | FLOAT: return the object directly
            return obj

        else:
            # unknown object type
            raise TypeError

    def _interpret_codeblock(
        self,
        code_block: list,
        parameters: dict,
        scope: Literal["global", "local", "stay_local"],
    ):
        """
        Execute a given code block line by line

        Parameters
        ----------
        code_block : list
            A list compatible with BAENG code, containing code lines
        parameters : dict
            Parameters passed as local variables.
            Used for function calls, else empty dict.
        scope : Literal["global", "local", "stay_local"]
            Scope of the executed code block.

            - "global": new variables in the codeblock get added to global variables
            - "local": the codeblock gets a new local scope.
                New variables in the codeblock get added to the new local scope.
            - "stay_local": no new local scope is added.
                New variables in the codeblock get added to the current local scope.
        """

        if scope == "local":
            # add new local scope to local_variables list
            self.local_variables.append(parameters)

        for code_line in code_block:
            # iterate over every line of baeng code
            try:
                # try to interpret code line as operator
                self.operators[code_line[0]](*code_line[1:], scope=scope)

            except KeyError:
                # if code line is no operator try to interpret as user_function
                if code_line[0] in self.user_functions:
                    # code line is a user_function

                    # evaluate every given parameter of the function call
                    parameter_names = self.user_functions[code_line[0]]["PARAMS"]
                    parameter_values = []
                    for parameter in code_line[1]:
                        parameter_values.append(
                            self._fetch_parameter(parameter, scope=scope)
                        )

                    # pack parameter names and values to dict
                    new_parameters = dict(zip(parameter_names, parameter_values))

                    for sample_position in range(self.IR.fs * self.IR.duration):
                        # iterate over each sample

                        # safe current sample_position in attributes
                        self.SAMPLEPOS = sample_position

                        # execute user_function as code with given parameters as local variables
                        self._interpret_codeblock(
                            self.user_functions[code_line[0]]["CODE"],
                            parameters=new_parameters,
                            scope="local",
                        )
                else:
                    # unknown command in current code line
                    raise NotImplementedError()

        if scope == "local":
            # remove the added local scope from the local variables list
            self.local_variables.pop(-1)

    def run(self):
        """
        Execute the given script
        """

        self._interpret_codeblock(
            self.script["CODE"], parameters=dict(), scope="global"
        )

        # export.wav at the end of code
        self.IR.export_wav_16bit(path=self.script["IR"][2])


if __name__ == "__main__":
    # check if file path is given as an argument
    if len(sys.argv) < 2:
        raise SystemExit("Missing path: <filename.baeng>")

    # fetch file path
    path = sys.argv[1]

    # check if file is .baeng
    if not path.endswith(".baeng"):
        raise SystemExit("File is not a .baeng")

    try:
        # load script from file
        with open(path, "rt") as fh:
            script = json.load(fh)
    except FileNotFoundError:
        raise SystemExit(f"File not found: {path}")

    Baeng(script).run()
