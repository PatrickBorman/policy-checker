import tau.smlab.syntech.Spectra.cli.SpectraTool;

/**
 * Thin CLI over Spectra's SpectraTool so Python can drive it as a subprocess.
 *   SpecCheck realizable <spec.spectra> [timeoutSec]
 *   SpecCheck ysat       <spec.spectra>
 *   SpecCheck core       <spec.spectra>
 *   SpecCheck cs         <spec.spectra> [timeoutSec]      counter-strategy (minimised)
 * Prints a single line "RESULT <value>" (or the raw text for core/cs) and exits 0.
 * Errors print "ERROR <message>" and exit 2.
 */
public class SpecCheck {
  public static void main(String[] a) {
    if (a.length < 2) { System.err.println("usage: SpecCheck <cmd> <spec> [timeout]"); System.exit(1); }
    String cmd = a[0], spec = a[1];
    int timeout = a.length > 2 ? Integer.parseInt(a[2]) : 120;
    long t0 = System.currentTimeMillis();
    try {
      switch (cmd) {
        case "realizable":
          System.out.println("RESULT " + SpectraTool.checkRealizability(spec, timeout)); break;
        case "ysat":
          System.out.println("RESULT " + SpectraTool.checkYSatisfiability(spec)); break;
        case "sat":
          System.out.println("RESULT " + SpectraTool.checkSatisfiability(spec)); break;
        case "core":
          System.out.println("RESULT " + SpectraTool.computeUnrealizableCore(spec)); break;
        case "cs":
          System.out.println("RESULT_BEGIN");
          System.out.println(SpectraTool.generateCounterStrategy(spec, true, timeout));
          System.out.println("RESULT_END"); break;
        default:
          System.err.println("unknown cmd " + cmd); System.exit(1);
      }
      System.err.println("[t] " + cmd + " " + (System.currentTimeMillis() - t0) + "ms");
    } catch (Throwable e) {
      System.out.println("ERROR " + e);
      e.printStackTrace(System.err);
      System.exit(2);
    } finally {
      try { SpectraTool.shutdown(); } catch (Throwable ignore) {}
    }
    System.exit(0);
  }
}
