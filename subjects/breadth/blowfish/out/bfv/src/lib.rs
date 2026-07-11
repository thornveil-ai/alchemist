#![allow(dead_code, non_snake_case, clippy::needless_range_loop, unused_variables)]
#[allow(non_camel_case_types)] pub type BLOWFISH_KEY = BlowfishKey;
pub const P_PERM: [u32; 18] = [608135816, 2242054355, 320440878, 57701188, 2752067618, 698298832, 137296536, 3964562569, 1160258022, 953160567, 3193202383, 887688300, 3232508343, 3380367581, 1065670069, 3041331479, 2450970073, 2306472731];



#[derive(Clone)]
pub struct BlowfishKey {
    pub p: [u32; 18],
    pub s: [[u32; 256]; 4],
}
impl Default for BlowfishKey {
    fn default() -> Self { Self { p: [0; 18], s: [[0; 256]; 4] } }
}

pub fn blowfish_encrypt(sched: &BlowfishKey, block: &[u8]) -> Vec<u8> {
    let mut l = ((block[0] as u32) << 24) | ((block[1] as u32) << 16) | ((block[2] as u32) << 8) | (block[3] as u32);
    let mut r = ((block[4] as u32) << 24) | ((block[5] as u32) << 16) | ((block[6] as u32) << 8) | (block[7] as u32);

    for i in 0..16 {
        l ^= sched.p[i];
        let t = blowfish_f(l, &sched.s);
        r ^= t;
        std::mem::swap(&mut l, &mut r);
    }
    // The loop above performs 16 swaps. The C code does 16 iterations but the last one has no swap.
    // To match the C logic: 16 iterations of (l^=p, r^=f(l), swap), then undo the last swap,
    // then apply the final P-array XORs.
    std::mem::swap(&mut l, &mut r);

    l ^= sched.p[16];
    r ^= sched.p[17];

    vec![
        (l >> 24) as u8,
        (l >> 16) as u8,
        (l >> 8) as u8,
        l as u8,
        (r >> 24) as u8,
        (r >> 16) as u8,
        (r >> 8) as u8,
        r as u8,
    ]
}
pub fn blowfish_key_setup(sched: &mut BlowfishKey, key: &[u8]) {
    sched.p.copy_from_slice(&P_PERM);
    // S_PERM is not provided in scope, but the C code uses s_perm. 
    // Assuming S_PERM is available in the actual environment as P_PERM is.
    sched.s.copy_from_slice(&S_PERM);

    let len = key.len();
    if len > 0 {
        for idx in 0..18 {
            let idx2 = idx * 4;
            let word = ((key[idx2 % len] as u32) << 24)
                | ((key[(idx2 + 1) % len] as u32) << 16)
                | ((key[(idx2 + 2) % len] as u32) << 8)
                | (key[(idx2 + 3) % len] as u32);
            sched.p[idx] ^= word;
        }
    }

    let mut block = [0u8; 8];
    for idx in (0..18).step_by(2) {
        block = blowfish_encrypt(sched, &block).try_into().expect("Invalid block size");
        sched.p[idx] = ((block[0] as u32) << 24) | ((block[1] as u32) << 16) | ((block[2] as u32) << 8) | (block[3] as u32);
        sched.p[idx + 1] = ((block[4] as u32) << 24) | ((block[5] as u32) << 16) | ((block[6] as u32) << 8) | (block[7] as u32);
    }

    for idx in 0..4 {
        for idx2 in (0..256).step_by(2) {
            block = blowfish_encrypt(sched, &block).try_into().expect("Invalid block size");
            sched.s[idx][idx2] = ((block[0] as u32) << 24) | ((block[1] as u32) << 16) | ((block[2] as u32) << 8) | (block[3] as u32);
            sched.s[idx][idx2 + 1] = ((block[4] as u32) << 24) | ((block[5] as u32) << 16) | ((block[6] as u32) << 8) | (block[7] as u32);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn fuzz_bfv() {
        let vectors: &[(&[u8], &[u8])] = &[
        (&[198, 126, 129, 107, 75, 251, 226, 251], &[84, 173, 84, 225, 67, 158, 228, 147]),
        (&[95, 118, 133, 159, 14, 103, 17, 240, 33, 177, 141, 146, 241, 158, 44, 157], &[44, 39, 255, 240, 113, 243, 31, 81]),
        (&[247, 109, 137, 211, 209, 212, 64, 229, 237, 109, 93, 68, 101, 32, 119, 179, 48, 47, 2, 112, 81, 239, 89, 85], &[102, 32, 134, 43, 57, 79, 64, 228]),
        (&[144, 100, 141, 7, 148, 65, 111, 218, 186, 40, 45, 247, 218, 162, 194, 201, 200, 231, 234, 185, 78, 45, 126, 91, 236, 178, 146, 91, 79, 136, 77, 38], &[88, 136, 182, 36, 199, 252, 156, 84]),
        (&[41, 92, 145, 59, 86, 173, 157, 207, 134, 227, 253, 169, 79, 35, 13, 223, 96, 159, 211, 2, 76, 108, 163, 98, 24, 32, 149, 6, 133, 51, 168, 106, 31, 19, 179, 246, 2, 4, 15, 67, 111, 190, 6, 13, 18, 196, 250, 246, 17, 134, 85, 0, 212, 54, 52, 200], &[223, 100, 169, 94, 245, 172, 62, 210])];
        for (key, expected) in vectors {
            let mut sched = BlowfishKey::default();
            blowfish_key_setup(&mut sched, key);
            assert_eq!(blowfish_encrypt(&sched, &[0, 1, 2, 3, 4, 5, 6, 7]).as_slice(), *expected, "keylen {}", key.len());
        }
    }
}
