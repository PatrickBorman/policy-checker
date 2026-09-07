from counterstrategy import Path as p
import re
import pyparsing as pp
import syntax_utils as su

fairness_pattern = re.compile(r"G\(F(\(.*\))\)")
invariant_pattern = re.compile(r"G(\(.*\))")

def gr1LTL2Boolean(ltlFormula,path):
    fairness_match = fairness_pattern.match(ltlFormula)
    invariant_match = invariant_pattern.match(ltlFormula)
    if fairness_match:
        return fairnessLTL2Boolean(fairness_match.group(1),path)
    elif invariant_match:
        return invariantLTL2Boolean(invariant_match.group(1),path)
    else:
        return initialLTL2Boolean(ltlFormula,path)

def initialLTL2Boolean(ltlFormula,path):
    """
    Translates an LTL initial condition formula (given as a string) into its boolean counterpart
    on the given model (given as a Path)
    @param ltlFormula: A string in normalized syntax, such as a & (b | !c)
    @type ltlFormula: str
    @param path: The path on which the formula is translated
    @type path: L{p.Path}
    @return: A string containing the translated initial condition
    """
    return "("+re.sub(r"(\w+)",r"\1__"+path.initial_state.id_state,ltlFormula)+")"

## Grammar definition for invariants
next_op = pp.Literal("X")
variable = pp.Word(pp.alphas+"_", pp.alphanums+"_")
lparen = pp.Literal("(")
rparen = pp.Literal(")")
symbol = next_op | variable | lparen | rparen | "&" | "|" | "->" | "<->" | "!"
ltlInvariant = pp.OneOrMore(symbol)

# variable = pp.Word(pp.alphas+"_",pp.alphanums+"_")
# literal = variable | "!" + variable
# # The Forward command is used to define ParserElements whose production rules are defined later than they are used
# bool_expr = pp.Forward()
# next_expr = "X" + literal | "X" + "(" + bool_expr + ")"
# next_expr.setResultsName('Next_expr')
# unary_expr = next_expr | literal | "!" + "(" + bool_expr +")" |  "(" + bool_expr + ")"
# and_expr = "&" + bool_expr
# or_expr = "|" + bool_expr
# impl_expr = "->" + bool_expr
# impl2_expr = "<->" + bool_expr
# bool_expr <<  (unary_expr + and_expr | unary_expr + or_expr | unary_expr + impl_expr | unary_expr + impl2_expr | unary_expr )



def invariantLTL2Boolean(ltlFormula,path):
    """
    Translates an LTL invariant condition formula (given as a string) into its boolean counterpart
    on the given model (given as a Path)
    @param ltlFormula: A string in normalized syntax, such as a & (b | !c)
    @type ltlFormula: str
    @param path: The path on which the formula is translated
    @type path: L{p.Path}
    @return: A string containing the translated invariant
    """

    translatedInv = ""

    # Returns all the tokens in ltlFormula
    ltlTokens = ltlInvariant.parseString(ltlFormula)
    translatedInv = translatedInv +"("+ _translateInvOnStatePair(ltlTokens,path.initial_state) + ") & "

    for state in path.transient_states:
        translatedInv = translatedInv +"("+ _translateInvOnStatePair(ltlTokens,state) + ") & "

    for state in path.unrolled_states:
        translatedInv = translatedInv + "(" + _translateInvOnStatePair(ltlTokens,state) + ") & "

    if path.is_loop:
        for state in path.looping_states:
            translatedInv = translatedInv +"("+ _translateInvOnStatePair(ltlTokens,state) + ") & "

    translatedInv = translatedInv[:-3]
    return translatedInv



def _translateInvOnStatePair(ltlTokens,state):
    ret_string = ""
    var_pattern = re.compile(r"\w+")
    cur_state_id = state.id_state
    next_paren_depth = 0
    for token in ltlTokens:
        if token == "X" and state.successor is not None:
            cur_state_id = state.successor
        elif token == "X" and state.successor is None:
            # In this case the path is finite, and the next state is actually the failing state
            return "TRUE"
        else:
            ret_string = ret_string + token
            if token == "(" and cur_state_id == state.successor:
                next_paren_depth = next_paren_depth + 1
            elif token == ")" and cur_state_id == state.successor:
                next_paren_depth = next_paren_depth - 1
                if next_paren_depth == 0:
                    cur_state_id = state.id_state
            elif var_pattern.match(token) is not None:
                ret_string = ret_string + "__" + cur_state_id

    # TRUE and FALSE are not variables. They are constant and the state id must not be postponed
    ret_string = re.sub(r"(TRUE|FALSE)__\w+", r"\1", ret_string)
    return ret_string


def fairnessLTL2Boolean(ltlFormula,path):
    """
    Translates an LTL fairness formula into boolean
    """
    if hasattr(path,"looping_states"):
        ret_string = "("
        for s in path.looping_states:
            ret_string = ret_string + "(" + re.sub(r"(\w+)",r"\1__"+s.id_state,ltlFormula) + ") | "
        ret_string = ret_string[:-3] + ")"

        # TRUE and FALSE are not variables. They are constant and the state id must not be postponed
        ret_string = re.sub(r"(TRUE|FALSE)__\w+", r"\1", ret_string)
        return ret_string
    else:
        return ""

def counterstrategyLTL2Boolean(initAssumptionsList,invAssumptionsList,fairAssumptionsList,path):
    translation = ""
    for assumption in initAssumptionsList:
        if translation != "":
            translation = translation + "&"
        translation = translation + initialLTL2Boolean(assumption,path)

    for assumption in invAssumptionsList:
        if translation != "":
            translation = translation + "&"
        translation = translation + invariantLTL2Boolean(assumption,path)

    for assumption in fairAssumptionsList:
        if translation != "":
            translation = translation + "&"
        translation = translation + fairnessLTL2Boolean(assumption,path)

    if translation != "":
        translation = translation + "&"
    translation = translation + path.get_valuation()

    translation = re.sub(r"(TRUE|FALSE)__\w+",r"\1",translation)

    return translation

def guaranteesLTL2Boolean(initGuaranteeList,invGuaranteeList,fairGuaranteeList,path):
    translation = ""
    for guarantee in initGuaranteeList:
        if translation != "":
            translation = translation + "&"
        translation = translation + initialLTL2Boolean(guarantee,path)

    for guarantee in invGuaranteeList:
        if translation != "":
            translation = translation + "&"
        translation = translation + invariantLTL2Boolean(guarantee,path)

    for guarantee in fairGuaranteeList:
        if translation != "":
            translation = translation + "&"
        translation = translation + fairnessLTL2Boolean(guarantee,path)

    translation = re.sub(r"(TRUE|FALSE)__\w+",r"\1",translation)

    return translation

def writePathToFile(filename,path):
    outfile = open(filename,"w")
    outfile.write(str(path))
    outfile.close()

def writeMathsatFormulaToFile(filename,formula):
    outfile = open(filename,"w")
    # Get unique ids appearing in formula
    bool_vars_unique = set(re.findall(r"(\w+)",formula))
    bool_vars_unique.discard("TRUE")
    bool_vars_unique.discard("FALSE")
#    bool_vars = list(bool_vars_unique)

    mathsat_formula = "VAR\n" + ','.join(bool_vars_unique) + ": BOOLEAN\n" + "FORMULA\n" + formula

    outfile.write(mathsat_formula)
    outfile.close()

def parseInterpolant(filename):
    """Parses an interpolant as stored in a file produced by MathSAT"""

    infile = open(filename)
    # Find all auxiliary variables definitions and add them to a dictionary.
    # The key is the variable name and the value is its definition.
    define_pattern = re.compile(r"DEFINE (\w+) := (.*)")
    formula_pattern = re.compile(r"FORMULA (.*)")
    varname_pattern = re.compile(r"(def_\d+)")
    negvarname_pattern = re.compile(r"!def_\d+")

    definitions = dict()
    formula = ""
    for line in [x[0:-1] for x in infile.readlines()]:
        if "DEFINE" in line:
            define_match = define_pattern.match(line)
            definitions[define_match.group(1)] = define_match.group(2)
        elif "FORMULA" in line:
            formula_match = formula_pattern.match(line)
            formula = formula_match.group(1)

    infile.close()

    # Now remove parentheses from & definitions
    for varname in definitions:
        if "|" not in definitions[varname] and "->" not in definitions[varname] and "!" not in definitions[varname]:
            definitions[varname] = definitions[varname].strip("()")

    # Replace any occurrence of a variable with the corresponding formula.
    # Now all useless parentheses have been stripped from the definitions.
    while "def_" in formula:
        # This gets the varname found in formula
        varname = varname_pattern.findall(formula)[0]
        formula = formula.replace(varname,definitions[varname])

    return su.removeUnnecessaryParentheses(formula)

## TEST FUNCTIONS

def testLTL2Bool():
    exampledir = "/home/dgc14/Dropbox/HiPEDS/Research/Project/Examples/LiftExample/"
    init_infile = open(exampledir+"liftExample_Assumptions_Init","r")
    inv_infile = open(exampledir+"liftExample_Assumptions_Inv","r")
    fair_infile = open(exampledir+"liftExample_Assumptions_Fair","r")

    path = p.Path(exampledir+"graph_with_signals.dot")

    translation = ""
    for line in init_infile:
        translation = translation + initialLTL2Boolean(line,path) + " & "
    translation = translation + "\n"
    init_infile.close()

    for line in inv_infile:
        translation = translation + invariantLTL2Boolean(line,path) + " & "
    translation = translation + "\n"
    inv_infile.close()

    for line in fair_infile:
        translation = translation + fairnessLTL2Boolean(line,path) + " & "
    translation = translation[:-3] + "\n"
    translation = re.sub(r"(TRUE__\w*)",r"TRUE",translation)
    print(translation)
    return

def testTranslationOnLift():
    exampledir = "/home/dgc14/Dropbox/HiPEDS/Research/Project/Examples/LiftExample/"
    examplefile = "liftExample"
    ass_init_file = open(exampledir+examplefile+"_Assumptions_Init")
    ass_inv_file = open(exampledir+examplefile+"_Assumptions_Inv")
    ass_fair_file = open(exampledir+examplefile+"_Assumptions_Fair")

    guar_init_file = open(exampledir+examplefile+"_Guarantees_Init")
    guar_inv_file = open(exampledir+examplefile+"_Guarantees_Inv")
    guar_fair_file = open(exampledir+examplefile+"_Guarantees_Fair")


    path = p.Path(exampledir+"graph_with_signals.dot")

    ass_init = ass_init_file.readlines()
    ass_inv = ass_inv_file.readlines()
    ass_fair = ass_fair_file.readlines()

    guar_init = guar_init_file.readlines()
    guar_inv = guar_inv_file.readlines()
    guar_fair = guar_fair_file.readlines()

    ass_init_file.close()
    ass_inv_file.close()
    ass_fair_file.close()

    guar_init_file.close()
    guar_inv_file.close()
    guar_fair_file.close()

    counterstrategyTranslation = counterstrategyLTL2Boolean(ass_init,ass_inv,ass_fair,path)
    guaranteesTranslation = guaranteesLTL2Boolean(guar_init,guar_inv,guar_fair,path)

    writeMathsatFormulaToFile(exampledir+"counterstrategy_auto",counterstrategyTranslation)
    writeMathsatFormulaToFile(exampledir+"guarantees_auto",guaranteesTranslation)

def testTranslationOnAMBA02():
    exampledir = "/home/dgc14/Dropbox/HiPEDS/Research/Project/Examples/AMBA02Example/"
    examplefile = "amba02"
    ass_init_file = open(exampledir+examplefile+"_Assumptions_Init")
    ass_inv_file = open(exampledir+examplefile+"_Assumptions_Inv")
    ass_fair_file = open(exampledir+examplefile+"_Assumptions_Fair")

    guar_init_file = open(exampledir+examplefile+"_Guarantees_Init")
    guar_inv_file = open(exampledir+examplefile+"_Guarantees_Inv")
    guar_fair_file = open(exampledir+examplefile+"_Guarantees_Fair")


    path = p.Path(exampledir+"graph_with_signals.dot")

    ass_init = ass_init_file.readlines()
    ass_inv = ass_inv_file.readlines()
    ass_fair = ass_fair_file.readlines()

    guar_init = guar_init_file.readlines()
    guar_inv = guar_inv_file.readlines()
    guar_fair = guar_fair_file.readlines()

    ass_init_file.close()
    ass_inv_file.close()
    ass_fair_file.close()

    guar_init_file.close()
    guar_inv_file.close()
    guar_fair_file.close()

    counterstrategyTranslation = counterstrategyLTL2Boolean(ass_init,ass_inv,ass_fair,path)
    guaranteesTranslation = guaranteesLTL2Boolean(guar_init,guar_inv,guar_fair,path)

    writeMathsatFormulaToFile(exampledir+"counterstrategy_auto",counterstrategyTranslation)
    writeMathsatFormulaToFile(exampledir+"guarantees_auto",guaranteesTranslation)

# def testPyparsing():
#     res = bool_expr.parseString("X(a | !(bravotu | meglioio))")
#     print res
#     print res.asDict()

def testStatePairTranslation():
    exampledir = "/home/dgc14/Dropbox/HiPEDS/Research/Project/Examples/LiftExample/"
    inv_infile = open(exampledir+"liftExample_Assumptions_Inv","r")

    path = p.Path(exampledir+"graph_with_signals.dot")

    for line in inv_infile.readlines():
        ltlTokens = ltlInvariant.parseString(line)
        print("LTL: " + line +"Translation: "+_translateInvOnStatePair(ltlTokens,path.initial_state))
        print(ltlTokens)
    inv_infile.close()
    return

def main():
    print(parseInterpolant("../Refinement/INTERP.1.msat"))

#    testPyparsing()
if __name__=='__main__':
    main()
