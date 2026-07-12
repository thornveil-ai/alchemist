/* leaf-bench subject: negate_all (category: uncovered) */
#include <stdint.h>
void negate_all(int *a, int n) {
    for (int i = 0; i < n; i++) a[i] = -a[i];
}
