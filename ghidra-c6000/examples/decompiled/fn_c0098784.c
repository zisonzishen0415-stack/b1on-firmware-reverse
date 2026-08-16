// f_c0098784 @ c0098784

/* WARNING: Control flow encountered bad instruction data */
/* WARNING: Removing unreachable block (ram,0xc007ff00) */
/* WARNING: Removing unreachable block (ram,0xc007ff2c) */
/* WARNING: Removing unreachable block (ram,0xc007fdb4) */
/* WARNING: Removing unreachable block (ram,0xc007ff88) */
/* WARNING: Removing unreachable block (ram,0xc007ff58) */

uint * f_c0098784(undefined4 param_1,undefined4 *param_2,uint *param_3,uint *param_4,int param_5,
                 undefined4 param_6,undefined4 param_7,undefined4 param_8)

{
  char cVar1;
  byte bVar2;
  uint *in_A1;
  byte bVar3;
  undefined4 in_A2;
  byte bVar4;
  uint uVar5;
  uint *puVar6;
  byte *pbVar7;
  byte *pbVar8;
  int in_A5;
  byte bVar9;
  int iVar10;
  undefined4 *in_A7;
  undefined4 in_A9;
  int in_A22;
  uint *in_A23;
  int in_A24;
  undefined4 in_A25;
  int in_A31;
  uint uVar11;
  byte *pbVar12;
  char *in_B5;
  int iVar13;
  int in_B14;
  BADSPACEBASE *in_B15;
  undefined1 *puVar14;
  int in_B17;
  int in_B18;
  int in_B19;
  int in_B20;
  
  uVar5 = 0xc0098788;
  pbVar8 = (byte *)func_0xc00c7560();
  puVar14 = (undefined1 *)((int)in_B15 + -0x20);
  if (param_2 == (undefined4 *)0x0) {
    *(uint **)((int)pbVar8 * 0x2c + 0xb370) = param_3;
    if ((param_4 == (uint *)0x0) || ((1 << (int)pbVar8 & uRam0000b23c) == 0)) {
      func_0xc00c7540();
      func_0xc00c7560();
                    /* WARNING: Bad instruction - Truncating control flow here */
      halt_baddata();
    }
    iVar13 = func_0xc008946c(pbVar8);
    if (param_2 == (undefined4 *)0x1) {
                    /* WARNING: Bad instruction - Truncating control flow here */
      halt_baddata();
    }
    if (iVar13 == 4 && param_2 == (undefined4 *)0x9) {
      iVar13 = func_0xc00894d4(pbVar8);
      if (iVar13 == 0) {
                    /* WARNING: Bad instruction - Truncating control flow here */
        halt_baddata();
      }
                    /* WARNING: Bad instruction - Truncating control flow here */
      halt_baddata();
    }
                    /* WARNING: Bad instruction - Truncating control flow here */
    halt_baddata();
  }
  if (param_2 == (undefined4 *)0x1) {
    *(char *)(*(ushort *)(in_A5 + 2) + 0x8540) = (char)*(undefined2 *)(in_A5 + 1);
                    /* WARNING: Bad instruction - Truncating control flow here */
    halt_baddata();
  }
  puVar6 = param_3;
  if ((int)param_2 - 2U < 9) {
                    /* WARNING: Bad instruction - Truncating control flow here */
    halt_baddata();
  }
  while( true ) {
    while( true ) {
      while( true ) {
        while( true ) {
          bVar9 = (byte)param_3;
          bVar3 = (byte)in_A2;
          if (in_A1 == (uint *)0x0) {
            func_0xc00c7540(param_8);
            return (uint *)0x0;
          }
          uVar11 = *(uint *)(pbVar8 + 0x20);
          if ((*puVar6 & 4) != 0) {
                    /* WARNING: Bad instruction - Truncating control flow here */
            halt_baddata();
          }
          if ((*puVar6 & 8) == 0) break;
          param_3 = param_4;
          func_0xc007f894(puVar6,0x23);
          in_A1 = (uint *)0x0;
          param_4 = param_3;
        }
        in_A1 = (uint *)0x0;
        if (uVar11 >> 0xe != 0) {
                    /* WARNING: Bad instruction - Truncating control flow here */
          halt_baddata();
        }
        if (uVar11 >> 0xd == 0) break;
        in_A7 = param_2;
        if (iRam00000ed8 == 0) {
          *param_4 = 0;
          *param_2 = 0xffffffff;
          iRam00000ed8 = 1;
          uRam00000ee4 = 0;
        }
        else {
          in_B5[0] = '\0';
          in_B5[1] = '\0';
          in_B5[2] = '\x04';
          in_B5[3] = '\0';
          *param_4 = 2;
          *param_2 = 0xffffffff;
        }
      }
      if ((uVar11 & 1) == 0) break;
      in_A1 = param_4;
      func_0xc007f9ec();
      param_4 = in_A1;
    }
    if (uVar11 >> 0x16 != 0) {
                    /* WARNING: Bad instruction - Truncating control flow here */
      halt_baddata();
    }
    if (uVar11 >> 0x15 != 0) {
                    /* WARNING: Bad instruction - Truncating control flow here */
      halt_baddata();
    }
    if (uVar11 >> 0x14 != 0) {
                    /* WARNING: Bad instruction - Truncating control flow here */
      halt_baddata();
    }
    if (uVar11 >> 0x13 != 0) {
                    /* WARNING: Bad instruction - Truncating control flow here */
      halt_baddata();
    }
    if ((uVar11 & 2) != 0) {
      func_0xc009ff34();
      iVar13 = func_0xc008b318(0);
      if (iVar13 != iVar13 + -1) {
        func_0xc008becc(1);
        func_0xc008beb8();
                    /* WARNING: Bad instruction - Truncating control flow here */
        halt_baddata();
      }
      func_0xc008beb8();
      func_0xc008e3c0(1);
                    /* WARNING: Bad instruction - Truncating control flow here */
      halt_baddata();
    }
    if ((uVar11 & 4) != 0) break;
    if ((uVar11 & 8) != 0) {
      return puVar6;
    }
    if (uVar11 >> 0x1b != 0) {
      if ((iRam000016f4 == 0) && (-1 < iRam000016fc)) {
        iRam000016fc = 0;
        *param_4 = 7;
        *param_2 = 0x84;
      }
                    /* WARNING: Bad instruction - Truncating control flow here */
      halt_baddata();
    }
    if (uVar11 >> 10 != 0) {
                    /* WARNING: Bad instruction - Truncating control flow here */
      halt_baddata();
    }
    if (uVar11 >> 0xf != 0) {
      in_B5[0] = '\0';
      in_B5[1] = '\0';
      in_B5[2] = '\x01';
      in_B5[3] = '\0';
      *param_4 = 1;
                    /* WARNING: Bad instruction - Truncating control flow here */
      halt_baddata();
    }
    if ((*puVar6 & 1) == 0) {
      if ((*puVar6 & 2) == 0) {
                    /* WARNING: Bad instruction - Truncating control flow here */
        halt_baddata();
      }
      param_3 = param_4;
      func_0xc007f894(puVar6,0x21);
      param_4 = param_3;
    }
    else {
      param_3 = param_4;
      func_0xc007f894(puVar6,0x20);
      in_A1 = (uint *)0x1;
      param_4 = param_3;
    }
  }
  pbVar12 = *(byte **)(puVar14 + 8);
  if (pbVar12 == (byte *)0x0 && *(int *)(puVar14 + 3) == 0) {
    if (((int)param_4 + 1 < 7) && (param_2 != (undefined4 *)0x0)) {
                    /* WARNING: Bad instruction - Truncating control flow here */
      halt_baddata();
    }
                    /* WARNING: Bad instruction - Truncating control flow here */
    halt_baddata();
  }
  iVar13 = (int)(pbVar8 + 0x20) >> 3;
  uVar11 = uVar5 & 7;
  if ((int)uVar5 >> 3 != iVar13) {
    if ((int)uVar5 >> 3 <= iVar13) {
                    /* WARNING: Bad instruction - Truncating control flow here */
      halt_baddata();
    }
                    /* WARNING: Bad instruction - Truncating control flow here */
    halt_baddata();
  }
  func_0xc0084020();
  bVar4 = (byte)uVar5;
  pbVar7 = (byte *)func_0xc00b4c24();
  if (pbVar8 != pbVar7) {
    pbVar7 = (byte *)func_0xc00b4af4();
  }
  if (*(int *)(in_B14 + 0x22) != 9) {
                    /* WARNING: Bad instruction - Truncating control flow here */
    halt_baddata();
  }
  while( true ) {
    if (in_A31 == 4) {
      bVar2 = (byte)-(in_B17 >> 0x1f);
      if (-(in_B17 >> 0x1f) == 0) {
        bVar2 = 0xaa;
      }
      *pbVar7 = bVar4 & bVar2 | (byte)((uint)in_B17 >> 0x1f) & ~bVar4;
    }
    if (in_A31 == 0) {
      *pbVar7 = bVar4 | *pbVar7;
    }
    puVar6 = (uint *)(pbVar7 + 0x80);
    if (in_A31 == 4) {
      return puVar6;
    }
    if ((int)in_A7 < param_5) {
      puVar6 = (uint *)(pbVar7 + 0x100);
      *(byte *)puVar6 = bVar9;
    }
    if (in_A31 == 0) {
      *(byte *)puVar6 = bVar3 | (byte)*puVar6;
    }
    else if (in_A31 == 4) {
                    /* WARNING: Bad instruction - Truncating control flow here */
      halt_baddata();
    }
    in_B17 = (in_B17 + 1) * 0x8000 >> 0x1f;
    if (in_B20 < in_B17) break;
    pbVar7 = pbVar12;
    if (in_A31 != 4 && in_A31 != 0) {
      *pbVar12 = bVar4 & *pbVar12;
    }
  }
  if ((int)(((uint)((int)(in_B18 - uVar11) >> 2) >> 0x1d) + (in_B18 - uVar11)) >> 3 <=
      (int)(((uint)((int)(uVar11 + in_B19) >> 2) >> 0x1d) + uVar11 + in_B19) >> 3) {
                    /* WARNING: Bad instruction - Truncating control flow here */
    halt_baddata();
  }
  do {
    iVar10 = in_A22;
    func_0xc007b664(puVar6,0);
    in_A22 = iVar10 + 5;
    puVar6 = in_A23;
    while( true ) {
      cVar1 = *(char *)(in_A24 + 1);
      if (cVar1 == '\0') {
                    /* WARNING: Bad instruction - Truncating control flow here */
        halt_baddata();
      }
      if (cVar1 == '\t') {
        do {
          func_0xc007b860(in_A9,(iVar13 << 7) >> 0x1f);
          in_B5 = in_B5 + 1;
          cVar1 = *in_B5;
          if (cVar1 == '\0') {
                    /* WARNING: Bad instruction - Truncating control flow here */
            halt_baddata();
          }
        } while (cVar1 == '\t');
        if (cVar1 != '\f') {
          func_0xc0082f60();
                    /* WARNING: Bad instruction - Truncating control flow here */
          halt_baddata();
        }
                    /* WARNING: Bad instruction - Truncating control flow here */
        halt_baddata();
      }
      in_A23 = puVar6;
      if (cVar1 == '\f') break;
      func_0xc007b664(puVar6,(char *)(in_A24 + 1),iVar10,in_A25);
      iVar10 = in_A22;
      in_A22 = iVar10;
    }
  } while( true );
}


