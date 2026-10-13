// Clear code units in given address ranges so the decompiler stops treating
// embedded data tables as instructions.
// Usage: -postScript MarkData.java <ranges.txt>
//   ranges.txt: one "startHEX endHEX" pair per line (8 hex digits each,
//   end exclusive), '#' comments allowed.
// @category Analysis

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Listing;

import java.io.BufferedReader;
import java.io.FileReader;

public class MarkData extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 1) {
            println("usage: MarkData.java <ranges.txt>");
            return;
        }
        Listing listing = currentProgram.getListing();
        int n = 0;
        try (BufferedReader br = new BufferedReader(new FileReader(args[0]))) {
            String line;
            while ((line = br.readLine()) != null) {
                line = line.trim();
                if (line.isEmpty() || line.startsWith("#")) {
                    continue;
                }
                String[] parts = line.split("\\s+");
                if (parts.length < 2) {
                    println("bad line: " + line);
                    continue;
                }
                long lo = Long.parseLong(parts[0].replaceFirst("^0x", ""), 16);
                long hi = Long.parseLong(parts[1].replaceFirst("^0x", ""), 16);
                Address a = currentProgram.getAddressFactory()
                        .getDefaultAddressSpace().getAddress(lo);
                Address b = currentProgram.getAddressFactory()
                        .getDefaultAddressSpace().getAddress(hi - 1);
                listing.clearCodeUnits(a, b, false);
                n++;
                println("cleared 0x" + parts[0] + "..0x" + parts[1]);
            }
        }
        println("ranges cleared: " + n);
    }
}
