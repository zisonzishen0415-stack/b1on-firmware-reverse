// Dump raw pcode for a function body and flag ops with overlapping inputs.
// Usage: -postScript RawPcodeDump.java <hexstart> <hexend>
// @category Analysis

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.pcode.PcodeOp;
import ghidra.program.model.pcode.Varnode;

public class RawPcodeDump extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        long start = Long.parseLong(args[0].replaceFirst("^0x", ""), 16);
        long end = Long.parseLong(args[1].replaceFirst("^0x", ""), 16);
        Listing listing = currentProgram.getListing();
        Address a = currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(start);
        Address stop = currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(end);
        while (a != null && a.getOffset() < end) {
            Instruction insn = listing.getInstructionAt(a);
            if (insn == null) {
                a = a.add(2);
                continue;
            }
            PcodeOp[] ops = insn.getPcode();
            for (PcodeOp op : ops) {
                boolean bad = false;
                if (op.getNumInputs() >= 2) {
                    for (int i = 0; i < op.getNumInputs() && !bad; i++) {
                        for (int j = i + 1; j < op.getNumInputs() && !bad; j++) {
                            Varnode v1 = op.getInput(i);
                            Varnode v2 = op.getInput(j);
                            long a1 = v1.getAddress().getOffset();
                            long a2 = v2.getAddress().getOffset();
                            long e1 = a1 + v1.getSize();
                            long e2 = a2 + v2.getSize();
                            if (a1 < e2 && a2 < e1) {
                                bad = true;
                            }
                        }
                    }
                }
                if (bad) {
                    println("OVERLAP @ " + a + "  " + op);
                }
            }
            println(a + "  " + insn);
            a = insn.getMaxAddress().add(1);
        }
    }
}
