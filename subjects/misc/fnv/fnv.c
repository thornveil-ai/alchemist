unsigned int fnv1a(const unsigned char *data, unsigned long len) {
    unsigned int h = 2166136261u;
    for (unsigned long i = 0; i < len; i++) { h ^= data[i]; h *= 16777619u; }
    return h;
}
