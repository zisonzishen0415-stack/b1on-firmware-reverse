// Bulk-create functions from an entry list and decompile each to C.
// Usage: -postScript DecompileAll.java <entries.txt> <outdir>
//   entries.txt: one hex address per line (8 digits, no 0x).
// Writes <outdir>/fn_<addr>.c plus <outdir>/index.csv (addr,ok,size,functions).
// @category Analysis

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSet;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.symbol.SourceType;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileReader;
import java.io.PrintWriter;
import java.util.ArrayList;
import java.util.List;

public class DecompileAll extends GhidraScript {
    private static final long BODY_LIMIT = 0x8000;

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 2) {
            println("usage: DecompileAll.java <entries.txt> <outdir>");
            return;
        }
        List<Long> entries = new ArrayList<>();
        List<Long> limits = new ArrayList<>();
        try (BufferedReader br = new BufferedReader(new FileReader(args[0]))) {
            String line;
            while ((line = br.readLine()) != null) {
                line = line.trim();
                if (line.isEmpty() || line.startsWith("#")) {
                    continue;
                }
                long lim = BODY_LIMIT;
                if (line.contains(":")) {
                    String[] parts = line.split(":");
                    line = parts[0];
                    lim = Long.parseLong(parts[1].replaceFirst("^0x", ""), 16);
                }
                entries.add(Long.parseLong(line.replaceFirst("^0x", ""), 16));
                limits.add(lim);
            }
        }
        File outDir = new File(args[1]);
        outDir.mkdirs();
        Listing listing = currentProgram.getListing();

        // Pass 1: create every function so the decompiler snapshot sees them all.
        int created = 0;
        for (long a : entries) {
            Address addr = currentProgram.getAddressFactory()
                    .getDefaultAddressSpace().getAddress(a);
            if (listing.getFunctionAt(addr) == null) {
                try {
                    listing.createFunction(String.format("f_%08x", a), addr,
                            new AddressSet(addr), SourceType.USER_DEFINED);
                    created++;
                } catch (Exception e) {
                    println("createFunction failed at " + addr + ": " + e);
                }
            }
        }
        println("functions created: " + created + " of " + entries.size());

        // Pass 2: exact body + decompile.
        DecompInterface decomp = new DecompInterface();
        decomp.toggleCCode(true);
        decomp.setSimplificationStyle("decompile");
        if (!decomp.openProgram(currentProgram)) {
            println("decompiler openProgram failed");
            return;
        }
        PrintWriter idx = new PrintWriter(new File(outDir, "index.csv"));
        idx.println("addr,ok,insns,bytes,error");
        int ok = 0, fail = 0;
        for (int ei = 0; ei < entries.size(); ei++) {
            long a = entries.get(ei);
            long lim = limits.get(ei);
            String hex = String.format("%08x", a);
            Address addr = currentProgram.getAddressFactory()
                    .getDefaultAddressSpace().getAddress(a);
            Function fn = listing.getFunctionAt(addr);
            if (fn == null) {
                idx.println(hex + ",0,0,0,no_function");
                fail++;
                continue;
            }
            AddressSet body = new AddressSet();
            Address cur = addr;
            int insns = 0;
            while (true) {
                Instruction insn = listing.getInstructionAt(cur);
                if (insn == null) {
                    break;
                }
                body.add(cur, insn.getMaxAddress());
                insns++;
                Function owner = listing.getFunctionContaining(insn.getMaxAddress().add(1));
                if (owner != null && !owner.getEntryPoint().equals(addr)) {
                    break;
                }
                cur = insn.getMaxAddress().add(1);
                if (cur.getOffset() - addr.getOffset() > lim) {
                    break;
                }
            }
            if (body.isEmpty()) {
                idx.println(hex + ",0,0,0,no_instruction");
                fail++;
                continue;
            }
            fn.setBody(body);
            DecompileResults res = decomp.decompileFunction(fn, 120, monitor);
            if (!res.decompileCompleted() || res.getDecompiledFunction() == null) {
                idx.println(hex + ",0," + insns + "," + body.getNumAddresses()
                        + ",\"" + String.valueOf(res.getErrorMessage()).replace("\"", "'") + "\"");
                fail++;
                continue;
            }
            String c = res.getDecompiledFunction().getC();
            try (PrintWriter pw = new PrintWriter(new File(outDir, "fn_" + hex + ".c"))) {
                pw.println("// " + fn.getName() + " @ " + addr);
                pw.print(c);
            }
            idx.println(hex + ",1," + insns + "," + body.getNumAddresses() + ",");
            ok++;
            if ((ok + fail) % 100 == 0) {
                println("progress: " + (ok + fail) + "/" + entries.size()
                        + " ok=" + ok + " fail=" + fail);
            }
        }
        idx.close();
        decomp.dispose();
        println("decompiled ok=" + ok + " fail=" + fail + " -> " + outDir);
    }
}
