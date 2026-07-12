/* leaf-bench subject: imax_array (category: iarray_reduce) */
#include <stdint.h>
int imax_array(const int *a, int n) {
    if (n <= 0) return 0;
    int m = a[0];
    for (int i = 1; i < n; i++) if (a[i] > m) m = a[i];
    return m;
}
