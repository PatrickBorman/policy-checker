import experiment_properties as exp
import interpolation
# import alur, varbias
import timeit
import uuid, re, os, ast
# import ref_utils.ratsy_utils as r
# import model_checking as mc
# from Weakness.src.weakness import computeD1_probe, computeD2_probe, Weakness
import numpy as np
import spectra_utils as spectra
import specification as sp


class RefinementNode:

    def __init__(self, gr1_units=[], parent_id=None):
        self.id = uuid.uuid4()
        self.temp_spec_filename = "temp/" + str(self.id) + ".spectra"

        self.parent_id = parent_id
        self.num_descendant_refinements = 0

        # Data fields (can be read from/written to a file)
        self.gr1_units = gr1_units # List of all units/conjuncts in this refinement
        self.length = len(gr1_units)

        # Weakness
        self.weakness = None
        self.weakness_num_automata = None
        self.weakness_numstates_automata = None
        self.weakness_times_automata = None
        self.weakness_is_automaton_strongly_connected = None

        self.is_y_sat = None
        self.is_realizable = None
        self.is_satisfiable = None
        self.is_well_separated = None
        self.goodness = None # This field contains the goodness measure to use in a heuristic-based search.
                             # The higher the better

        # Stats fields (can be read from/written to a file)
        self.timestamp = exp.get_elapsed_time()
        self.timestamp_realizability_check = None
        self.time_counterstrategy = None
        self.counterstrategy_num_states = None
        self.time_y_sat_check = None
        self.time_realizability_check = None
        self.time_satisfiability_check = None
        self.time_well_separation_check = None
        # Total time to model check all children of this node.
        self.time_refine = None
        self.time_weakness = None
        self.time_goodness = None
        # Time for generation method (interpolation or multivarbias or other)
        self.time_generation_method = None
        self.time_interpolation = None
        # Time for computing number of observed counterstrategies eliminated

        self.counterstrategy = None
        self.unreal_core = None

        self.interpolant_computed = False
        self.interpolant = None
        self.interpolant_is_false = None
        self.no_interpolant = None
        self.non_state_separable = None
        self.num_state_components = None
        self.num_non_io_separable = None
        
        # Used to check whether two nodes contain the same refinement
        self.unique_refinement = sorted(self.gr1_units)

        self.notes = ""

    # Methods to load node data from experiment file
    __re_first_cap = re.compile('(.)([A-Z][a-z]+)')
    __re_all_cap = re.compile('([a-z0-9])([A-Z])')

    def __convertCamelToSnakeCase(self, name):
        """Converts names like FieldName to field_name"""
        s1 = self.__re_first_cap.sub(r'\1_\2', name)
        return self.__re_all_cap.sub(r'\1_\2', s1).lower()

    def __convertSnakeToCamelCase(self, name):
        """Converts names like field_name to FieldName"""
        components = name.split('_')
        # We capitalize the first letter of each component except the first one
        # with the 'title' method and join them together.
        return ''.join(x.title() for x in components)

    def loadDataFieldsFromList(self, fieldnames, fieldvalues):
        """Loads data fields from a list
        fieldnames: a list of field names, as strings
        fieldvalues: a list of field values, as strings
        """
        fieldnames = [self.__convertCamelToSnakeCase(x) for x in fieldnames]
        for i,field in enumerate(fieldnames):
            if fieldvalues[i] == "N/A":
                setattr(self, field, None)
            elif field == "goodness" and exp.goodness_measure == "weakness":
                inf = np.inf
                eval_field = eval(fieldvalues[i])
                self.goodness = Weakness(eval_field[0], eval_field[1], eval_field[2], eval_field[3])
                self.weakness = self.goodness
            elif field == "refinement":
                self.gr1_units = eval(fieldvalues[i])
            else:
                try:
                    # literal_eval identifies Boolean and numeric types
                    setattr(self,field,ast.literal_eval(fieldvalues[i]))
                except Exception:
                    setattr(self, field, fieldvalues[i])

    def __readNotes(self):
        """Checks if there is a notefile regarding the current node. If so, returns its content"""
        if os.path.isfile(self.getNotesFileId()):
            with open(self.getNotesFileId()) as notefile:
                return " ".join(notefile.readlines())
        else:
            return ""

    def writeNotes(self, string):
        with open(self.getNotesFileId(), "a") as notesfile:
            notesfile.write(string + ";")


    def saveRefinementData(self, csv_writer, fields):
        """Saves the data contents of the 'fields' fields into datafile as a semicolon-separated string"""

        field_values = []
        fields = [self.__convertCamelToSnakeCase(x) for x in fields]
        for field in fields:
            if field == "elapsed_time":
                field_value = exp.get_elapsed_time()
            elif field == "refinement":
                field_value = self.unique_refinement
            elif field == "parent":
                field_value = self.parent_id
            elif field == "num_children":
                field_value = self.num_descendant_refinements
            elif field == "is_solution":
                if self.is_realizable == True and self.is_satisfiable == True:
                    field_value = True
                elif self.is_realizable == False or self.is_satisfiable == False:
                    field_value = False
                else:
                    field_value = "N/A"
            else:
                field_value = getattr(self, field)
            if field_value is not None:
                field_values.append(str(field_value))
            else:
                field_values.append("N/A")

        csv_writer.writerow(field_values)

    #==========================================================================
    # Methods to deal .spectra files

    def __setTempSpecFileName(self, filename):
        self.temp_spec_filename = filename

    def __getTempSpecFileName(self):
        return self.temp_spec_filename

    def __generateSpecFile(self):
        if not os.path.isfile(self.__getTempSpecFileName()):
            specification = sp.read_file(exp.specfile)
            specification = sp.spectra_format(specification)
            assumptions = sp.spectra_format(self.gr1_units)
            for asm in assumptions:
                specification.append("\nassumption\n")
                specification.append("\t" + asm + ";\n")
            sp.write_file(specification, self.__getTempSpecFileName())

    def __minimizeSpecFile(self):
        if not os.path.isfile(self.__getTempSpecFileName()):
            raise Exception("Generate spec file before minimizing")
        if not self.unreal_core:
            raise Exception("Compute unrealizable core before minimizing")

        spec = sp.read_file(self.__getTempSpecFileName())
        self.deleteTempSpecFile()
        self.__setTempSpecFileName("temp/" + str(self.id) + "_min.spectra")
        new_spec = []
        i = 0
        while i < len(spec):
            if "guarantee" in spec[i]:
                i += 2
                continue
            new_spec.append(spec[i])
            i += 1

        for gar in sp.spectra_format(self.unreal_core):
            new_spec.append("guarantee\n\t" + gar + ";\n")

        sp.write_file(new_spec, self.__getTempSpecFileName())
        
    def deleteTempSpecFile(self):
        if os.path.isfile(self.__getTempSpecFileName()):
            os.remove(self.__getTempSpecFileName())

    def getNotesFileId(self):
        return "temp/" + str(self.id) + "_notes.txt"

    #================================================================================================
    # Methods to return the refinement in various formats
    def getInitialAssumptionsAndRefinement(self):
        return " & ".join(exp.initialGR1Units) + ((" & " + " & ".join(self.gr1_units)) if not not self.gr1_units else "")

    def getRefinementAsFormula(self):
        return " & ".join(self.gr1_units)

    def getInitialAssumptionsNoFairness(self):
        return " & ".join([x for x in exp.initialGR1Units if not x.startswith("G(F(")])
    
    def checkRealizability(self, filename):
        return spectra.check_realizibility(filename)

    #===============================================================================================
    # Methods related to assumptions refinement
    def isRealizable(self):
        if self.is_realizable is not None:
            return self.is_realizable
        self.__generateSpecFile()
        realizability_check_start = timeit.default_timer()
        self.is_realizable = self.checkRealizability(self.__getTempSpecFileName())
        self.time_realizability_check = timeit.default_timer() - realizability_check_start
        self.timestamp_realizability_check = exp.get_elapsed_time()
        return self.is_realizable

    def isSatisfiable(self):
        if self.is_satisfiable is not None:
            return self.is_satisfiable
        time_satisfiability_check_start = timeit.default_timer()
        self.is_satisfiable = spectra.check_satisfiability(self.__getTempSpecFileName())
        self.time_satisfiability_check = timeit.default_timer() - time_satisfiability_check_start
        return self.is_satisfiable
    
    def isWellSeparated(self):
        if self.is_well_separated is not None:
            return self.is_well_separated
        time_well_separation_check_start = timeit.default_timer()
        self.is_well_separated = spectra.check_well_separation(self.__getTempSpecFileName())
        self.time_well_separation_check = timeit.default_timer() - time_well_separation_check_start
        return self.is_well_separated

    def isYSat(self):
        if self.is_y_sat is not None:
            return self.is_y_sat
        self.__generateSpecFile()
        time_y_sat_check_start = timeit.default_timer()
        self.is_y_sat = spectra.check_y_sat(self.__getTempSpecFileName())
        self.time_y_sat_check = timeit.default_timer() - time_y_sat_check_start
        return self.is_y_sat
    
    def getCounterstrategy(self):
        """Returns a counterstrategy object"""

        if self.counterstrategy is not None:
            return self.counterstrategy
        if not self.isRealizable():
            counterstrategy_start = timeit.default_timer()
            self.counterstrategy = spectra.generate_counterstrategy(self.__getTempSpecFileName())
            self.time_counterstrategy = timeit.default_timer() - counterstrategy_start
            self.counterstrategy_num_states = self.counterstrategy.num_states
            return self.counterstrategy
        return None

    def getUnrealizableCore(self):
        """Gets an unrealizable core for the current node"""
        if self.unreal_core is None:
            self.unreal_core = spectra.compute_unrealizable_core(self.__getTempSpecFileName())
        return self.unreal_core

    def refine(self):
        """Produces a list of Refinement objects based on the selected refinement method"""

        refinements = []

        if exp.search_method == "bfs":
            if not exp.use_all_gars:
                self.getUnrealizableCore()
            if exp.minimize_spec:
                self.__minimizeSpecFile()
            self.getCounterstrategy()
            candidate_refs = self.generateAlternativeRefinements()
            time_refine_start = timeit.default_timer()
            for candidate_ref in candidate_refs:
                # Append the refinement generated by just concatenating the new assumption
                refinements.append(self.__concatenateAssumption(candidate_ref))
            self.time_refine = timeit.default_timer() - time_refine_start
        self.num_descendant_refinements = len(refinements)
        return refinements

    def __concatenateAssumption(self, candidate_ref):
        """Generate a new refinement by just concatenating candidate_ref to self. Keep the bipartite graph consistent"""
        assumptions = self.gr1_units + [candidate_ref]
        return RefinementNode(assumptions, self.id)

    def generateAlternativeRefinements(self):
        time_generation_method_start = timeit.default_timer()
        refinements = []
        if exp.generation_method == "interpolation":
            guarantees = exp.guaranteesList if exp.use_all_gars else self.unreal_core
            refinements = interpolation.GenerateAlternativeRefinements(str(self.id), self.counterstrategy, exp.initialGR1Units + self.gr1_units, guarantees, exp.inputVarsList, exp.outputVarsList, self)

        self.time_generation_method = timeit.default_timer() - time_generation_method_start
        return refinements

    #================================================================================================
    # Methods for computing quantitative heuristics

    def computeWeakness(self):
        start_time_weakness = timeit.default_timer()
        if self.weakness is None:
            self.weakness, self.weakness_num_automata, self.weakness_numstates_automata, self.weakness_times_automata, self.weakness_is_automaton_strongly_connected = computeWeakness_probe(self.getRefinementAsFormula(),exp.varsList)
        self.time_weakness = timeit.default_timer() - start_time_weakness
        return self.weakness

    def computeGoodness(self):
        start_time_goodness = timeit.default_timer()
        if exp.goodness_measure == "weakness":
            self.goodness = self.computeWeakness()
        self.time_goodness = timeit.default_timer() - start_time_goodness

    # The higher goodness the better the refinement.
    # In min-heap implementations of priority queues, the lower-ranked nodes are the first to be popped.
    # So the higher the goodness the lower the rank of a refinement
    def __le__(self, other):
        if self.goodness is not None and other.goodness is not None:
            return (self.goodness >= other.goodness)
        else:
            raise Exception("Refinements compared despite goodness not computed")

    def __lt__(self, other):
        if self.goodness is not None and other.goodness is not None:
            return (self.goodness > other.goodness)
        else:
            raise Exception("Refinements compared despite goodness not computed")

    def __ge__(self, other):
        return not self < other

    def __gt__(self, other):
        return not self <= other

    def __eq__(self, other):
        if self.goodness is not None and other.goodness is not None:
            return (self.goodness == other.goodness)
        else:
            raise Exception("Refinements compared despite goodness not computed")
