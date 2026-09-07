import re
import specification as sp
import experiment_properties as exp
from counterstrategy import CounterstrategyState, Counterstrategy

import jpype
import jpype.imports
from jpype.types import *

EXTRA_TIME = 60

jpype.startJVM(classpath=["spectra/dependencies/*", "spectra/SpectraTool.jar"])
SpectraTool = jpype.JClass('tau.smlab.syntech.Spectra.cli.SpectraTool')
print()

def check_realizibility(spectra_file_path):
    remaining_time = int(exp.timeout - exp.elapsed_time + EXTRA_TIME)
    return SpectraTool.checkRealizability(spectra_file_path, remaining_time)

def check_satisfiability(spectra_file_path):
    return SpectraTool.checkSatisfiability(spectra_file_path)

def check_well_separation(spectra_file_path):
    return SpectraTool.checkWellSeparation(spectra_file_path)

def check_y_sat(spectra_file_path):
    return SpectraTool.checkYSatisfiability(spectra_file_path)

fairness_pattern = re.compile(r"(GF|alwEv)\s*\(")
invariant_pattern = re.compile(r"(G|alw)\s*\(")

def compute_unrealizable_core(spectra_file_path):
    output = str(SpectraTool.computeUnrealizableCore(spectra_file_path))
    # print(output)
    core_found = re.compile("< ([^>]*) >").search(output)
    if not core_found:
        return None
    spec = sp.read_file(spectra_file_path)
    spec = [re.sub(r'\s', '', line) for line in spec]

    line_nums = []

    for i in range(len(spec)):
        if "guarantee" in spec[i] \
        and not fairness_pattern.match(spec[i+1]) \
        and not invariant_pattern.match(spec[i+1]):
            line_nums.append(i+1)
    

    line_nums = line_nums + [int(x) for x in core_found.group(1).split(" ")]
    line_nums = list(set(line_nums))
    # line_nums = [54, 56, 58, 67, 71]
    # print("LINE NUMS: ", line_nums)

    uc = [spec[line] for line in line_nums]
    uc = sp.unspectra(uc)
    return uc

def generate_counterstrategy(spectra_file_path):

    remaining_time = int(exp.timeout - exp.elapsed_time + EXTRA_TIME)
    output = str(SpectraTool.generateCounterStrategy(spectra_file_path, exp.minimize_spec, remaining_time))
    # print(output)
    return parse_counterstrategy(output.replace("\\t", ""))

def parse_counterstrategy(text):
    state_pattern = re.compile(r"(Initial )?(Dead )?State (\w+) <(.*?)>\s+With (?:no )?successors(?: : |.)(.*)(?:\n|$)")
    assignment_pattern = re.compile(r"(\w+):(\w+)")

    state_matches = re.finditer(state_pattern, text)
    states = dict()
    for match in state_matches:
        is_initial = match.group(1) != None
        is_dead = match.group(2) != None
        state_name = match.group(3)
        vars = dict(re.findall(assignment_pattern,  match.group(4)))
        inputs = dict()
        for x in exp.inputVarsList:
            inputs[x] = True if vars[x] == "true" else False
        outputs = dict()
        for y in exp.outputVarsList:
            if y in vars:
                outputs[y] = True if vars[y] == "true" else False
        successors = []
        if not match.group(5) == '':
            successors = match.group(5).split(", ")

        state = CounterstrategyState(state_name, inputs, outputs, successors, is_initial, is_dead)
        states[state.name] = state

    return Counterstrategy(states, use_influential=exp.use_influential)

def shutdown():
    SpectraTool.shutdown()
    jpype.shutdownJVM()