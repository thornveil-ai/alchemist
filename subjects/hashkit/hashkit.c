/* hashkit.c — reference implementations. */

#include "hashkit.h"

uint32_t fnv1a32(const uint8_t *buf, size_t len)
{
    uint32_t h = 0x811c9dc5U;      /* FNV offset basis */
    size_t i;
    for (i = 0; i < len; i++) {
        h ^= (uint32_t)buf[i];
        h *= 0x01000193U;          /* FNV prime */
    }
    return h;
}

uint16_t crc16_ccitt(const uint8_t *buf, size_t len)
{
    uint16_t crc = 0xFFFF;
    size_t i;
    int b;
    for (i = 0; i < len; i++) {
        crc ^= (uint16_t)((uint16_t)buf[i] << 8);
        for (b = 0; b < 8; b++) {
            if (crc & 0x8000)
                crc = (uint16_t)((crc << 1) ^ 0x1021);
            else
                crc = (uint16_t)(crc << 1);
        }
    }
    return crc;
}

uint16_t bsd_sum16(const uint8_t *buf, size_t len)
{
    uint16_t sum = 0;
    size_t i;
    for (i = 0; i < len; i++) {
        sum = (uint16_t)((sum >> 1) | ((sum & 1) << 15));  /* rotate right */
        sum = (uint16_t)(sum + buf[i]);
    }
    return sum;
}
