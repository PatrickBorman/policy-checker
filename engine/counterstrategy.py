import random
from path import State, Path

class CounterstrategyState:

    def __init__(self, name: str, inputs: dict, outputs: dict, successors=[], is_initial= False, is_dead = False):
        self.name = name
        self.inputs = inputs
        self.outputs = outputs
        self.influential_outputs = dict()
        self.successors = successors
        self.is_initial = is_initial
        self.is_dead = is_dead

    def add_successor(self, state_name):
        self.successors.append(state_name)
    
    def __str__(self):
        return f"State: {self.name}\n" + \
                f"Inputs: {self.inputs}\n" + \
                f"Outputs: {self.outputs}\n" + \
                f"Influential outputs: {self.influential_outputs}\n" + \
                f"Successors: {self.successors}\n" + \
                f"Initial: {self.is_initial}\n" + \
                f"Dead: {self.is_dead}"


class Counterstrategy:

    def __init__(self, states = dict(), use_influential=True):
        self.states = states
        self.use_influential = use_influential

        if self.use_influential:
            for state in self.states.values():
                self.compute_influentials(state)
        self.num_states = len(self.states)

    def __str__(self):
        state_strs = [str(state) + "\n" for state in self.states.values()]
        return "\n".join(state_strs)

    def add_state(self, state):
        self.states[state.name] = state

    def get_state(self, name):
        return self.states.get(name)

    def compute_influentials(self, state: CounterstrategyState):
        successors = [succ for succ in state.successors if "Sf" not in succ]

        different_out_vars = []
        for out_var in state.outputs:
            can_be_1, can_be_0 = False, False
            for succ in successors:
                if self.states[succ].outputs[out_var] is True:
                    can_be_1 = True
                if self.states[succ].outputs[out_var] is False:
                    can_be_0 = True
                if can_be_1 and can_be_0:
                    different_out_vars.append(out_var)
                    break

        for succ in successors:
            for out_var in different_out_vars:
                self.states[succ].influential_outputs[out_var] = self.states[succ].outputs[out_var]

    def getValuation(self, state):
        literals = []
        for varname in state.inputs:
            if state.inputs[varname] is True:
                literals.append(varname)
            else:
                literals.append("!"+varname)
        if self.use_influential:
            outputs = state.influential_outputs
        else:
            outputs = state.outputs
        for varname in outputs:
            if state.outputs[varname] is True:
                literals.append(varname)
            else:
                literals.append("!"+varname)
        return literals  

    def extractSingleTrace(self): 
        # to do - successors for each state need to be set. No use using names. 
        my_visited = [] 
        my_transient = []
        my_looping = []
        initial_state_name = next((state_name for state_name in self.states if self.states[state_name].is_initial))
        my_visited.append(State(initial_state_name))
        initial_state = self.states[initial_state_name]
        cur_state = initial_state
        print(initial_state)
        while cur_state.successors != []: 
            successor_state_name = next((state_name for state_name in cur_state.successors))
            successor_state = State(successor_state_name)
            successor_state_cs = self.states[successor_state_name]
            curr_path_state = State(cur_state.name)
            curr_path_state.set_successor(successor_state_name)
            # 1. get the intial state. Add to visited State(initila state name). extract counterstrategy state. 

            if successor_state in visited_states:
                looping_index = visited_states.index(successor_state)
                index = 0
                for state in visited_states:
                    if index >= looping_index: 
                        my_looping.append(state)  
                    elif index > 0: 
                        my_transient.append(state)
                    index + 1
                path = Path(State(initial_state_name, my_transient, my_looping))
                print("=== MY PATH ===")
                print(path)
                return path
            visited_states.append(successor_state)
            cur_state = successor_state_cs
        print("NON LOOPING PATH")
        index = 0
        for state in visited_states: 
            if index > 0: 
                my_transient.append(state)
            index + 1
        path = Path(State(initial_state_name), my_transient)
        print("=== MY PATH ===")
        print(path)  
        return path

    def extractRandomPath(self):
        """Extracts randomly a path from the counterstrategy"""

        # Perform a random walk from the initial state until hitting a failing state (no successors)
        # or completing a loop (which happens when visiting a state already visited in the walk)
        visited_states = []
        looping = False
        loop_startindex = None

        successors = [state_name for state_name in self.states if self.states[state_name].is_initial and not "Sf" in state_name]
        while successors != [] and not looping:
            
            curr_state = random.choice(successors)
            # curr_state = successors[0]
            
            if curr_state in visited_states:
                looping = True
                loop_startindex = visited_states.index(curr_state)
            else:
                successors = [state_name for state_name in self.states[curr_state].successors if not "Sf" in state_name]
                visited_states.append(curr_state)

        if visited_states == []:
            visited_states.append(random.choice([state for state in self.states if self.states[state].is_initial]))

        initial_state = State(visited_states[0])
        for var in self.getValuation(self.states[visited_states[0]]):
            initial_state.add_to_valuation(var)

        if len(visited_states)>1:
            initial_state.set_successor(visited_states[1])
            transient_states = []

            if not looping:

                # If the path is not looping, all the remaining states are transient
                for i,state in enumerate(visited_states[1:]):
                    i = i + 1 # Indices start from 1, since we iterate from the second element
                    new_state = State(state)
                    if i < len(visited_states)-1:
                        new_state.set_successor(visited_states[i+1])

                    for var in self.getValuation(self.states[state]):
                        new_state.add_to_valuation(var)

                    transient_states.append(new_state)

                # If the path is not looping, it ends in a failing state
                successors = self.states[transient_states[-1].id_state].successors
                while successors != []:
                    
                    failing_state_name = random.choice(successors)
                    failing_state = State(failing_state_name)
                
                    for var in self.getValuation(self.states[failing_state_name]):
                        failing_state.add_to_valuation(var)
                    transient_states[-1].set_successor(failing_state_name)
                    transient_states.append(failing_state)

                    successors = self.states[transient_states[-1].id_state].successors

                looping_states = None

            else:
                # In case the path is looping, the transient states go from index 1 to index loop_startindex-1
                # and the remaining ones are the looping states
                for i, state in enumerate(visited_states[1:loop_startindex]):
                    i = i + 1  # Indices start from 1, since we iterate from the second element
                    new_state = State(state)
                    if i < len(visited_states) - 1:
                        new_state.set_successor(visited_states[i + 1])

                    for var in self.getValuation(self.states[state]):
                        new_state.add_to_valuation(var)

                    transient_states.append(new_state)

                visited_states.append(visited_states[loop_startindex])
                looping_states = []
                for i,state in enumerate(visited_states[loop_startindex:-1]):
                    i = i + loop_startindex # Subarray starts at position loop_startindex
                    new_state = State(state)
                    new_state.set_successor(visited_states[i + 1])
                    for var in self.getValuation(self.states[state]):
                        new_state.add_to_valuation(var)
                    looping_states.append(new_state)

        else:

            if not looping:
                transient_states = []

                successors = self.states[initial_state.id_state].successors
                failing_state_name = random.choice(successors)
                initial_state.set_successor(failing_state_name)
                failing_state = State(failing_state_name)

                for var in self.getValuation(self.states[failing_state_name]):
                    failing_state.add_to_valuation(var)
                transient_states.append(failing_state)
                
                successors = self.states[transient_states[-1].id_state].successors
                while successors != []:
                    
                    failing_state_name = random.choice(successors)
                    failing_state = State(failing_state_name)
                
                    for var in self.getValuation(self.states[failing_state_name]):
                        failing_state.add_to_valuation(var)
                    transient_states[-1].set_successor(failing_state_name)
                    transient_states.append(failing_state)
                    
                    successors = self.states[transient_states[-1].id_state].successors

                looping_states = None
            
            else:
                initial_state.set_successor(initial_state.id_state)
                path = Path(initial_state, [], [initial_state])
                # path.unroll()
                return path

        # print()
        # print("=== INI ===")
        # print(self.states[initial_state.id_state])
        # print("\n=== TRANSIENT ===")
        # for state in transient_states:
        #     print(self.states[state.id_state])
        # print("\n=== LOOPING ===")
        # if looping_states is not None:
        #     for state in looping_states:
        #         print(self.states[state.id_state])

        return Path(initial_state,transient_states,looping_states)

