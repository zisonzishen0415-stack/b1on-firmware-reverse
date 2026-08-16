// Deterministically disassemble every executable memory block by parsing
// one instruction at a time with the SLEIGH language (no flow dependency).
// @category Analysis

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.lang.InstructionPrototype;
import ghidra.program.model.lang.Language;
import ghidra.program.model.lang.ProgramProcessorContext;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.mem.MemBuffer;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.mem.MemoryBufferImpl;

public class FullDis extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 1) {
            println("usage: FullDis.java <insn_map.txt>");
            return;
        }
        Language lang = currentProgram.getLanguage();
        Memory mem = currentProgram.getMemory();
        Listing listing = currentProgram.getListing();
        ProgramProcessorContext ctx = new ProgramProcessorContext(
                currentProgram.getProgramContext(),
                currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(0));
        for (MemoryBlock block : currentProgram.getMemory().getBlocks()) {
            if ((block.getFlags() & MemoryBlock.EXECUTE) != 0) {
                listing.clearCodeUnits(block.getStart(), block.getEnd(), false);
            }
        }
        int total = 0;
        java.io.BufferedReader br = new java.io.BufferedReader(
                new java.io.FileReader(args[0]));
        String line;
        while ((line = br.readLine()) != null) {
            line = line.trim();
            if (line.isEmpty()) {
                continue;
            }
            String[] parts = line.split(" ");
            long a = Long.parseLong(parts[0], 16);
            Address addr = currentProgram.getAddressFactory()
                    .getDefaultAddressSpace().getAddress(a);
            if (listing.getInstructionAt(addr) != null) {
                continue;
            }
            try {
                MemBuffer mb = new MemoryBufferImpl(mem, addr);
                InstructionPrototype proto = lang.parse(mb, ctx, true);
                int len = proto.getLength();
                listing.createInstruction(addr, proto, mb, ctx, len);
                total++;
            } catch (Exception e) {
                println("parse failed at " + addr + ": " + e);
            }
        }
        br.close();
        println("created instructions: " + total);
    }
}
