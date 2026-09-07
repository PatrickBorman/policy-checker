import io_utils as io
import timeit
import random
import os
import specification as sp
import re

# Set random seed for repeatability
# random.seed(1000)

output_folder = "outputs/"
case_study_name = ""
generation_method = "interpolation"
n_multivarbias = 5
goodness_measure = ""
goodness_update_required = False
search_method = "bfs"
refinement_method = generation_method + ("-" + search_method if search_method != "" else "") + ("-" + goodness_measure if goodness_measure != "" else "")
exp_number = "tacas20_duplicatecheck"
limit_fairness = -1 # Max fairness conditions allowed in the experiment. -1 if unlimited
# include_parent_unreal_core_check = True
include_parent_unreal_core_check = False

# Decide whether the search should return initial conditions, invariants, and/or fairness conditions
# By default, they are all True
search_initials = True
search_invariants = True
search_fairness = True

# Whether to use all guarantees or unrealizable core
use_all_gars = False

# Whether to minimize the specification
minimize_spec = True

# Whether to only use influential output variables
use_influential = True

timeout = 600 # 10 minutes
repair_limit = -1

# This is a reference to the original specification file
specfile = ""
datafile = os.path.join(output_folder, case_study_name + "_interpolation" + "_nodes.csv")
statsfile = os.path.join(output_folder, case_study_name + "_interpolation" + "_stats.csv")
checkpointfile = os.path.join(output_folder, case_study_name + "_" + refinement_method + "_exp" + str(exp_number) + "_checkpoint.csv")
satfile = os.path.join(output_folder, case_study_name + "_" + refinement_method + "_exp" + str(exp_number) + "_sat.csv")
weaknessfile = os.path.join(output_folder, case_study_name + "_" + refinement_method + "_exp" + str(exp_number) + "_weakness.csv")
wellsepfile = os.path.join(output_folder, case_study_name + "_" + refinement_method + "_exp" + str(exp_number) + "_wellsep.csv")
equivclassesfile = os.path.join(output_folder, case_study_name + "_" + refinement_method + "_exp" + str(exp_number) + "_equivclasses.csv")
distancesfile = os.path.join(output_folder, case_study_name + "_" + refinement_method + "_exp" + str(exp_number) + "_distances.csv")
cstimesfile = os.path.join(output_folder, case_study_name + "_" + refinement_method + "_exp" + str(exp_number) + "_cstimes.csv")
uniquesolsfile = os.path.join(output_folder, case_study_name + "_" + refinement_method + "_exp" + str(exp_number) + "_uniquesols.csv")

if case_study_name != "":
    spec = sp.read_file(specfile)
    spec = sp.interpolation_spec(spec)

    inputVarsList = io.extractInputVariablesFromFile(spec)
    outputVarsList = io.extractOutputVariablesFromFile(spec)
    varsList = inputVarsList + outputVarsList
    initialGR1Units = io.extractAssumptionList(spec)
    guaranteesList = io.extractGuaranteesList(spec)

counterstrategies = []

start_time = timeit.default_timer()
elapsed_time = 0

def configure(
        spectra_file,
        repair_limit_in=-1,
        timeout_in=600,
        output_folder="outputs/",
        use_all_gars_in = False,
        minimize_spec_in = True,
        use_influential_in = True,
        debug=False,
        show_args=True):
    
    global specfile
    global datafile
    global checkpointfile
    global satfile
    global weaknessfile
    global wellsepfile
    global statsfile
    global equivclassesfile
    global distancesfile
    global cstimesfile
    global uniquesolsfile

    global statsfile

    global inputVarsList
    global outputVarsList
    global varsList
    global initialGR1Units
    global guaranteesList

    global use_all_gars
    global minimize_spec
    global use_influential

    global timeout
    global repair_limit
    global start_time
    global elapsed_time
    
    use_all_gars = use_all_gars_in
    minimize_spec = minimize_spec_in
    use_influential = use_influential_in
    timeout = timeout_in
    repair_limit = repair_limit_in

    if show_args:
        print()
        print("=== ARGS ===")
        print("ALL GARS:", use_all_gars)
        print("MINIMIZE SPEC:", minimize_spec)
        print("USE INFLUENTIAL:", use_influential)
        print("TIMEOUT:", timeout)
        print("REPAIR LIMIT:", repair_limit)
        print()

    specfile = spectra_file
    case_study_name = os.path.splitext(os.path.basename(specfile))[0]

    datafile = os.path.join(output_folder, case_study_name + "_interpolation" + "_nodes.csv")
    statsfile = os.path.join(output_folder, case_study_name + "_interpolation" + "_stats.csv")
    checkpointfile = os.path.join(output_folder, case_study_name + "_" + refinement_method + "_exp" + str(exp_number) + "_checkpoint.csv")
    satfile = os.path.join(output_folder, case_study_name + "_" + refinement_method + "_exp" + str(exp_number) + "_sat.csv")
    weaknessfile = os.path.join(output_folder, case_study_name + "_" + refinement_method + "_exp" + str(exp_number) + "_weakness.csv")
    wellsepfile = os.path.join(output_folder, case_study_name + "_" + refinement_method + "_exp" + str(exp_number) + "_wellsep.csv")
    equivclassesfile = os.path.join(output_folder, case_study_name + "_" + refinement_method + "_exp" + str(exp_number) + "_equivclasses.csv")
    distancesfile = os.path.join(output_folder, case_study_name + "_" + refinement_method + "_exp" + str(exp_number) + "_distances.csv")
    cstimesfile = os.path.join(output_folder, case_study_name + "_" + refinement_method + "_exp" + str(exp_number) + "_cstimes.csv")
    uniquesolsfile = os.path.join(output_folder, case_study_name + "_" + refinement_method + "_exp" + str(exp_number) + "_uniquesols.csv")


    spec = sp.read_file(specfile)
    spec = sp.interpolation_spec(spec)

    inputVarsList = io.extractInputVariablesFromFile(spec)
    outputVarsList = io.extractOutputVariablesFromFile(spec)
    varsList = inputVarsList + outputVarsList
    initialGR1Units = io.extractAssumptionList(spec)
    guaranteesList = io.extractGuaranteesList(spec)

    if debug:
        print("+++++++++++ " + case_study_name)
        print("=== INPUT VARS ===")
        for var in inputVarsList:
            print(var)
        print()
        print("=== OUTPUT VARS ===")
        for var in outputVarsList:
            print(var)
        print()
        print("=== ASSUMPTIONS ===")
        for asm in initialGR1Units:
            print(asm)
        print()
        print("=== GUARANTEES ===")
        for gar in guaranteesList:
            print(gar)
        print()

    start_time = timeit.default_timer()
    elapsed_time = 0

def reset_start_time():
    global start_time
    start_time = timeit.default_timer()

def get_elapsed_time():
    global elapsed_time
    elapsed_time = timeit.default_timer() - start_time
    return elapsed_time