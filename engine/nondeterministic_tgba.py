import automaton
import subprocess
import shlex
from definitions import ROOT_DIR
import re
import tarjan
import io_utils as io
import dd

## This hack is to circumvent Python importing the dd module defined inside Ratsy.
# Here I need to import Python's standard dd module
# def import_non_local(name, custom_name=None):
#     import imp

#     custom_name = custom_name or name

#     f, pathname, desc = imp.find_module(name, ["/usr/local/lib/python2.7/dist-packages"])
#     module = imp.load_module(custom_name, f, pathname, desc)

#     return module
# dd = import_non_local('dd')
##

class NondeterministcTGBA(automaton.Automaton):
    """Calls Spot to create a Transition-based Generalized Buchi Automaton.
    The Buchi acceptance condition consists of a set of transitions to be visited infinitely often,
    and more than one accepting transitions are possible"""

    def __init__(self,sourceType,**kwargs):
        """- sourceType can be 'ltl' or 'smv' or 'buchi_hoa'
            - If sourceType=='ltl' kwargs contains
                - an ltlFormula field with the LTL formula
                - a var_set field with the variables in the model
            - If sourceType=='smv' kwargs contains a file field with the .smv file containing the Kripke structure file (not implemented)
            - If sourceType=='tgba_hoa' kwargs contains (not implemented)
                - a hoa_file field with the HOA description of a TGBA
                - a var_set field with the variables in the model"""

        # Init graph structure
        self.numstates = 0  # Total number of states. States are numbered from 0 to numstates-1
        self.edges = []  # Each edge is a 5-tuple [id_src, label, id_dest, multiplicity, accepting_labels].
        # An edge may correspond to more than one transition, according to the logical expression in label.
        # multiplicity is the number of transitions it corresponds. It is redundant information
        self.init_states = []  # Ids of initial states
        self.states = [] # List of all State objects
        self.accepting_labels = 0  # Number of accepting edge sets
        self.edge_vars = []  # List of variables occurring in edge label formulae (subset of var_set)

        if sourceType=='ltl':
            self.ltlFormula = kwargs['ltlFormula']
            self.var_set = kwargs['var_set']

            self.reduced = True  # When reduced is true, use overflow avoidance trick
            self._LTL2TGBA(self.ltlFormula)


    def _LTL2TGBA(self,ltlFormula):
        """Converts a formula into a TGBA"""
        # shlex.split splits the string according to shell format
        # subprocess.PIPE is needed to pipe the standard output of ltl2tgba to the standard input of this Python script
        p = subprocess.Popen(shlex.split(ROOT_DIR + "/spot/build/bin/ltl2tgba --low \'" + ltlFormula + "\'"), 0, None, None, subprocess.PIPE)
        spot_out = p.stdout

        self._convertHOA2TGBA(spot_out)

        p.terminate()

    def _convertHOA2TGBA(self,hoa_stream):
        """Converts Spot's text description format of a BA into an edge-labelled graph"""
        # Regex patterns for file scanning
        re_initstates = re.compile(r"Start: (\d+)")
        re_numstates = re.compile(r"States: (\d+)")
        re_acceptance = re.compile(r"Acceptance: (\d+)( t)?")
        re_srcstate = re.compile(r"State: (\d+)( \{\d+\})?")
        re_edges = re.compile(r"\[(.+)\] (\d+)( \{\d+( \d+)*\})?")
        re_numbers = re.compile(r"([0-9]+)")

        linematch = re.match(re_numstates, hoa_stream.readline().decode('utf-8'))
        while linematch is None:
            linematch = re.match(re_numstates, hoa_stream.readline().decode('utf-8'))
        self.numstates = int(linematch.group(1))

        # Finds the initial state's id. Multiple starting states are denoted by multiple "Start: " lines
        linematch = re.match(re_initstates, hoa_stream.readline().decode('utf-8'))
        while linematch is None:
            linematch = re.match(re_initstates, hoa_stream.readline().decode('utf-8'))
        self.init_states.append(int(linematch.group(1)))
        # There may be more than one "Start: " lines. Read all of them before going to next step
        hoa_line = hoa_stream.readline().decode('utf-8')
        linematch = re.match(re_initstates, hoa_line)
        while linematch is not None:
            self.init_states.append(int(linematch.group(1)))
            hoa_line = hoa_stream.readline().decode('utf-8')
            linematch = re.match(re_initstates, hoa_line)

        # Gets the set of variables used in the HOA
        while(not hoa_line.startswith("AP:")):
            hoa_line = hoa_stream.readline().decode('utf-8')
        try:
            self.constrained_var_set = hoa_line[hoa_line.index("\"") + 1:-2].split("\" \"")
        except ValueError:
            # In case the formula is equivalent to FALSE, the formula is empty and the AP: line is "AP: 0".
            # In this case the index("\"") function above raises an exception, and the automaton is empty.
            self.constrained_var_set = self.var_set

        linematch = re.match(re_acceptance,hoa_stream.readline().decode('utf-8'))
        while linematch is None:
            linematch = re.match(re_acceptance,hoa_stream.readline().decode('utf-8'))
        self.accepting_labels = int(linematch.group(1))
        # This records whether the TGBA accepts any infinite run
        # This kind of automaton is called safety automaton
        if linematch.group(2) == " t":
            self.safety_automaton = True
        else:
            self.safety_automaton = False

        # Even if set to produce TGBAs, Spot sometimes produces state-based GBAs.
        # Checks whether the acceptance condition is state-based or transition-based
        inline = hoa_stream.readline().decode('utf-8')
        while not inline.startswith("properties: "):
            inline = hoa_stream.readline().decode('utf-8')
        if "state-acc" in inline:
            state_acceptance = True
        else:
            state_acceptance = False

        # Finds all the transitions
        inline = hoa_stream.readline().decode('utf-8')
        while inline != "":
            linematch = re.match(re_srcstate, inline)
            if linematch is not None:
                # cursrc contains the source state of each upcoming transition
                cursrc = int(linematch.group(1))

                # Even if set to produce TGBAs, Spot sometimes produces state-based GBAs.
                # The following code reads a state-based acceptance condition if present, and adds it to
                # all outgoing edges
                if state_acceptance == True:
                    if linematch.group(2) is not None:
                        accept_labels = linematch.group(2)[2:-1].split(" ")
                    else:
                        accept_labels = []
            else:
                # The current line is a transition from the latest observed cursrc
                linematch = re.match(re_edges, inline)
                if linematch is not None:
                    # Reformat edge formula so that it can be read by dd module
                    # Replace variable id with name and replace negation symbol
                    # formula = (re.sub(re_numbers,"var\g<1>",linematch.group(1))).replace("!","~")
                    formula = re_numbers.sub(lambda x: self.constrained_var_set[int(x.group())], linematch.group(1))
                    # Transition-based acceptance condition: parse if present
                    # Remove heading blank and curly brace and trailing curly brace,
                    # then split labels
                    if not state_acceptance:
                        if linematch.group(3) is not None:
                            accept_labels = linematch.group(3)[2:-1].split(" ")
                        else:
                            accept_labels = []

                    if self.reduced:
                        self.edges.append(
                            [cursrc, formula, int(linematch.group(2)), self._getEdgeReducedMultiplicity(formula), accept_labels])
                    else:
                        self.edges.append(
                            [cursrc, formula, int(linematch.group(2)), self._getEdgeMultiplicity(formula), accept_labels])

            inline = hoa_stream.readline().decode('utf-8')



    def _getEdgeMultiplicity(self, formula):
        """Returns the number of variable assignments satisfying the label formula in edge"""

        # Extract all variables in the formula. Take distinct entries only
        vars = list(set(re.findall(r"\w+", formula)))

        # Build a BDD object
        bdd = dd.BDD()
        [bdd.add_var(var) for var in vars]
        node = bdd.add_expr(formula)

        # BDD.sat_len gets the number of satisfying assignments for the BDD
        # The number is multiplied by a factor accounting for the unconstrained variables in the formula
        # ** is exponentiation
        return bdd.count(node) * 2 ** (len(self.var_set) - len(vars))

    def _getEdgeReducedMultiplicity(self, formula):
        """Computes the multiplicity of an edge by neglecting variables not appearing in the formula"""
        # Extract all variables in the formula. Take distinct entries only
        vars = list(set(re.findall(r"\w+", formula)))

        # Build a BDD object
        bdd = dd.BDD()
        [bdd.add_var(var) for var in vars]
        node = bdd.add_expr(formula)

        # BDD.sat_len gets the number of satisfying assignments for the BDD
        # The number is multiplied by a factor accounting for the unconstrained variables in the formula
        # ** is exponentiation
        return bdd.count(node) * 2 ** (len(self.constrained_var_set) - len(vars))

    def getAdjacencyListNoSinks(self):
        adjList = self.getAdjacencyList()
        no_sinks = False
        while not no_sinks:
            sink_states = []
            for state in adjList:
                if adjList[state] == []:
                    sink_states.append(state)

            if sink_states == []:
                no_sinks = True
            else:
                for sink_state in sink_states:
                    adjList.pop(sink_state)
                    for state in adjList:
                        adjList[state] = [x for x in adjList[state] if x != sink_state]
        return adjList

    def checkEmptiness(self):
        """Returns True if the automaton is empty, False otherwise."""

        # If there are no accepting labels and this is not an automaton that accepts
        # any path (safety automaton), the automaton is empty
        if self.accepting_labels==0 and not self.safety_automaton:
            return True

        # Compute SCCs in the automaton (excluding sink states, otherwise they appear as SCCs)
        sccs = tarjan.tarjan(self.getAdjacencyListNoSinks())

        # If there is at least one SCC, assuming the automaton
        # only contains states reachable from the initial state,
        # then it contains at least one infinite path.
        # Thus, if it is a safety automaton, it is not empty.
        if self.safety_automaton and sccs.__len__()>0:
            return False

        # This dictionary maps every SCC to the set of acceptance labels in that SCC
        scc_labels = dict()
        # Check all the accepting labels inside an SCC
        for scc in range(len(sccs)):
            scc_labels[scc] = set()
            for edge in self.edges:
                if edge[0] in sccs[scc] and edge[2] in sccs[scc]:
                    # This edge is inside the SCC. Add its labels to the labels of the SCC
                    scc_labels[scc] = scc_labels[scc].union(set(edge[4]))
            # We are assuming that Spot removes the unreachable SCCs.
            # All SCCs that are found in the TGBA returned by Spot are reachable by at least one initial state
            # So, if we find an SCC that contains all accepting labels, the automaton is not empty
            if len(scc_labels[scc])==self.accepting_labels:
                return False
        # No SCC has all labels, so the automaton must be empty
        return True



    def getHausdorffDimension(self):
        pass


# def testFormulaAutomaton(formula):
#     a = NondeterministcTGBA("ltl",ltlFormula=formula,var_set=io.getDistinctVariablesInFormula(formula))
#     print(a.checkEmptiness())


# def main():
#     a = NondeterministcTGBA("ltl",ltlFormula="G(a -> X(!b))",var_set=['a','b','c'])
#     #a = automatonFromRatFile("/home/dgc14/WeakestAssumptions/Weakness/tests/amba08.rat")
#     print "a.numstates: " + str(a.numstates)
#     print "a.edges: " + str(a.edges)
#     print "a.init_states: " + str(a.init_states)
#     print "a.accepting_labels: " + str(a.accepting_labels)
#     print "a.var_set" + str(a.var_set)
#     print "a.constrained_var_set" + str(a.constrained_var_set)
# #    print "a._getEdgeMultiplicity(a.edges[0][1]): " + str(a._getEdgeMultiplicity(a.edges[0][1]))
#     print "a.getAdjacencyList: " + str(a.getAdjacencyList())
#     print "a.getAdjacencyMatrix: "+str(a.getAdjacencyMatrix())
#     print "a.getHausdorffDimension: "+str(a.getHausdorffDimension())
#     print "a.checkEmptiness: "+str(a.checkEmptiness())

# if __name__=="__main__" :
    # testFormulaAutomaton("G((!Button | !Noise | !responded_1 | !responded_2 | XHeading) & (!Button | !Noise | !Obstacle | !responded_1 | responded_2 | !search | X(!Button | Heading | !Obstacle | !responded_1)) & F(responded_1 & !responded_1))")
