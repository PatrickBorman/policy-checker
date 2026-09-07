import pyparsing as pp
import re

# To make the parsing "incredibly faster"
pp.ParserElement.enablePackrat()
# initialList = []
# invariantsList = []
# fairnessList = []

## GR(1) grammar

un_op = pp.Literal("!") | pp.Literal("X")
always_op = pp.Literal("G")
eventually_op = pp.Literal("F")
const_true = pp.Literal("true")
const_false = pp.Literal("false")
variable = pp.Word(pp.alphas+"_", pp.alphanums+"_")
# lparen = pp.Literal("(")
# rparen = pp.Literal(")")

and_op = pp.Literal("&")
or_op = pp.Literal("|")
implies_op = pp.Literal("->")
dimplies_op = pp.Literal("<->")

bool_operand = const_true | const_false | variable

class BoolOperand(object):
    def __init__(self, t):
        self.operand = t[0]

    def __str__(self):
        return self.operand

    def __eq__(self,other):
        return self.operand == other.operand

    def __ne__(self,other):
        return not self == other
    # Redefine hash to allow uniqueness check in set operations
    def __hash__(self):
        return hash(self.operand)

bool_operand.setParseAction(BoolOperand)

class BoolUnary(object):
    def __init__(self, t):
        self.operator = t[0][0]
        self.operand = t[0][1]
        self.expression = self.operator+"("+str(self.operand)+")" if self.operator != "!" \
            else self.operator+str(self.operand)


    def __str__(self):
        return self.expression

    def __eq__(self,other):
        return self.expression == other.expression

    def __ne__(self,other):
        return not self == other

    # Redefine hash to allow uniqueness check in set operations
    def __hash__(self):
        return hash(self.expression)

class BoolBinary(object):
    def __init__(self, t):
        self.operator = t[0][1]
        self.args = t[0][0::2]
        self.expression = "(" + str(self.args[0])
        for arg in self.args[1:]:
            self.expression = self.expression + \
                              " " + self.reprsymbol + " " + \
                              str(arg)
        self.expression = self.expression + ")"

    def __str__(self):
        return self.expression

    def __eq__(self,other):
        return self.expression == other.expression
    def __ne__(self,other):
        return not self == other

    # Redefine __hash__ to allow uniqueness check in set operations
    def __hash__(self):
        return hash(self.expression)

class BoolAnd(BoolBinary):
    reprsymbol = '&'

class BoolOr(BoolBinary):
    reprsymbol = '|'

class BoolImplies(BoolBinary):
    reprsymbol = '->'

class BoolDImplies(BoolBinary):
    reprsymbol = '<->'

class Always(BoolUnary):
    reprsymbol = 'G'

class Eventually(BoolUnary):
    reprsymbol = 'F'

bool_expr = pp.infixNotation(bool_operand,
                             [(un_op, 1, pp.opAssoc.RIGHT, BoolUnary),
                              (and_op, 2, pp.opAssoc.LEFT, BoolAnd),
                              (or_op, 2, pp.opAssoc.LEFT, BoolOr),
                              (implies_op, 2, pp.opAssoc.LEFT, BoolImplies),
                              (dimplies_op, 2, pp.opAssoc.LEFT, BoolDImplies)])

ltl_expr = pp.infixNotation(bool_operand,
                             [(un_op, 1, pp.opAssoc.RIGHT, BoolUnary),
                              (always_op, 1, pp.opAssoc.RIGHT, Always),
                              (eventually_op, 1, pp.opAssoc.RIGHT, Eventually),
                              (and_op, 2, pp.opAssoc.LEFT, BoolAnd),
                              (or_op, 2, pp.opAssoc.LEFT, BoolOr),
                              (implies_op, 2, pp.opAssoc.LEFT, BoolImplies),
                              (dimplies_op, 2, pp.opAssoc.LEFT, BoolDImplies)])

# class Invariant(object):
#     def __init__(self,t):
#         self.expression = "("+str(t)+")"
#
#     def __str__(self):
#         return self.expression
#
# class Fairness(object):
#     def __init__(self,t):
#         self.expression = "("+str(t)+")"
#
#     def __str__(self):
#         return self.expression
#
# class Initial(object):
#     def __init__(self,t):
#         self.expression = "("+str(t)+")"
#
#     def __str__(self):
#         return self.expression

pars = None

def parserInit():
    """Resets the parser"""
    global pars
    pars = None

def parseInitials(phi):
    """Returns an array containing all initial conditions.
        For instance, if phi = a & b & G(a & b) & G(c) & G(F(c)) it returns ['(a)','(b)']"""
    global pars
    if pars is None:
        pars = ltl_expr.parseString(phi)
    initials = []
    if not isinstance(pars[0],BoolUnary) and not isinstance(pars[0],BoolOperand):
        for gr1_unit in pars[0].args:
            if not isinstance(gr1_unit, Always):
                initials.append("(" + str(gr1_unit) + ")")
    elif not isinstance(pars[0],Always):
        initials.append("(" + str(pars[0]) + ")")
    return initials

def parseInvariants(phi):
    """Returns an array containing all invariants without the G operator.
    For instance, if phi = G(a & b) & G(c) & G(F(c)) it returns ['(a & b)','(c)']"""
    global pars
    if pars is None:
        pars = ltl_expr.parseString(phi)
    invariants = []
    if not isinstance(pars[0],BoolUnary) and not isinstance(pars[0],BoolOperand):
        for gr1_unit in pars[0].args:
            if isinstance(gr1_unit,Always):
                if not isinstance(gr1_unit.operand,Eventually):
                    invariants.append("("+str(gr1_unit.operand)+")")
    elif isinstance(pars[0],Always):
        if not isinstance(pars[0].operand, Eventually):
            invariants.append("(" + str(pars[0].operand) + ")")
    return invariants

def parseFairness(phi):
    """Returns an array containing all fairness without the G operator.
        For instance, if phi = G(a & b) & G(c) & G(F(c)) it returns ['(c)']"""
    global pars
    if pars is None:
        pars = ltl_expr.parseString(phi)
    fairness = []
    if not isinstance(pars[0], BoolUnary) and not isinstance(pars[0], BoolOperand):
        for gr1_unit in pars[0].args:
            if isinstance(gr1_unit, Always):
                if isinstance(gr1_unit.operand, Eventually):
                    fairness.append("("+str(gr1_unit.operand.operand)+")")
    elif isinstance(pars[0],Always):
        if isinstance(pars[0].operand, Eventually):
            fairness.append("(" + str(pars[0].operand.operand) + ")")
    return fairness

def getInvariant(phi):
    """Given phi, returns a single invariant containing the conjunction of the invariants in phi"""
    invariants = parseInvariants(phi)
    return "G(" + " & ".join(invariants)+")"

def getCFairness(phi):
    """Returns an array of alternative fairness complements. For instance, if phi contains G(F(a)) & G(F(b)) the procedure
    returns ['!(a)','!(b)']"""
    fairness = parseFairness(phi)
    return ["!("+x+")" for x in fairness]

def getParseTreeFromBoolean(phi):
    phi = removeUnnecessaryParentheses(phi)
    return bool_expr.parseString(phi)[0]

def removeUnnecessaryParentheses(phi):
    """Given a string containing a Boolean logic expression, removes unnecessary parentheses from it.
    This is to avoid errors when parsing the string due to excessive recursion depth"""

    # Remove parentheses around single literals
    var_pattern = re.compile(r"\((\w+)\)")
    while re.findall(var_pattern,phi) != []:
        phi = re.sub(var_pattern,r"\1",phi)

    # Remove double negations
    idx_double_neg = phi.find("!(!")
    while idx_double_neg != -1:
        # Current recursion depth (the first negation symbol is at depth 0)
        j = 1
        # Current scanned character
        i = idx_double_neg + 3
        no_double_neg = False
        # No double negation if after !(! there is not a parenthesized expression or a literal:
        # !(!var) is a double negation
        # !(!(a & b)) is
        # !(!a & b) is not
        while i < len(phi) and j != 0 and not no_double_neg:
            if phi[i] == "(":
                j = j + 1
            elif phi[i] == ")":
                j = j - 1
            elif j == 1 and (phi[i]=="&" or phi[i]=="|" or phi[i]=="-"):
                no_double_neg = True
            i = i + 1
        if j == 0:
            end_double_neg = i - 1
            phi = phi[0:idx_double_neg]+phi[idx_double_neg+3:end_double_neg]+phi[end_double_neg+1:]
            # Look up for another candidate double negation in the changed string
            idx_double_neg = phi.find("!(!")
        # If going into this branch, the current candidate double
        # negation was not a double negation. phi did not change, so we need to look for the next index containing
        # !(!
        elif idx_double_neg+3 < len(phi):
            offset_double_neg = phi[idx_double_neg+3:].find("!(!")
            if offset_double_neg != -1:
                idx_double_neg = offset_double_neg + idx_double_neg + 3
            else:
                idx_double_neg = -1
        else:
            # No more to check
            idx_double_neg = -1

    return phi


def main():
    print(parseInitials("a"))
    print(parseInvariants("a & b & G(a) & G(F(c))"))
    #print(str(parseInvariants("a & b & G(a)")[0])
    #print(str(parseInvariants("G(a & b -> c | d & X(e)) & G(f | g) & G(F(h & !i))"))
    #print(str(parseFairness("G(a & b -> c | d & X(e)) & G(f | g) & G(F(h & !i))"))
    parserInit()
    print(getInvariant("G(a & b -> c | d & X(e)) & G(f | g) & G(F(h & !i))"))
    parserInit()
    print(getCFairness("G(a & b -> c | d & X(e)) & G(f | g) & G(F(h & !i))"))
    parserInit()
    print(parseInitials("!b1 & !b2 & !b3 & G((b1 & f1) -> X(!b1)) & G((b2 & f2) -> X(!b2)) & G((b3 & f3) -> X(!b3)) & G((b1 & !f1) -> X(b1)) & G((b2 & !f2) -> X(b2)) & G((b3 & !f3) -> X(b3)) & G((!b1 & !b2 & !b3) -> X(b1 | b2 | b3))"))
    print(getInvariant("!b1 & !b2 & !b3 & G((b1 & f1) -> X(!b1)) & G((b2 & f2) -> X(!b2)) & G((b3 & f3) -> X(!b3)) & G((b1 & !f1) -> X(b1)) & G((b2 & !f2) -> X(b2)) & G((b3 & !f3) -> X(b3)) & G((!b1 & !b2 & !b3) -> X(b1 | b2 | b3))"))
    print(getCFairness("!b1 & !b2 & !b3 & G((b1 & f1) -> X(!b1)) & G((b2 & f2) -> X(!b2)) & G((b3 & f3) -> X(!b3)) & G((b1 & !f1) -> X(b1)) & G((b2 & !f2) -> X(b2)) & G((b3 & !f3) -> X(b3)) & G((!b1 & !b2 & !b3) -> X(b1 | b2 | b3))"))

    parserInit()
    print(str(getParseTreeFromBoolean("a | !b & c & d | e & (!f | !(g & h) | i) | (j)")))

    print("Parentheses cleanup: " + removeUnnecessaryParentheses("(a & !(!(b))) & !(!(b & (c) & !d)) & ((((d)))) & !(!e)"))

if(__name__=="__main__"):
    main()