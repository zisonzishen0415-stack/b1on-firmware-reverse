// Dump disassembly of the current program to a text file.
// Usage: analyzeHeadless ... -process <file> -postScript DumpDis.java <outfile>
// @category Analysis

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.SymbolTable;

import java.io.File;
import java.io.PrintWriter;

public class DumpDis extends GhidraScript {
    @Override
    public void run() throws Exception {
        Listing listing = currentProgram.getListing();
        for (MemoryBlock b : currentProgram.getMemory().getBlocks()) {
            println("block " + b.getName() + " " + b.getStart() + " flags=" + b.getFlags());
        }
        SymbolTable st = currentProgram.getSymbolTable();
        var eps = st.getExternalEntryPointIterator();
        while (eps.hasNext()) {
            println("entry: " + eps.next());
        }
        int count = 0;
        StringBuilder sb = new StringBuilder();
        InstructionIterator ii = listing.getInstructions(true);
        while (ii.hasNext()) {
            ii.next();
            count++;
        }
        println("instruction count: " + count);

        String[] args = getScriptArgs();
        String outPath = (args.length > 0) ? args[0] : "dump.dis";
        try (PrintWriter pw = new PrintWriter(new File(outPath))) {
            ii = listing.getInstructions(true);
            while (ii.hasNext()) {
                Instruction insn = ii.next();
                pw.printf("%08x  %s%n", insn.getAddress().getOffset(), insn);
            }
        }
        println("wrote " + outPath);
    }
}
