import itertools
import re
import shlex
import subprocess
import timeit
from definitions import ROOT_DIR
import dd
import numpy as np
import tarjan
from io import BytesIO

class Automaton:
    """Defines the Buchi automaton corresponding to an LTL formula"""

    def __init__(self,sourceType,**kwargs):
        """- sourceType can be 'ltl' or 'smv' or 'buchi_hoa'
           - If sourceType=='ltl' kwargs contains
                - an ltlFormula field with the LTL formula
                - a var_set field with the variables in the model
           - If sourceType=='smv' kwargs contains
                a file field with the .smv file containing the Kripke structure file
           - If sourceType=='buchi_hoa' kwargs contains
                - a hoa_file field with the HOA description of a Buchi automaton
                - a var_set field with the variables in the model
           - If sourceType=='manual', then the fields must be included manually"""

        # Init graph structure
        self.numstates = 0  # Total number of states. States are numbered from 0 to numstates-1
        self.edges = []  # Each edge is a quadruple [id_src, label, id_dest, multiplicity].
        # An edge may correspond to more than one transition, according to the logical expression in label.
        # multiplicity is the number of transitions it corresponds. It is redundant information
        self.init_states = []  # Ids of initial states
        self.accepting_states = []  # Ids of accepting states
        self.edge_vars = []  # List of variables occurring in edge label formulae (subset of var_set)

        self.sccs = [] # List of SCCs. Used to buffer the results of getSCCs()
        self.accepting_sccs_indices = [] # List of accepting SCCs. Used to buffer the results of getAcceptingSCCs()
        self.coreachable_sccs_indices = [] # List of co-reachable SCCs. Used to buffer the results of getCoReachableSCCs
        self.sccs_entropies = [] # List of entropies of each SCC. Used to buffer the results of getEntropy()
        self.is_strongly_connected = None # getHausdorffDimension decides whether the automaton is strongly connected
        self.sccs_maxentropy = [] # List of accepting SCCs with max entropy. Used to buffer the results of getHausdorffDimension()

        # TIME PROBE: Check time to generate automaton
        start = timeit.default_timer()

        # If the source is an LTL formula, read it and convert it to a Buchi automaton
        if sourceType == "ltl":
            self.ltlFormula = kwargs["ltlFormula"]
            self.var_set = kwargs["var_set"]  # Full set of variables of the model (includes unconstrained vars not appearing in ltlFormula)

            #self._getVarsFromFormula()
            self.reduced = True  # When reduced is true, use overflow avoidance trick
            self._LTL2Buchi(self.ltlFormula)

        elif sourceType == "buchi_hoa":
            self.hoa_file = kwargs["hoa_file"]

            #self._getVarsFromHOA()
            self.reduced = True

            if "var_set" in kwargs.keys():
                self.var_set = kwargs["var_set"]
            else:
                self.var_set = self._getVarsFromHOA()

            hoa_stream = open(self.hoa_file,"r")
            self._convertHOA2Automaton(hoa_stream)
            hoa_stream.close()

        # TIME PROBE STOP
        self.automaton_compute_time = timeit.default_timer() - start


    def _getVarsFromHOA(self):
        hoa_stream = open(self.hoa_file,"r")

        for line in hoa_stream.readlines():
            if line.startswith("AP:"):
                # Variables are listed in this line in quotes and separated by blanks
                # s[index("\"")+1:-2] deletes first and last quotes along with the prefix "AP: <n>", split takes care of the middle ones
                hoa_var_set = line[line.index("\"")+1:-2].split("\" \"")
                break

        hoa_stream.close()
        return hoa_var_set


    def _getVarsFromFormula(self):
        """Get the set of variables appearing in the LTL formula. Used in overflow avoidance tricks"""

        # candidateVars contains all alphanumeric substrings in formula.
        # Turned to set to eliminate duplicates
        candidateVars = list(set(re.findall(r"\w+", self.ltlFormula)))
        # Delete X operator from variables
        candidateVars = map(lambda x: x[1:] if x.startswith("X") else x,candidateVars)

        # Temporal operators must be removed
        if 'G' in candidateVars: candidateVars.remove('G')
        if 'X' in candidateVars: candidateVars.remove('X')
        if 'F' in candidateVars: candidateVars.remove('F')

        self.constrained_var_set = candidateVars


    def _LTL2Buchi(self,ltlFormula):
        """Calls the external tool Spot to compute the automaton corresponding to the LTL formula"""

        # shlex.split splits the string according to shell format
        # subprocess.PIPE is needed to pipe the standard output of ltl2tgba to the standard input of this Python script
        command = [ROOT_DIR + "spot/build/bin/ltl2tgba", "-B", "-S", "-D", "-f", ltlFormula]
        
        try:
            p = subprocess.run(command,0,None,None,subprocess.PIPE, timeout=20000)
            spot_out = BytesIO(p.stdout)

            self._convertHOA2Automaton(spot_out)
        except subprocess.TimeoutExpired:
            print("LTL2Buchi timed out.")

    def _convertHOA2Automaton(self, hoa_stream):
        """Converts Spot's text description format of a BA into an edge-labelled graph"""
        # Regex patterns for file scanning
        re_initstates = re.compile(r"Start: (\d+)")
        re_numstates = re.compile(r"States: (\d+)")
        re_srcstate = re.compile(r"State: (\d+)( \{\d+\})?")
        re_edges = re.compile(r"\[(.+)\] (\d+)")
        re_numbers = re.compile(r"([0-9]+)")

        linematch = re.match(re_numstates, hoa_stream.readline().decode('utf-8'))
        i = 1
        while linematch is None:
            i += 1
            linematch = re.match(re_numstates, hoa_stream.readline().decode('utf-8'))
        self.numstates = int(linematch.group(1))

        # Finds the initial state's id. We are assuming a single initial state (deterministic automaton)
        linematch = re.match(re_initstates, hoa_stream.readline().decode('utf-8'))
        while linematch is None:
            linematch = re.match(re_initstates, hoa_stream.readline().decode('utf-8'))
        self.init_states.append(int(linematch.group(1)))

        # Gets the set of variables used in the HOA
        hoa_line = hoa_stream.readline().decode('utf-8')
        while(not hoa_line.startswith("AP:")):
            hoa_line = hoa_stream.readline().decode('utf-8')
        try:
            self.constrained_var_set = hoa_line[hoa_line.index("\"") + 1:-2].split("\" \"")
        except ValueError:
            # In case the formula is equivalent to FALSE, the formula is empty and the AP: line is "AP: 0".
            # In this case the index("\"") function above raises an exception, and the automaton is empty.
            # In case the formula is TRUE, it is written 't' in HOA syntax and again the AP: line is "AP: 0"
            self.constrained_var_set = self.var_set

        # Finds all the transitions
        inline = hoa_stream.readline().decode('utf-8')
        #i = 1
        while inline != "":
            #print "spot_out transitions: Reading line "+str(i)
            #i += 1
            linematch = re.match(re_srcstate,inline)
            if linematch is not None:
                # cursrc contains the source state of each upcoming transition
                cursrc = int(linematch.group(1))
                if linematch.group(2) is not None:
                    # The "{x}" string is contained in the line, therefore it is an accepting state
                    self.accepting_states.append(cursrc)

            else:
                linematch = re.match(re_edges,inline)
                if linematch is not None:
                    # Reformat edge formula so that it can be read by dd module
                    # Replace variable id with name and replace negation symbol
                    #formula = (re.sub(re_numbers,"var\g<1>",linematch.group(1))).replace("!","~")
                    formula = re_numbers.sub(lambda x: self.constrained_var_set[int(x.group())],linematch.group(1))
                    formula = re.sub(r"\bt\b","TRUE",formula)
                    if self.reduced:
                        self.edges.append([cursrc, formula, int(linematch.group(2)), self._getEdgeReducedMultiplicity(formula)])
                    else:
                        self.edges.append([cursrc, formula, int(linematch.group(2)), self._getEdgeMultiplicity(formula)])

            inline = hoa_stream.readline().decode('utf-8')

    def _getEdgeMultiplicity(self,formula):
        """Returns the number of variable assignments satisfying the label formula in edge"""

        # Extract all variables in the formula. Take distinct entries only.
        # Do not list constants as variables
        vars = list(set(re.findall(r"\b(?!TRUE|FALSE)\w+",formula)))
        # Reformat constants in dd syntax
        formula = formula.replace("TRUE","True").replace("FALSE","False")

        # Build a BDD object
        bdd = dd.BDD()
        [bdd.add_var(var) for var in vars]
        node = bdd.add_expr(formula)

        # BDD.count gets the number of satisfying assignments for the BDD
        # The number is multiplied by a factor accounting for the unconstrained variables in the formula
        # ** is exponentiation
        return node.count(nvars=len(vars))*2**(len(self.var_set)-len(vars))

    def _getEdgeReducedMultiplicity(self, formula):
        """Computes the multiplicity of an edge by neglecting variables not appearing in the formula"""

        # Extract all variables in the formula. Take distinct entries only.
        # Do not list constants as variables
        vars = list(set(re.findall(r"\b(?!TRUE|FALSE)\w+",formula)))
        # Reformat constants in dd syntax
        formula = formula.replace("TRUE","True").replace("FALSE","False")

        # Build a BDD object
        bdd = dd.BDD()
        [bdd.add_var(var) for var in vars]
        node = bdd.add_expr(formula)

        # BDD.count gets the number of satisfying assignments for the BDD
        # The number is multiplied by a factor accounting for the unconstrained variables in the formula
        # ** is exponentiation
        return node.count(nvars=len(vars)) * 2 ** (len(self.constrained_var_set) - len(vars))

    def getAdjacencyMatrix(self):
        """Returns the adjacency matrix of the automaton"""
        mat = np.zeros([self.numstates,self.numstates],np.int32)
        for edge in self.edges:
            # Assign edge multiplicity to the (id_src,id_dst) matrix element
            mat[edge[0]][edge[2]] = edge[3]
        return mat

    def reachable(self, graph, node, reached):
        """Returns the set of all reachable states from the initial one (return type: set)"""

        reached.update([node])
        adjacent = graph.get(node)

        if adjacent is not None:
            for subnode in adjacent:
                if subnode not in reached:
                    reached.update(self.reachable(graph, subnode, reached))
        return reached

    def getCoReachableSCCs(self):
        if self.coreachable_sccs_indices == []:
            sccs = self.getSCCs()
            coreach_list = self.getCoReachabilityList()
            accepting_sccs = self.getAcceptingSCCs()

            coreachable_states = set([])
            for accepting_scc in accepting_sccs:
                coreachable_states.update(self.reachable(coreach_list, self.sccs[accepting_scc][0], coreachable_states))

            self.coreachable_sccs_indices = [self.sccs.index(scc) for scc in sccs if scc[0] in coreachable_states]
        return self.coreachable_sccs_indices

    def getSCCs(self):
        """Returns all SCCs of the automaton reachable from the initial state."""
        if self.sccs == []:
            adjList = self.getAdjacencyList()
            reachable_states = self.reachable(adjList, self.init_states[0], set([]))

            self.sccs = [x for x in tarjan.tarjan(adjList) if not not set(x).intersection(reachable_states)]

            if len(self.sccs) == 1:
                self.is_strongly_connected = True
            else:
                self.is_strongly_connected = False
            return self.sccs
        else:
            return self.sccs

    def getAcceptingSCCs(self):
        if self.accepting_sccs_indices == [] and self.accepting_states != []:
            accepting_sccs = self.getSCCs()
            # Different behavior for Buchi and Generalized Buchi
            if type(self.accepting_states[0]) == int:
                self.accepting_sccs_indices = [self.sccs.index(x) for x in self.sccs if not not set(x).intersection(set(self.accepting_states))]
            else:
                for accepting_set in self.accepting_states:
                    # Remove the sccs that have no intersection with accepting_set
                    accepting_sccs = [x for x in accepting_sccs if not not set(x).intersection(set(accepting_set))]
                self.accepting_sccs_indices = [self.sccs.index(x) for x in accepting_sccs]
        return self.accepting_sccs_indices

    def turnIntoClosure(self):
        """Transforms self into the automaton of its closure. In the closure, every state is an accepting state"""
        self.accepting_states = range(self.numstates)
        self.accepting_sccs_indices = self.sccs
        self.coreachable_sccs_indices = self.sccs
        self.sccs_entropies = []

    def getEntropiesSCCs(self):
        if self.sccs_entropies == []:
            self.getSCCs()
            self.sccs_entropies = [None] * len(self.sccs)
            sccs_indices = self.getCoReachableSCCs()
            adjMatrix = self.getAdjacencyMatrix()
            for scc in sccs_indices:
                submatrix = adjMatrix[np.ix_(self.sccs[scc], self.sccs[scc])]
                maxeig = np.max(np.absolute(np.linalg.eig(submatrix)[0]))
                if self.reduced:
                    # Overflow avoidance (see Notebook 2 pag. 6)
                    self.sccs_entropies[scc] = ((len(self.var_set) - len(self.constrained_var_set) + np.log2(maxeig)) / len(self.var_set))
                else:
                    self.sccs_entropies[scc] = (np.log2(maxeig) / len(self.var_set))
        return self.sccs_entropies


    def getEntropy(self):
        return max(self.getEntropiesSCCs() or [-np.inf])


    def getHausdorffDimension(self):
        """Computes the Hausdorff Dimension of the automaton's accepted language."""

        accepting_sccs = self.getAcceptingSCCs()
        hausdim = max([self.getEntropiesSCCs()[i] for i in accepting_sccs] or [-np.inf])
        self.sccs_maxentropy = [self.sccs[i] for i in range(len(self.sccs)) if self.sccs_entropies[i] == hausdim]
        return hausdim


    def getAdjacencyList(self):
        """Returns the adjacency list of the automaton (without multiplicities)"""
        list = dict()
        for i in range(0,self.numstates):
            list[i] = []
            for edge in self.edges:
                # If edge source is i
                if edge[0] == i:
                    # Add edge dest to adjacent nodes of i
                    list[i].append(edge[2])
        return list

    def getCoReachabilityList(self):
        """Returns the adjacency list after inverting the direction of all arcs"""
        list = dict()
        for i in range(0,self.numstates):
            list[i] = []
            for edge in self.edges:
                # If edge source is i
                if edge[2] == i:
                    # Add edge dest to adjacent nodes of i
                    list[i].append(edge[0])
        return list

    def getSubgraph(self, state_list):
        """Returns the subgraph induced by the state_list in input. Edges are only included if both the nodes they insist
        onto are in state_list"""

        subgraph = Automaton("manual")
        subgraph.var_set = self.var_set
        subgraph.constrained_var_set = self.constrained_var_set
        subgraph.reduced = self.reduced

        subgraph.numstates = len(state_list)

        # state_list contains the ids of the states as they are identified in the original automaton
        # self.
        # Also self.edges uses those ids. But in the subgraph we need to identify them progressively
        # to keep consistency. So subgraph.edges first reads the edges and then those are transformed
        # to use the new ids for the states
        subgraph.edges = [x for x in self.edges if x[0] in state_list and x[2] in state_list]
        for edge in subgraph.edges:
            edge[0] = state_list.index(edge[0])
            edge[2] = state_list.index(edge[2])

        # Any initial state will not change the Hausdorff dimension. Set it to state 0
        subgraph.init_states = [0]


        # Same applies to state ids in accepting states
        # In a Buchi automaton accepting_states is just a list of states, while in a GBA it is
        # a collection of lists of states
        if self.accepting_states != [] and type(self.accepting_states[0]) == int:
            subgraph.accepting_states = [state_list.index(x) for x in state_list if x in self.accepting_states]
        else:
            subgraph.accepting_states = []
            for accepting_set in self.accepting_states:
                subgraph.accepting_states.append([state_list.index(x) for x in state_list if x in accepting_set])

        return subgraph

#######################################################################################################################

class IntersectionAutomaton(Automaton):

    def __init__(self,a1,a2):

        # TIME PROBE: Check time to generate automaton
        start = timeit.default_timer()

        # The states of the intersection automaton are all combinations of a state of a1 and a state of a2
        self.states = list(itertools.product(range(0,a1.numstates),range(0,a2.numstates)))
        self.numstates1 = a1.numstates
        self.numstates2 = a2.numstates
        self.numstates = len(self.states)
        self.reduced = True # For overflow avoidance in Hausdim computation
        # A non-deadlocking edge in the intersection automaton is a combination of an edge in a1 and one in a2
        self.edges = [] # Each edge is a 4-element list [id_src formula id_dest multiplicity]
        self.var_set = list(set(a1.var_set + a2.var_set))
        self.constrained_var_set = list(set(a1.constrained_var_set + a2.constrained_var_set))
        self.init_states =[self._linearizedStateID(a,b) for a in a1.init_states for b in a2.init_states]
        self.accepting_states = [a1.accepting_states,a2.accepting_states]

        self.sccs = [] # List of SCCs. Used to buffer the results of getSCCs()
        self.accepting_sccs_indices = [] # List of accepting SCCs. Used to buffer the results of getAcceptingSCCs()
        self.coreachable_sccs_indices = [] # List of co-reachable SCCs. Used to buffer the results of getCoReachableSCCs
        self.sccs_entropies = [] # List of entropies of each SCC. Used to buffer the results of getEntropy()
        self.is_strongly_connected = None # getHausdorffDimension decides whether the automaton is strongly connected
        self.sccs_maxentropy = [] # List of accepting SCCs with max entropy. Used to buffer the results of getHausdorffDimension()

        for edge1 in a1.edges:
            for edge2 in a2.edges:
                # The formula of the edge is the 'and' between the formula of edge1 and the formula of edge2
                formula = "("+ edge1[1] + ") & (" + edge2[1] + ")"
                multiplicity = self._getEdgeReducedMultiplicity(formula) if self.reduced else self._getEdgeMultiplicity(formula)
                # If the multiplicity of this formula is 0, then do not add the edge
                if multiplicity > 0:
                    self.edges.append([self._linearizedStateID(edge1[0],edge2[0]),formula,self._linearizedStateID(edge1[2],edge2[2]),multiplicity])

        # TIME PROBE STOP
        self.automaton_compute_time = timeit.default_timer() - start

    def _linearizedStateID(self,i,j):
        """In the intersection automaton states are denoted by pairs of state IDs from two automata. Return a linearized index
        for the given state (i,j), linearized by sorting the pairs by increasing i's and then by increasing j's"""

        return i*self.numstates2+j

    def _stateIDAsPair(self,lin_id):
        return (int(lin_id/self.numstates2),lin_id%self.numstates2)

    def getAcceptingSCCs(self):
        """If the automaton comes from an intersection, it has two accepting sets. The first one has indices from the
        first automaton and the second one from the second automaton"""
        if self.accepting_sccs_indices == []:
            sccs = self.getSCCs()
            for i,scc in enumerate(sccs):
                accepting_aut_1 = False
                accepting_aut_2 = False
                scc_pairs = [self._stateIDAsPair(x) for x in scc]
                s = 0
                while s < len(scc_pairs) and not (accepting_aut_1 and accepting_aut_2):
                    if scc_pairs[s][0] in self.accepting_states[0]:
                        accepting_aut_1 = True
                    if scc_pairs[s][1] in self.accepting_states[1]:
                        accepting_aut_2 = True
                    s += 1
                if accepting_aut_1 and accepting_aut_2:
                    self.accepting_sccs_indices.append(i)
        return self.accepting_sccs_indices
