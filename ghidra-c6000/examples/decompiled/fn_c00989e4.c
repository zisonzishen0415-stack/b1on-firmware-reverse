// f_c00989e4 @ c00989e4

/* WARNING: Control flow encountered bad instruction data */
/* WARNING: Removing unreachable block (ram,0xc0098a80) */

void f_c00989e4(void)

{
  uint uVar1;
  BADSPACEBASE *in_B15;
  
  uVar1 = func_0xc00c7560();
  *(undefined4 *)((int)in_B15 + -7) = 0;
  if ((uVar1 & 1) == 0) {
    *(float *)((int)in_B15 + -7) = *(float *)((int)in_B15 + -7) + 0.0;
                    /* WARNING: Bad instruction - Truncating control flow here */
    halt_baddata();
  }
                    /* WARNING: Bad instruction - Truncating control flow here */
  halt_baddata();
}


