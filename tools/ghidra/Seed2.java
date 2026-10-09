// Pre-analysis for the zoom firmware: drop non-loaded blocks, add RAM blocks,
// seed known starts, and force CALLPs through A3 (save/restore helpers) to be
// calls that fall through, iterating until disassembly stops growing.
import ghidra.app.script.GhidraScript;
import ghidra.app.cmd.disassemble.DisassembleCommand;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.*;
import ghidra.program.model.symbol.FlowType;
import java.nio.file.*;
import java.util.*;

public class Seed2 extends GhidraScript {
    @Override
    public void run() throws Exception {
        Memory mem = currentProgram.getMemory();
        for (MemoryBlock b : mem.getBlocks())
            if (!b.isLoaded() || b.getName().startsWith("_elf")) mem.removeBlock(b, monitor);
        long[][] ram = { {0xc0100000L, 0xc011adc0L}, {0x11f00000L, 0x11f08000L} };
        for (long[] r : ram) {
            Address s = toAddr(r[0]);
            if (!mem.contains(s)) {
                MemoryBlock b = mem.createUninitializedBlock("ram_" + Long.toHexString(r[0]), s, r[1] - r[0], false);
                b.setRead(true); b.setWrite(true);
            }
        }
        List<Address> seeds = new ArrayList<>();
        for (String l : Files.readAllLines(Paths.get(getScriptArgs()[0]))) {
            l = l.trim(); if (!l.isEmpty()) seeds.add(toAddr(Long.parseLong(l, 16)));
        }
        AddressSet todo = new AddressSet();
        for (Address a : seeds) if (mem.contains(a)) todo.add(a);
        Listing lst = currentProgram.getListing();
        Set<Address> fixed = new HashSet<>();
        for (int round = 0; round < 60 && !todo.isEmpty(); round++) {
            for (AddressRange r : todo) new DisassembleCommand(r.getMinAddress(), null, true).applyTo(currentProgram, monitor);
            todo = new AddressSet();
            for (Instruction i : lst.getInstructions(true)) {
                if (fixed.contains(i.getAddress())) continue;
                String m = i.getMnemonicString();
                if (m.startsWith("CALLP")) {
                    fixed.add(i.getAddress());
                    i.setFlowOverride(ghidra.program.model.listing.FlowOverride.CALL);
                    Address ft = i.getMaxAddress().add(1);
                    if (mem.contains(ft) && lst.getInstructionAt(ft) == null) todo.add(ft);
                }
            }
            long n = 0; for (Instruction i : lst.getInstructions(true)) n++;
            println("round " + round + " instructions " + n + " new fallthroughs " + todo.getNumAddresses());
        }
        int n = 0;
        for (Address a : seeds) if (mem.contains(a) && getFunctionAt(a) == null && createFunction(a, null) != null) n++;
        println("seeded functions: " + n);
    }
}
