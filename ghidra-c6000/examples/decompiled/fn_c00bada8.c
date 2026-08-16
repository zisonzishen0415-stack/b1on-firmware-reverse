// f_c00bada8 @ c00bada8

void f_c00bada8(undefined4 param_1,int param_2)

{
  int iVar1;
  uint uVar2;
  
  iVar1 = func_0xc00c7560();
  if (*(int *)(iVar1 + 2) != param_2) {
    if (*(code **)(iVar1 + 7) != (code *)0x0) {
                    /* WARNING: Could not recover jumptable at 0xc00badc4. Too many branches */
                    /* WARNING: Treating indirect jump as call */
      (**(code **)(iVar1 + 7))();
      return;
    }
    if (*(int *)(iVar1 + 9) == 0) {
      (*(code *)0x0)();
      return;
    }
  }
  *(int *)(iVar1 + 2) = param_2;
  uVar2 = func_0xc009ff94();
  if (uVar2 == 1) {
    func_0xc009ff94();
    uVar2 = func_0xc00b1518();
    uVar2 = uVar2 >> 0x18 & 1;
  }
  func_0xc009ffb0(uVar2);
  func_0xc00c8480();
  func_0xc00c7540();
  uRam0000bbe8 = 1;
  uRam0000bbea = 2;
  return;
}


