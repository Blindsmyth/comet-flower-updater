// Export function starts and selected xrefs for the zoom-project Ghidra test.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import java.io.*;

public class ExportMap extends GhidraScript {
    @Override
    public void run() throws Exception {
        String out = getScriptArgs().length > 0 ? getScriptArgs()[0] : "ghidra_out";
        new File(out).mkdirs();
        try (PrintWriter w = new PrintWriter(new FileWriter(out + "/functions.txt"))) {
            for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
                w.printf("%s %d %s%n", f.getEntryPoint(), f.getBody().getNumAddresses(), f.getName());
            }
        }
        String[] targets = { "c0119fb0", "c01357c8", "c011a1b0", "c00643c0", "c015afa0", "c011aac0" };
        ReferenceManager rm = currentProgram.getReferenceManager();
        try (PrintWriter w = new PrintWriter(new FileWriter(out + "/xrefs.txt"))) {
            for (String t : targets) {
                Address a = toAddr(Long.parseLong(t, 16));
                // references to the address itself and to anything inside the first 0x200 bytes
                for (int off = 0; off < 0x200; off++) {
                    Address x = a.add(off);
                    for (Reference r : rm.getReferencesTo(x)) {
                        Function f = getFunctionContaining(r.getFromAddress());
                        w.printf("%s+%x <- %s %s %s%n", t, off, r.getFromAddress(), r.getReferenceType(),
                                 f == null ? "-" : f.getEntryPoint().toString());
                    }
                    if (!t.equals("c0119fb0")) break;
                }
            }
        }
        println("exported to " + out);
    }
}
