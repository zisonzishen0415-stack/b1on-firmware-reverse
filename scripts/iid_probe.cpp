// Brute-force probe: which (class UID order, interface IID order) pair
// instantiates the AmpNeve VST3 in this JUCE build? Prints every combo.
#include <cstdio>
#include <cstring>
#include <windows.h>
#include "public.sdk/source/vst/hosting/module.h"
#include "pluginterfaces/vst/ivstaudioprocessor.h"
#include "pluginterfaces/vst/ivstcomponent.h"
#include "pluginterfaces/vst/ivsteditcontroller.h"
#include "pluginterfaces/vst/ivsthostapplication.h"
#include "pluginterfaces/base/ipluginbase.h"

using namespace Steinberg;
using namespace Steinberg::Vst;

static int hexVal(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}
namespace Steinberg {
FUID::FUID() { for (int i = 0; i < 16; ++i) data[i] = 0; }
bool FUID::fromString(const char* s) {
    if (!s) return false;
    for (int i = 0; i < 16; ++i) {
        int hi = hexVal(s[2 * i]), lo = hexVal(s[2 * i + 1]);
        if (hi < 0 || lo < 0) return false;
        data[i] = (char)((hi << 4) | lo);
    }
    return true;
}
void FUID::toString(char* s) const {
    for (int i = 0; i < 16; ++i) sprintf(s + 2 * i, "%02X", (unsigned char)data[i]);
    s[32] = 0;
}
bool FUID::isValid() const {
    for (int i = 0; i < 16; ++i) if (data[i]) return true;
    return false;
}
}

static void hexToBytes(const char* h, char* out) {
    for (int k = 0; k < 16; ++k)
        out[k] = (char)((hexVal(h[2 * k]) << 4) | hexVal(h[2 * k + 1]));
}

static void reverseGroups(const char* in, char* out) {
    char b[16]; hexToBytes(in, b);
    for (int g = 0; g < 4; ++g)
        for (int k = 0; k < 4; ++k)
            out[g * 4 + k] = b[g * 4 + (3 - k)];
}

int main(int argc, char** argv) {
    if (argc < 2) return 2;
    HMODULE mod = LoadLibraryA(argv[1]);
    if (!mod) { printf("LoadLibrary fail %lu\n", GetLastError()); return 2; }
    auto getFactory = (IPluginFactory * (*)()) GetProcAddress(mod, "GetPluginFactory");
    IPluginFactory* f = getFactory();
    PClassInfo info;
    f->getClassInfo(0, &info);
    char infoHex[33];
    for (int k = 0; k < 16; ++k) sprintf(infoHex + 2 * k, "%02x", (unsigned char)info.cid[k]);
    infoHex[32] = 0;
    printf("getClassInfo cid = %s\n", infoHex);

    struct { const char* name; char bytes[16]; } classes[4];
    hexToBytes(infoHex, classes[0].bytes); classes[0].name = "info2";
    reverseGroups(infoHex, classes[1].bytes); classes[1].name = "groupRev";
    for (int k = 0; k < 16; ++k) classes[2].bytes[k] = info.cid[15 - k];
    classes[2].name = "fullRev";
    // moduleinfo.json CID (hardcoded for AmpNeve)
    hexToBytes("ABCDEF019182FAEB416D4E76416D4E76", classes[3].bytes); classes[3].name = "json";

    const char* iidList[8];
    iidList[0] = "42043F99B7DA453CA569E79D9AAEC33D"; /* IAudioProcessor canonical */
    iidList[1] = "993F04423C45DAB79DE769A53DC3AE9A"; /* IAudioProcessor LE */
    iidList[2] = "E831FF31F2D54301928EBBEE25697802"; /* IComponent canonical */
    iidList[3] = "31FF31E80143D5F2EEBB922802697825"; /* IComponent LE */
    iidList[4] = "01efcdab8291ebfa416d4e76416d4e76"; /* class UID info2 */
    iidList[5] = "ABCDEF019182FAEB416D4E76416D4E76"; /* class UID json */
    iidList[6] = "0000000000000000C000000000000046"; /* FUnknown canonical */
    iidList[7] = "000000000000000046000000000000C0"; /* FUnknown LE */

    for (int c = 0; c < 4; ++c) {
        for (int i = 0; i < 8; ++i) {
            char iid[16];
            hexToBytes(iidList[i], iid);
            FUnknown* out = nullptr;
            tresult r = f->createInstance(classes[c].bytes, iid, (void**)&out);
            if (r == kResultOk)
                printf("OK   class=%-8s iid=%s\n", classes[c].name, iidList[i]);
            else
                printf("fail class=%-8s iid=%s r=%d\n", classes[c].name, iidList[i], (int)r);
        }
    }
    return 0;
}
