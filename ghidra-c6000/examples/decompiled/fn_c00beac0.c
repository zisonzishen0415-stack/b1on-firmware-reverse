// f_c00beac0 @ c00beac0

void f_c00beac0(void)

{
  int *piVar1;
  int iVar2;
  int iVar3;
  
  piVar1 = (int *)func_0xc00c7560();
  iVar2 = f_c008940c(*piVar1);
  iVar3 = *piVar1;
  *(undefined4 *)(iVar3 + 0xd528) = *(undefined4 *)(iVar2 + 8);
  piVar1 = (int *)func_0xc00c7540(iVar3,1);
  *(undefined4 *)(*piVar1 + 0xd528) = 0x6844;
  return;
}


