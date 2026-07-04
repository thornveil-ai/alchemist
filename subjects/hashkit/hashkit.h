/* hashkit.h — three standard non-cryptographic checksums.
 *
 *   - fnv1a32():  FNV-1a 32-bit hash (offset 0x811c9dc5, prime 0x01000193).
 *   - crc16_ccitt(): CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF, no reflect).
 *   - bsd_sum16(): the classic BSD 16-bit rotate-and-add checksum.
 */
#ifndef HASHKIT_H
#define HASHKIT_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* FNV-1a 32-bit hash. Seeds internally at the FNV offset basis. */
uint32_t fnv1a32(const uint8_t *buf, size_t len);

/* CRC-16/CCITT-FALSE. Polynomial 0x1021, initial value 0xFFFF, MSB-first,
 * no input/output reflection, no final XOR. */
uint16_t crc16_ccitt(const uint8_t *buf, size_t len);

/* BSD 16-bit checksum: for each byte, rotate the accumulator right by one
 * (within 16 bits) then add the byte, keeping the running value mod 2^16. */
uint16_t bsd_sum16(const uint8_t *buf, size_t len);

#ifdef __cplusplus
}
#endif

#endif /* HASHKIT_H */
