#![allow(dead_code, clippy::needless_range_loop, unused_variables)]
// Auto-onboarded from 1 source file(s). Tables/consts are data; functions for the model.



pub fn siphash(in_data: &[u8], k: &[u8], outlen: usize) -> Vec<u8> {
    let mut v0: u64 = 0x736f6d6570736575;
    let mut v1: u64 = 0x646f72616e646f6d;
    let mut v2: u64 = 0x6c7967656e657261;
    let mut v3: u64 = 0x7465646279746573;

    let k0 = u64::from_le_bytes(k[0..8].try_into().unwrap());
    let k1 = u64::from_le_bytes(k[8..16].try_into().unwrap());

    v3 ^= k1;
    v2 ^= k0;
    v1 ^= k1;
    v0 ^= k0;

    if outlen == 16 {
        v1 ^= 0xee;
    }

    let inlen = in_data.len();
    let end = inlen - (inlen % 8);
    let mut ni = 0;

    while ni < end {
        let m = u64::from_le_bytes(in_data[ni..ni + 8].try_into().unwrap());
        v3 ^= m;

        for _ in 0..2 {
            v0 = v0.wrapping_add(v1);
            v2 = v2.wrapping_add(v3);
            v1 = v1.rotate_left(13) ^ v0;
            v3 = v3.rotate_left(16) ^ v2;
            v0 = v0.rotate_left(32);
            v2 = v2.wrapping_add(v1);
            v0 = v0.wrapping_add(v3);
            v1 = v1.rotate_left(17) ^ v2;
            v3 = v3.rotate_left(21) ^ v0;
            v2 = v2.rotate_left(32);
        }

        v0 ^= m;
        ni += 8;
    }

    let left = inlen & 7;
    let mut b = ((inlen as u64) << 56);
    for i in 0..left {
        b |= (in_data[ni + i] as u64) << (i * 8);
    }

    v3 ^= b;

    for _ in 0..2 {
        v0 = v0.wrapping_add(v1);
        v2 = v2.wrapping_add(v3);
        v1 = v1.rotate_left(13) ^ v0;
        v3 = v3.rotate_left(16) ^ v2;
        v0 = v0.rotate_left(32);
        v2 = v2.wrapping_add(v1);
        v0 = v0.wrapping_add(v3);
        v1 = v1.rotate_left(17) ^ v2;
        v3 = v3.rotate_left(21) ^ v0;
        v2 = v2.rotate_left(32);
    }

    v0 ^= b;

    if outlen == 16 {
        v2 ^= 0xee;
    } else {
        v2 ^= 0xff;
    }

    for _ in 0..4 {
        v0 = v0.wrapping_add(v1);
        v2 = v2.wrapping_add(v3);
        v1 = v1.rotate_left(13) ^ v0;
        v3 = v3.rotate_left(16) ^ v2;
        v0 = v0.rotate_left(32);
        v2 = v2.wrapping_add(v1);
        v0 = v0.wrapping_add(v3);
        v1 = v1.rotate_left(17) ^ v2;
        v3 = v3.rotate_left(21) ^ v0;
        v2 = v2.rotate_left(32);
    }

    let mut out = Vec::with_capacity(outlen);
    let b_final = v0 ^ v1 ^ v2 ^ v3;
    out.extend_from_slice(&b_final.to_le_bytes());

    if outlen == 16 {
        v1 ^= 0xdd;
        for _ in 0..4 {
            v0 = v0.wrapping_add(v1);
            v2 = v2.wrapping_add(v3);
            v1 = v1.rotate_left(13) ^ v0;
            v3 = v3.rotate_left(16) ^ v2;
            v0 = v0.rotate_left(32);
            v2 = v2.wrapping_add(v1);
            v0 = v0.wrapping_add(v3);
            v1 = v1.rotate_left(17) ^ v2;
            v3 = v3.rotate_left(21) ^ v0;
            v2 = v2.rotate_left(32);
        }
        let b_final2 = v0 ^ v1 ^ v2 ^ v3;
        out.extend_from_slice(&b_final2.to_le_bytes());
    }

    out
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn t_siphash_0(){ assert_eq!(siphash(&[], &[]).as_slice(), &[]); }
    #[test]
    fn t_siphash_1(){ assert_eq!(siphash(&[0], &[0]).as_slice(), &[]); }
    #[test]
    fn t_siphash_2(){ assert_eq!(siphash(&[97, 98, 99], &[97, 98, 99]).as_slice(), &[]); }
    #[test]
    fn t_siphash_3(){ assert_eq!(siphash(&[49, 50, 51, 52, 53, 54, 55, 56, 57], &[49, 50, 51, 52, 53, 54, 55, 56, 57]).as_slice(), &[]); }
    #[test]
    fn t_siphash_4(){ assert_eq!(siphash(&[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19], &[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19]).as_slice(), &[]); }
    #[test]
    fn t_siphash_5(){ assert_eq!(siphash(&[84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120], &[84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120]).as_slice(), &[]); }
    #[test]
    fn t_siphash_6(){ assert_eq!(siphash(&[11], &[11]).as_slice(), &[]); }
    #[test]
    fn t_siphash_7(){ assert_eq!(siphash(&[11, 48, 85, 122, 159, 196, 233], &[11, 48, 85, 122, 159, 196, 233]).as_slice(), &[]); }
    #[test]
    fn t_siphash_8(){ assert_eq!(siphash(&[11, 48, 85, 122, 159, 196, 233, 14, 51, 88, 125, 162, 199, 236, 17, 54, 91, 128, 165, 202, 239, 20, 57, 94, 131, 168, 205, 242, 23, 60, 97], &[11, 48, 85, 122, 159, 196, 233, 14, 51, 88, 125, 162, 199, 236, 17, 54, 91, 128, 165, 202, 239, 20, 57, 94, 131, 168, 205, 242, 23, 60, 97]).as_slice(), &[]); }
    #[test]
    fn t_siphash_9(){ assert_eq!(siphash(&[11, 48, 85, 122, 159, 196, 233, 14, 51, 88, 125, 162, 199, 236, 17, 54, 91, 128, 165, 202, 239, 20, 57, 94, 131, 168, 205, 242, 23, 60, 97, 134, 171, 208, 245, 26, 63, 100, 137, 174, 211, 248, 29, 66, 103, 140, 177, 214, 251, 32, 69, 106, 143, 180, 217, 254, 35, 72, 109, 146, 183, 220, 1, 38], &[11, 48, 85, 122, 159, 196, 233, 14, 51, 88, 125, 162, 199, 236, 17, 54, 91, 128, 165, 202, 239, 20, 57, 94, 131, 168, 205, 242, 23, 60, 97, 134, 171, 208, 245, 26, 63, 100, 137, 174, 211, 248, 29, 66, 103, 140, 177, 214, 251, 32, 69, 106, 143, 180, 217, 254, 35, 72, 109, 146, 183, 220, 1, 38]).as_slice(), &[]); }
    #[test]
    fn t_siphash_10(){ assert_eq!(siphash(&[11, 48, 85, 122, 159, 196, 233, 14, 51, 88, 125, 162, 199, 236, 17, 54, 91, 128, 165, 202, 239, 20, 57, 94, 131, 168, 205, 242, 23, 60, 97, 134, 171, 208, 245, 26, 63, 100, 137, 174, 211, 248, 29, 66, 103, 140, 177, 214, 251, 32, 69, 106, 143, 180, 217, 254, 35, 72, 109, 146, 183, 220, 1, 38, 75, 112, 149, 186, 223, 4, 41, 78, 115, 152, 189, 226, 7, 44, 81, 118, 155, 192, 229, 10, 47, 84, 121, 158, 195, 232, 13, 50, 87, 124, 161, 198, 235, 16, 53, 90], &[11, 48, 85, 122, 159, 196, 233, 14, 51, 88, 125, 162, 199, 236, 17, 54, 91, 128, 165, 202, 239, 20, 57, 94, 131, 168, 205, 242, 23, 60, 97, 134, 171, 208, 245, 26, 63, 100, 137, 174, 211, 248, 29, 66, 103, 140, 177, 214, 251, 32, 69, 106, 143, 180, 217, 254, 35, 72, 109, 146, 183, 220, 1, 38, 75, 112, 149, 186, 223, 4, 41, 78, 115, 152, 189, 226, 7, 44, 81, 118, 155, 192, 229, 10, 47, 84, 121, 158, 195, 232, 13, 50, 87, 124, 161, 198, 235, 16, 53, 90]).as_slice(), &[]); }
}
