#include "gen.h"
int weighted_pick(int idx, int scale) {
    if (idx < 0 || idx > 3) {
        return 0;
    }
    return WEIGHTS[idx] * scale;
}
