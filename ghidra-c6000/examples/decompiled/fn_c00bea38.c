// f_c00bea38 @ c00bea38

void f_c00bea38(void)

{
  int iVar1;
  int *piVar2;
  int iVar3;
  undefined4 uVar4;
  int iVar5;
  undefined4 *puVar6;
  undefined4 uVar7;
  
  iVar1 = func_0xc00c7560();
  uVar4 = 0x2a0;
  puVar6 = (undefined4 *)0xd528;
  iVar5 = 5;
  uVar7 = 0x6840;
  iVar3 = 0xd510;
  do {
    func_0xc00c1840(iVar1,0);
    iVar1 = *(int *)(iVar3 + 1);
    func_0xc00c1840();
    puVar6 = (undefined4 *)((int)puVar6 + 1);
    *puVar6 = uVar7;
    iVar3 = iVar1;
  } while (iVar5 != 1);
  func_0xc00c7560(iVar1,puVar6,uVar4);
  piVar2 = (int *)func_0xc00c7560();
  iVar3 = f_c008940c(*piVar2);
  iVar1 = *piVar2;
  *(undefined4 *)(iVar1 + 0xd528) = *(undefined4 *)(iVar3 + 8);
  piVar2 = (int *)func_0xc00c7540(iVar1,1);
  *(undefined4 *)(*piVar2 + 0xd528) = 0x6844;
  return;
}


