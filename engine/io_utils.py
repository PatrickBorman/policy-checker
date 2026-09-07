import re
import specification as sp


# Returns a list with all assumptions in a .rat file
def extractAssumptionList(spec):
    spec = [re.sub(r"\s", "", spec[i + 1]) for i, line in enumerate(spec) if re.search("asm|assumption", line)]
    return spec

# Returns a list with all guarantees in a .rat file
def extractGuaranteesList(spec):
    spec = [re.sub(r"\s", "", spec[i + 1]) for i, line in enumerate(spec) if re.search("gar|guarantee", line)]
    return spec

# Extract input variables from .rat file
def extractInputVariablesFromFile(spec):
    variables = []
    for line in spec:
        match = re.search(r'(?:env)\s+boolean\s+(\w+)\s*', line)
        if match:
            variables.append(match.group(1))

    return variables

# Extract output variables from .rat file
def extractOutputVariablesFromFile(spec):
    variables = []
    for line in spec:
        match = re.search(r'(?:sys|aux)\s+boolean\s+(\w+)\s*', line)
        if match:
            variables.append(match.group(1))
    
    return variables


# Extract variables as a list from a string formula
def extractVariablesFromFormula(phi):
    exclude = {"G", "F", "GF", "X", "next", "U", "true", "false", "and"}
    return [x for x in re.findall("\w+", phi) if x not in exclude]

# Replaces '&&' with '&', '||' with '|'
def normalizeFormulaSyntax( formula ):
    formula = formula.replace('&&','&')
    formula = formula.replace('||','|')
    formula = re.sub(r"\b%s\b" % "next", "X", formula)
    formula = re.sub(r"\b%s\b" % "always", "G", formula)
    formula = re.sub(r"\b%s\b" % "eventually!", "F", formula)
    # Pattern replacement for boolean variables expressed as name=value
    patternBoolPosVar = re.compile("([A-Za-z0-9_]+)( ?= ?1)")
    patternBoolNegVar = re.compile("([A-Za-z0-9_]+)( ?= ?0)")

    formula = patternBoolPosVar.sub(r"\1",formula)
    formula = patternBoolNegVar.sub(r"!\1",formula)
    formula = formula.lstrip().rstrip()

    return formula

# UNUSED
def normalizeSpinFormulaSyntax( formula ):
    formula = re.sub(r'\b&\b', '&&',formula)
    formula = re.sub(r'\b\|\b', '||',formula)
    # The last replacement is necessary when formula is output by a parser that recognizes FALSE as F(ALSE)
    formula = re.sub(r"\b%s\b" % "next", "X", formula)
    formula = re.sub(r"\b%s\b" % "always", "G", formula)
    formula = re.sub(r"\b%s\b" % "eventually!", "F", formula)
    formula = formula.replace("TRUE","true").replace("FALSE","false").replace("F(ALSE)","false")
    # Pattern replacement for boolean variables expressed as name=value
    patternBoolPosVar = re.compile("([A-Za-z0-9_]+)( ?= ?1)")
    patternBoolNegVar = re.compile("([A-Za-z0-9_]+)( ?= ?0)")

    formula = patternBoolPosVar.sub(r"\1", formula)
    formula = patternBoolNegVar.sub(r"!\1", formula)
    formula = formula.lstrip().rstrip()

    return formula

# varpattern matches variable names in LTL formulae
varpattern = re.compile(r"\b(?!TRUE|FALSE)\w+")

# UNUSED
def getDistinctVariablesInFormula(formula):
    """Returns the set of all distinct variables appearing in formula"""
    varset = set(varpattern.findall(formula))
    varset.discard("X")
    varset.discard("G")
    varset.discard("F")
    return varset

# UNUSED
def countBoolOpsInFormula(formula):
    formula = normalizeFormulaSyntax(formula)
    # We do not include the number of "<->" in the formula since they are already counted in "->"
    return formula.count("&") + formula.count("|") + formula.count("->")

def main():
    print(extractInputVariablesFromFile("/home/dgc14/WeakestAssumptions/Weakness/tests/amba08.rat"))
    print(extractOutputVariablesFromFile("/home/dgc14/WeakestAssumptions/Weakness/tests/amba08.rat"))

if __name__=="__main__":
    main()