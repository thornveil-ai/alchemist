/* leaf-bench subject: sum_array (category: uncovered) */
#include <stdint.h>
long sum_array(const int *a, int n) {
    long s = 0;
    for (int i = 0; i < n; i++) s += a[i];
    return s;
}
