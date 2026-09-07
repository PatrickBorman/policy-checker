
class State(object):
    def __init__(self, id_state):
        """
        Constructor.
        """

        self.id_state = id_state
        self.valuation = set()

        #: The successor's id
        #: @type string
        self.successor = None

    def set_successor(self, id_state):
        self.successor = id_state
        return

    def get_valuation(self):
        valuation_with_ids = []
        for bool_literal in self.valuation:
            valuation_with_ids.append(bool_literal + "__" + self.id_state)
        return ' & '.join(valuation_with_ids)

    def add_to_valuation(self, bool_literal):
        self.valuation.add(bool_literal)
        return


"""This is a rewriting of the Path class, much simpler than previous version since it does not read the path from a file"""
class Path:
    def __init__(self, initial_state, transient_states, looping_states=None):
        #: List of all the states
        #: @type: L{State dict}
        self.states = dict()

        #: Initial state of the graph
        #: @type: L{State}
        self.initial_state = initial_state

        #: Transient states
        #: @type: L{State[]}
        self.transient_states = transient_states

        #: Looping states
        #: @type: L{State[]}
        if looping_states is not None:
            self.looping_states = looping_states
            self.is_loop = True
        else:
            self.is_loop = False
        self.unrolled_states = []
        self.unrolling_degree = 0

        self.states[self.initial_state.id_state] = self.initial_state
        for state in self.transient_states:
            self.states[state.id_state] = state

        if self.is_loop:
            for state in self.looping_states:
                self.states[state.id_state] = state

    def get_valuation(self):
        valuation = ""
        for s in self.states.values():
            if valuation != "" and s.get_valuation() != "":
                valuation = valuation + " & "
            valuation = valuation + s.get_valuation()
        return valuation

    def save(self,file):
        file.write(str(self))

    # Unrolls the path by one more degree
    def unroll(self):
        if self.is_loop:
            # Increase the unrolling degree
            self.unrolling_degree = self.unrolling_degree+1
            # Fit the first unrolled state in the path by changing the previous state's
            # successor
            unrolled_state = State(self.looping_states[0].id_state+"_"+str(self.unrolling_degree))
            if self.unrolling_degree == 1:
                if len(self.transient_states) >= 1:
                    self.transient_states[-1].set_successor(unrolled_state.id_state)
                else:
                    self.initial_state.set_successor(unrolled_state.id_state)
            else:
                self.unrolled_states[-1].set_successor(unrolled_state.id_state)
            self.unrolled_states.append(unrolled_state)
            self.states[unrolled_state.id_state] = unrolled_state
            unrolled_state.valuation = self.looping_states[0].valuation

            # Add the other unrolled states
            for i in range(1,len(self.looping_states)):
                unrolled_state = State(self.looping_states[i].id_state+"_"+str(self.unrolling_degree))
                self.unrolled_states[-1].set_successor(unrolled_state.id_state)
                self.unrolled_states.append(unrolled_state)
                self.states[unrolled_state.id_state] = unrolled_state
                unrolled_state.valuation = self.looping_states[i].valuation

            # Set the successor of the last unrolled state
            self.unrolled_states[-1].set_successor(self.looping_states[0].id_state)

    def __str__(self):
        ret_string = self.initial_state.id_state
        if self.transient_states is not None:
            for s in self.transient_states:
                ret_string = ret_string + " -> " + s.id_state
        if self.is_loop:
            if self.unrolling_degree >= 1:
                for s in self.unrolled_states:
                    ret_string = ret_string + " -> " + s.id_state
            ret_string = ret_string + " -> loop("
            for s in self.looping_states:
                ret_string = ret_string + " -> " + s.id_state
            ret_string = ret_string + ")"
        return ret_string

