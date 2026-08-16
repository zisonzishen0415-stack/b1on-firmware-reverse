// Create functions at the given addresses and decompile them to C files.
// Usage: -postScript DecompileFns.java <outdir> <addr1> <addr2> ...
// @category Analysis

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSet;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.symbol.SourceType;

import java.io.File;
import java.io.PrintWriter;

public class DecompileFns extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 2) {
            println("usage: DecompileFns.java <outdir> <hexaddr> ...");
            return;
        }
        File outDir = new File(args[0]);
        outDir.mkdirs();
        Listing listing = currentProgram.getListing();
        // Create all functions first so the decompiler's snapshot includes them.
        for (int i = 1; i < args.length; i++) {
            String arg = args[i];
            long bodyLimit = 0x8000;
            if (arg.contains(":")) {
                String[] parts = arg.split(":");
                arg = parts[0];
                bodyLimit = Long.parseLong(parts[1].replaceFirst("^0x", ""), 16);
            }
            long a = Long.parseLong(arg.replaceFirst("^0x", ""), 16);
            Address addr = currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(a);
            if (listing.getFunctionAt(addr) == null) {
                try {
                    listing.createFunction("f_" + arg, addr,
                            new AddressSet(addr), SourceType.USER_DEFINED);
                } catch (Exception e) {
                    println("createFunction failed at " + addr + ": " + e);
                }
            }
        }
        DecompInterface decomp = new DecompInterface();
        decomp.toggleCCode(true);
        decomp.setSimplificationStyle("decompile");
        if (!decomp.openProgram(currentProgram)) {
            println("decompiler openProgram failed");
            return;
        }
        for (int i = 1; i < args.length; i++) {
            String arg = args[i];
            long bodyLimit = 0x8000;
            if (arg.contains(":")) {
                String[] parts = arg.split(":");
                arg = parts[0];
                bodyLimit = Long.parseLong(parts[1].replaceFirst("^0x", ""), 16);
            }
            long a = Long.parseLong(arg.replaceFirst("^0x", ""), 16);
            Address addr = currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(a);
            Function fn = listing.getFunctionAt(addr);
            // Compute an exact body: contiguous instructions from the entry,
            // stopping at undefined bytes or another function's entry.
            AddressSet body = new AddressSet();
            Address cur = addr;
            while (true) {
                ghidra.program.model.listing.Instruction insn = listing.getInstructionAt(cur);
                if (insn == null) {
                    break;
                }
                body.add(cur, insn.getMaxAddress());
                Function owner = listing.getFunctionContaining(insn.getMaxAddress().add(1));
                if (owner != null && !owner.getEntryPoint().equals(addr)) {
                    break;
                }
                cur = insn.getMaxAddress().add(1);
                if (cur.getOffset() - addr.getOffset() > bodyLimit) {
                    break;  // safety cap
                }
            }
            fn.setBody(body);
            DecompileResults res = decomp.decompileFunction(fn, 120, monitor);
            if (!res.decompileCompleted() || res.getDecompiledFunction() == null) {
                println("decompile failed at " + addr + " completed=" + res.decompileCompleted()
                        + " err=[" + res.getErrorMessage() + "] fn=" + res.getFunction()
                        + " body=" + fn.getBody());
                continue;
            }
            String name = "fn_" + arg + ".c";
            try (PrintWriter pw = new PrintWriter(new File(outDir, name))) {
                pw.println("// " + fn.getName() + " @ " + addr);
                pw.println(res.getDecompiledFunction().getC());
            }
            println("decompiled " + addr + " -> " + name);
        }
        decomp.dispose();
    }
}
