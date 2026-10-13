// RetryDecompile.java — close the remaining decompiler failures.
// For each address: ensure instructions exist (disassemble if needed),
// ensure a function exists (create if needed), then decompile trying the
// default simplification style followed by "normalize" and "firstpass".
// Usage: analyzeHeadless ... -postScript RetryDecompile.java <addrlist> <outdir>
//   <addrlist> = comma-separated hex addresses (no 0x needed)
// @category Analysis

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;

import java.io.File;
import java.io.PrintWriter;

public class RetryDecompile extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        // analyzeHeadless splits script args on commas/semicolons — take a
        // FILE with one address per line instead.
        java.util.List<String> addrList = new java.util.ArrayList<>();
        for (String line : java.nio.file.Files.readAllLines(
                java.nio.file.Paths.get(args[0]))) {
            line = line.trim();
            if (!line.isEmpty()) addrList.add(line);
        }
        File outDir = new File(args[1]);
        outDir.mkdirs();

        for (String a : addrList) {
            a = a.trim().toLowerCase();
            if (a.isEmpty()) continue;
            Address addr = currentProgram.getAddressFactory()
                    .getDefaultAddressSpace().getAddress(Long.parseLong(a, 16));

            // 1) ensure instruction(s) at the address
            Instruction ins = getInstructionAt(addr);
            if (ins == null) {
                try {
                    disassemble(addr);
                } catch (Exception e) {
                    println(a + " DISASM_FAIL " + e.getMessage());
                    continue;
                }
                ins = getInstructionAt(addr);
            }
            if (ins == null) {
                println(a + " STILL_NO_INSTRUCTION");
                continue;
            }

            // 2) ensure a function exists
            Function fn = getFunctionAt(addr);
            if (fn == null) {
                try {
                    fn = createFunction(addr, null);
                } catch (Exception e) {
                    println(a + " CREATE_FN_FAIL " + e.getMessage());
                }
            }
            if (fn == null) {
                fn = getFunctionContaining(addr);
            }
            if (fn == null) {
                println(a + " NO_FUNCTION");
                continue;
            }

            // 3) decompile with style fallbacks
            String[] styles = {"decompile", "normalize", "firstpass"};
            boolean ok = false;
            for (String style : styles) {
                DecompInterface dc = new DecompInterface();
                dc.setSimplificationStyle(style);
                if (!dc.openProgram(currentProgram)) {
                    println(a + " OPEN_FAIL");
                    break;
                }
                DecompileResults res = dc.decompileFunction(fn, 60, monitor);
                dc.dispose();
                String code = res.getDecompiledFunction() != null
                        ? res.getDecompiledFunction().getC() : null;
                if (res.decompileCompleted() && code != null) {
                    File out = new File(outDir, "fn_" + a + ".c");
                    try (PrintWriter pw = new PrintWriter(out)) {
                        pw.println("// " + fn.getName() + " @ " + a
                                + "  [style=" + style + "]");
                        pw.println(code);
                    }
                    println(a + " OK style=" + style + " -> " + out.getPath());
                    ok = true;
                    break;
                }
                println(a + " style=" + style + " failed: "
                        + (res.getErrorMessage() == null ? "?" : res.getErrorMessage()));
            }
            if (!ok) {
                println(a + " ALL_STYLES_FAILED");
            }
        }
        println("RETRY_DONE");
    }
}
