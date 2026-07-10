//! Murmur3
//!
//! Module containing 7 functions: rotl32, rotl64, fmix32, fmix64,
//! MurmurHash3_x86_32, MurmurHash3_x86_128, MurmurHash3_x64_128

#![allow(unused_variables, unused_imports, dead_code)]

use crate::*;

/// Rotl32
/// Performs a left circular shift (rotation) on a 32-bit unsigned integer.
pub fn rotl32(x: u32, r: u32) -> u32 {
    let r = r % 32;
    if r == 0 {
        return x;
    }
    (x << r) | (x >> (32 - r))
}

/// Rotl64
/// Performs a circular left shift (bit rotation) on a 64-bit unsigned integer.
pub fn rotl64(x: u64, r: u32) -> u64 {
    let r = r % 64;
    if r == 0 {
        return x;
    }
    (x << r) | (x >> (64 - r))
}

/// Fmix32
/// A finalization mix function that forces all bits of a 32-bit hash block to
/// avalanche, ensuring that small changes in the input result in large changes in
/// the output.
///
/// Standards: MurmurHash3
pub fn fmix32(mut h: u32) -> u32 {
    h ^= h >> 16;
    h = h.wrapping_mul(0x85ebca6b);
    h ^= h >> 13;
    h = h.wrapping_mul(0xc2b2ae35);
    h ^= h >> 16;
    h
}

/// Fmix64
/// A finalization mix function used to ensure that the hash value is
/// well-distributed (avoids collisions) by applying a series of XOR-shifts and
/// multiplications.
///
/// Standards: MurmurHash3
pub fn fmix64(mut k: u64) -> u64 {
    k ^= k >> 33;
    k = k.wrapping_mul(0xff51afd7ed558ccd);
    k ^= k >> 33;
    k = k.wrapping_mul(0xc4ceb9fe1a85ec53);
    k ^= k >> 33;
    k
}

/// Murmurhash3 X86 32
/// Implements the 32-bit MurmurHash3 algorithm for x86 architectures, providing a
/// fast, non-cryptographic hash of a byte sequence.
///
/// Standards: MurmurHash3
#[allow(clippy::unimplemented)]
pub fn murmur_hash3_x86_32(key: &[u8], seed: u32) {
    let _ = key;
    let _ = seed;
    unimplemented!("skeleton: murmur_hash3_x86_32 not yet implemented")
}

/// Murmurhash3 X86 128
/// Implements the 128-bit MurmurHash3 algorithm optimized for x86 architectures,
/// producing a high-quality hash from an input byte slice.
///
/// Standards: MurmurHash3 (Austin Appleby)
#[allow(clippy::unimplemented)]
pub fn murmur_hash3_x86_128(key: &[u8], seed: u32, out: &mut [u32; 4]) {
    let _ = key;
    let _ = seed;
    let _ = out;
    unimplemented!("skeleton: murmur_hash3_x86_128 not yet implemented")
}

/// Murmurhash3 X64 128
/// Implements the 128-bit MurmurHash3 algorithm optimized for 64-bit
/// architectures, producing a high-quality non-cryptographic hash of a byte
/// sequence.
///
/// Standards: MurmurHash3 (Austin Appleby)
#[allow(clippy::unimplemented)]
pub fn murmur_hash3_x64_128(key: &[u8], seed: u32, out: &mut [u8; 16]) {
    let _ = key;
    let _ = seed;
    let _ = out;
    unimplemented!("skeleton: murmur_hash3_x64_128 not yet implemented")
}

#[cfg(test)]
mod tests {
    #![allow(unused_imports, unused_variables, unused_macros)]
    extern crate alloc;
    use alloc::format;
    use alloc::string::String;

    #[test]
    fn test_rotl32_spec_0() {
        let x = 0u32;
        let r = 0u32;
        let got = super::rotl32(x, r);
        assert_eq!(got, 0, "scalar_0");
    }

    #[test]
    fn test_rotl32_spec_1() {
        let x = 1u32;
        let r = 1u32;
        let got = super::rotl32(x, r);
        assert_eq!(got, 2, "scalar_1");
    }

    #[test]
    fn test_rotl32_spec_2() {
        let x = 2u32;
        let r = 2u32;
        let got = super::rotl32(x, r);
        assert_eq!(got, 8, "scalar_2");
    }

    #[test]
    fn test_rotl32_spec_3() {
        let x = 3u32;
        let r = 3u32;
        let got = super::rotl32(x, r);
        assert_eq!(got, 24, "scalar_3");
    }

    #[test]
    fn test_rotl32_spec_4() {
        let x = 4294967295u32;
        let r = 4294967295u32;
        let got = super::rotl32(x, r);
        assert_eq!(got, 4294967295, "scalar_4");
    }

    #[test]
    fn test_rotl32_spec_5() {
        let x = 4294967294u32;
        let r = 4294967294u32;
        let got = super::rotl32(x, r);
        assert_eq!(got, 3221225471, "scalar_5");
    }

    #[test]
    fn test_rotl32_spec_6() {
        let x = 2147483647u32;
        let r = 2147483647u32;
        let got = super::rotl32(x, r);
        assert_eq!(got, 3221225471, "scalar_6");
    }

    #[test]
    fn test_rotl32_spec_7() {
        let x = 1431655765u32;
        let r = 1431655765u32;
        let got = super::rotl32(x, r);
        assert_eq!(got, 2863311530, "scalar_7");
    }

    #[test]
    fn test_rotl32_spec_8() {
        let x = 1676950277u32;
        let r = 3684226476u32;
        let got = super::rotl32(x, r);
        assert_eq!(got, 1135629887, "scalar_8");
    }

    #[test]
    fn test_rotl32_spec_9() {
        let x = 374770337u32;
        let r = 3030311702u32;
        let got = super::rotl32(x, r);
        assert_eq!(got, 2823132578, "scalar_9");
    }

    #[test]
    fn test_rotl32_spec_10() {
        let x = 861289767u32;
        let r = 515957865u32;
        let got = super::rotl32(x, r);
        assert_eq!(got, 2893696614, "scalar_10");
    }

    #[test]
    fn test_rotl32_spec_11() {
        let x = 3532597350u32;
        let r = 1696570651u32;
        let got = super::rotl32(x, r);
        assert_eq!(got, 915700035, "scalar_11");
    }

    #[test]
    fn test_rotl32_spec_12() {
        let x = 39654292u32;
        let r = 3374510824u32;
        let got = super::rotl32(x, r);
        assert_eq!(got, 1561564162, "scalar_12");
    }

    #[test]
    fn test_rotl32_spec_13() {
        let x = 3408121133u32;
        let r = 1956481593u32;
        let got = super::rotl32(x, r);
        assert_eq!(got, 1536575386, "scalar_13");
    }

    #[test]
    fn test_rotl32_spec_14() {
        let x = 3241485146u32;
        let r = 948101882u32;
        let got = super::rotl32(x, r);
        assert_eq!(got, 1795478669, "scalar_14");
    }

    #[test]
    fn test_rotl32_spec_15() {
        let x = 3495242951u32;
        let r = 3114109953u32;
        let got = super::rotl32(x, r);
        assert_eq!(got, 2695518607, "scalar_15");
    }

    #[test]
    fn test_rotl32_spec_16() {
        let x = 2357344266u32;
        let r = 385010413u32;
        let got = super::rotl32(x, r);
        assert_eq!(got, 1191268752, "scalar_16");
    }

    #[test]
    fn test_rotl32_spec_17() {
        let x = 1740275586u32;
        let r = 3471785603u32;
        let got = super::rotl32(x, r);
        assert_eq!(got, 1037302803, "scalar_17");
    }

    #[test]
    fn test_rotl32_spec_18() {
        let x = 1800988596u32;
        let r = 783092114u32;
        let got = super::rotl32(x, r);
        assert_eq!(got, 2664541539, "scalar_18");
    }

    #[test]
    fn test_rotl32_spec_19() {
        let x = 498341423u32;
        let r = 619609168u32;
        let got = super::rotl32(x, r);
        assert_eq!(got, 372186548, "scalar_19");
    }

    #[test]
    fn test_rotl32_spec_20() {
        let x = 2614007529u32;
        let r = 3340007993u32;
        let got = super::rotl32(x, r);
        assert_eq!(got, 3543637293, "scalar_20");
    }

    #[test]
    fn test_rotl32_spec_21() {
        let x = 3233287710u32;
        let r = 3092808310u32;
        let got = super::rotl32(x, r);
        assert_eq!(got, 2276470275, "scalar_21");
    }

    #[test]
    fn test_rotl32_spec_22() {
        let x = 3502316727u32;
        let r = 2030553267u32;
        let got = super::rotl32(x, r);
        assert_eq!(got, 3854468616, "scalar_22");
    }

    #[test]
    fn test_rotl32_spec_23() {
        let x = 3150325024u32;
        let r = 2677912710u32;
        let got = super::rotl32(x, r);
        assert_eq!(got, 4052305966, "scalar_23");
    }

    #[test]
    fn test_rotl32_spec_24() {
        let x = 4066313903u32;
        let r = 2860311886u32;
        let got = super::rotl32(x, r);
        assert_eq!(got, 3249274007, "scalar_24");
    }

    #[test]
    fn test_rotl32_spec_25() {
        let x = 471313795u32;
        let r = 1740701840u32;
        let got = super::rotl32(x, r);
        assert_eq!(got, 2911050775, "scalar_25");
    }

    #[test]
    fn test_rotl32_spec_26() {
        let x = 1814133985u32;
        let r = 3898710235u32;
        let got = super::rotl32(x, r);
        assert_eq!(got, 190909415, "scalar_26");
    }

    #[test]
    fn test_rotl32_spec_27() {
        let x = 4062749208u32;
        let r = 1849549605u32;
        let got = super::rotl32(x, r);
        assert_eq!(got, 1158955806, "scalar_27");
    }

    #[test]
    fn test_rotl32_spec_28() {
        let x = 1615906270u32;
        let r = 604387498u32;
        let got = super::rotl32(x, r);
        assert_eq!(got, 1125611905, "scalar_28");
    }

    #[test]
    fn test_rotl32_spec_29() {
        let x = 4051622447u32;
        let r = 1612057427u32;
        let got = super::rotl32(x, r);
        assert_eq!(got, 3514797046, "scalar_29");
    }

    #[test]
    fn test_rotl32_spec_30() {
        let x = 3570690740u32;
        let r = 1088387724u32;
        let got = super::rotl32(x, r);
        assert_eq!(got, 1185631565, "scalar_30");
    }

    #[test]
    fn test_rotl32_spec_31() {
        let x = 2266783129u32;
        let r = 2970590891u32;
        let got = super::rotl32(x, r);
        assert_eq!(got, 3807169592, "scalar_31");
    }

    #[test]
    fn test_rotl32_spec_32() {
        let x = 1089993460u32;
        let r = 2184472783u32;
        let got = super::rotl32(x, r);
        assert_eq!(got, 4252639355, "scalar_32");
    }

    #[test]
    fn test_rotl32_spec_33() {
        let x = 1985075364u32;
        let r = 861216061u32;
        let got = super::rotl32(x, r);
        assert_eq!(got, 2395618068, "scalar_33");
    }

    #[test]
    fn test_rotl32_spec_34() {
        let x = 167080110u32;
        let r = 945124932u32;
        let got = super::rotl32(x, r);
        assert_eq!(got, 2673281760, "scalar_34");
    }

    #[test]
    fn test_rotl32_spec_35() {
        let x = 2561552417u32;
        let r = 2165302682u32;
        let got = super::rotl32(x, r);
        assert_eq!(got, 2254616768, "scalar_35");
    }

    #[test]
    fn test_rotl32_spec_36() {
        let x = 1048458355u32;
        let r = 3426857531u32;
        let got = super::rotl32(x, r);
        assert_eq!(got, 2582901155, "scalar_36");
    }

    #[test]
    fn test_rotl32_spec_37() {
        let x = 571487584u32;
        let r = 1094605008u32;
        let got = super::rotl32(x, r);
        assert_eq!(got, 895492624, "scalar_37");
    }

    #[test]
    fn test_rotl32_spec_38() {
        let x = 438550865u32;
        let r = 153558149u32;
        let got = super::rotl32(x, r);
        assert_eq!(got, 1148725795, "scalar_38");
    }

    #[test]
    fn test_rotl32_spec_39() {
        let x = 392657458u32;
        let r = 2699992688u32;
        let got = super::rotl32(x, r);
        assert_eq!(got, 2050103143, "scalar_39");
    }

    #[test]
    fn test_rotl64_spec_0() {
        let x = 0u64;
        let r = 0u32;
        let got = super::rotl64(x, r);
        assert_eq!(got, 0, "scalar_0");
    }

    #[test]
    fn test_rotl64_spec_1() {
        let x = 1u64;
        let r = 1u32;
        let got = super::rotl64(x, r);
        assert_eq!(got, 2, "scalar_1");
    }

    #[test]
    fn test_rotl64_spec_2() {
        let x = 2u64;
        let r = 2u32;
        let got = super::rotl64(x, r);
        assert_eq!(got, 8, "scalar_2");
    }

    #[test]
    fn test_rotl64_spec_3() {
        let x = 3u64;
        let r = 3u32;
        let got = super::rotl64(x, r);
        assert_eq!(got, 24, "scalar_3");
    }

    #[test]
    fn test_rotl64_spec_4() {
        let x = 18446744073709551615u64;
        let r = 4294967295u32;
        let got = super::rotl64(x, r);
        assert_eq!(got, 18446744073709551615, "scalar_4");
    }

    #[test]
    fn test_rotl64_spec_5() {
        let x = 18446744073709551614u64;
        let r = 4294967294u32;
        let got = super::rotl64(x, r);
        assert_eq!(got, 13835058055282163711, "scalar_5");
    }

    #[test]
    fn test_rotl64_spec_6() {
        let x = 9223372036854775807u64;
        let r = 2147483647u32;
        let got = super::rotl64(x, r);
        assert_eq!(got, 13835058055282163711, "scalar_6");
    }

    #[test]
    fn test_rotl64_spec_7() {
        let x = 6148914691236517205u64;
        let r = 1431655765u32;
        let got = super::rotl64(x, r);
        assert_eq!(got, 12297829382473034410, "scalar_7");
    }

    #[test]
    fn test_rotl64_spec_8() {
        let x = 893830640694475525u64;
        let r = 3684226476u32;
        let got = super::rotl64(x, r);
        assert_eq!(got, 4877487209795794495, "scalar_8");
    }

    #[test]
    fn test_rotl64_spec_9() {
        let x = 1834525367383526049u64;
        let r = 3030311702u32;
        let got = super::rotl64(x, r);
        assert_eq!(got, 14305004317252672866, "scalar_9");
    }

    #[test]
    fn test_rotl64_spec_10() {
        let x = 28239303458307367u64;
        let r = 515957865u32;
        let got = super::rotl64(x, r);
        assert_eq!(got, 12428331886955658854, "scalar_10");
    }

    #[test]
    fn test_rotl64_spec_11() {
        let x = 1286997712672073830u64;
        let r = 1696570651u32;
        let got = super::rotl64(x, r);
        assert_eq!(got, 14885655997850772140, "scalar_11");
    }

    #[test]
    fn test_rotl64_spec_12() {
        let x = 1648777927101059988u64;
        let r = 3374510824u32;
        let got = super::rotl64(x, r);
        assert_eq!(got, 6706867096080534018, "scalar_12");
    }

    #[test]
    fn test_rotl64_spec_13() {
        let x = 219839785649556781u64;
        let r = 1956481593u32;
        let got = super::rotl64(x, r);
        assert_eq!(got, 6486900961738901402, "scalar_13");
    }

    #[test]
    fn test_rotl64_spec_14() {
        let x = 1219558440841847642u64;
        let r = 948101882u32;
        let got = super::rotl64(x, r);
        assert_eq!(got, 7513045380582659213, "scalar_14");
    }

    #[test]
    fn test_rotl64_spec_15() {
        let x = 462807417111260359u64;
        let r = 3114109953u32;
        let got = super::rotl64(x, r);
        assert_eq!(got, 925614834222520718, "scalar_15");
    }

    #[test]
    fn test_rotl64_spec_16() {
        let x = 751687040856373258u64;
        let r = 385010413u32;
        let got = super::rotl64(x, r);
        assert_eq!(got, 5116442454143021456, "scalar_16");
    }

    #[test]
    fn test_rotl64_spec_17() {
        let x = 1600374978815623042u64;
        let r = 3471785603u32;
        let got = super::rotl64(x, r);
        assert_eq!(got, 12802999830524984336, "scalar_17");
    }

    #[test]
    fn test_rotl64_spec_18() {
        let x = 2302591862505531316u64;
        let r = 783092114u32;
        let got = super::rotl64(x, r);
        assert_eq!(got, 14728368799762907089, "scalar_18");
    }

    #[test]
    fn test_rotl64_spec_19() {
        let x = 2082396369769993775u64;
        let r = 619609168u32;
        let got = super::rotl64(x, r);
        assert_eq!(got, 2915831943049190630, "scalar_19");
    }

    #[test]
    fn test_rotl64_spec_20() {
        let x = 1228795927025587945u64;
        let r = 3340007993u32;
        let got = super::rotl64(x, r);
        assert_eq!(got, 15141694716144753965, "scalar_20");
    }

    #[test]
    fn test_rotl64_spec_21() {
        let x = 1840404415966088734u64;
        let r = 3092808310u32;
        let got = super::rotl64(x, r);
        assert_eq!(got, 9765601262076702211, "scalar_21");
    }

    #[test]
    fn test_rotl64_spec_22() {
        let x = 1728239021722770615u64;
        let r = 2030553267u32;
        let got = super::rotl64(x, r);
        assert_eq!(got, 16553191397077714440, "scalar_22");
    }

    #[test]
    fn test_rotl64_spec_23() {
        let x = 3765439633433888u64;
        let r = 2677912710u32;
        let got = super::rotl64(x, r);
        assert_eq!(got, 240988136539768832, "scalar_23");
    }

    #[test]
    fn test_rotl64_spec_24() {
        let x = 244117110423226031u64;
        let r = 2860311886u32;
        let got = super::rotl64(x, r);
        assert_eq!(got, 15118017252872143064, "scalar_24");
    }

    #[test]
    fn test_rotl64_spec_25() {
        let x = 677844138696617347u64;
        let r = 1740701840u32;
        let got = super::rotl64(x, r);
        assert_eq!(got, 3433744128914164072, "scalar_25");
    }

    #[test]
    fn test_rotl64_spec_26() {
        let x = 228398949501861089u64;
        let r = 3898710235u32;
        let got = super::rotl64(x, r);
        assert_eq!(got, 1396410446362794877, "scalar_26");
    }

    #[test]
    fn test_rotl64_spec_27() {
        let x = 1837365160497947160u64;
        let r = 1849549605u32;
        let got = super::rotl64(x, r);
        assert_eq!(got, 4977677169119738910, "scalar_27");
    }

    #[test]
    fn test_rotl64_spec_28() {
        let x = 1981114028366284254u64;
        let r = 604387498u32;
        let got = super::rotl64(x, r);
        assert_eq!(got, 4834465138735241601, "scalar_28");
    }

    #[test]
    fn test_rotl64_spec_29() {
        let x = 901413777197423151u64;
        let r = 1612057427u32;
        let got = super::rotl64(x, r);
        assert_eq!(got, 13289994917586166803, "scalar_29");
    }

    #[test]
    fn test_rotl64_spec_30() {
        let x = 1636666174396983988u64;
        let r = 1088387724u32;
        let got = super::rotl64(x, r);
        assert_eq!(got, 7616551573479178603, "scalar_30");
    }

    #[test]
    fn test_rotl64_spec_31() {
        let x = 992456198640655769u64;
        let r = 2970590891u32;
        let got = super::rotl64(x, r);
        assert_eq!(got, 16351664722640976952, "scalar_31");
    }

    #[test]
    fn test_rotl64_spec_32() {
        let x = 105961723365161716u64;
        let r = 2184472783u32;
        let got = super::rotl64(x, r);
        assert_eq!(got, 4165865372223406268, "scalar_32");
    }

    #[test]
    fn test_rotl64_spec_33() {
        let x = 2287152026491148452u64;
        let r = 861216061u32;
        let got = super::rotl64(x, r);
        assert_eq!(got, 9509266040166169364, "scalar_33");
    }

    #[test]
    fn test_rotl64_spec_34() {
        let x = 393048735350091950u64;
        let r = 945124932u32;
        let got = super::rotl64(x, r);
        assert_eq!(got, 6288779765601471200, "scalar_34");
    }

    #[test]
    fn test_rotl64_spec_35() {
        let x = 1646142417431048225u64;
        let r = 2165302682u32;
        let got = super::rotl64(x, r);
        assert_eq!(got, 4207128138911277335, "scalar_35");
    }

    #[test]
    fn test_rotl64_spec_36() {
        let x = 998436359561426035u64;
        let r = 3426857531u32;
        let got = super::rotl64(x, r);
        assert_eq!(got, 10983955430001340835, "scalar_36");
    }

    #[test]
    fn test_rotl64_spec_37() {
        let x = 1337014648277316960u64;
        let r = 1094605008u32;
        let got = super::rotl64(x, r);
        assert_eq!(got, 557639381874119310, "scalar_37");
    }

    #[test]
    fn test_rotl64_spec_38() {
        let x = 207476075073356113u64;
        let r = 153558149u32;
        let got = super::rotl64(x, r);
        assert_eq!(got, 6639234402347395616, "scalar_38");
    }

    #[test]
    fn test_rotl64_spec_39() {
        let x = 679898941166680626u64;
        let r = 2699992688u32;
        let got = super::rotl64(x, r);
        assert_eq!(got, 8805110595897268071, "scalar_39");
    }

    #[test]
    fn test_fmix32_spec_0() {
        let h = 0u32;
        let got = super::fmix32(h);
        assert_eq!(got, 0, "scalar_0");
    }

    #[test]
    fn test_fmix32_spec_1() {
        let h = 1u32;
        let got = super::fmix32(h);
        assert_eq!(got, 1364076727, "scalar_1");
    }

    #[test]
    fn test_fmix32_spec_2() {
        let h = 2u32;
        let got = super::fmix32(h);
        assert_eq!(got, 821347078, "scalar_2");
    }

    #[test]
    fn test_fmix32_spec_3() {
        let h = 3u32;
        let got = super::fmix32(h);
        assert_eq!(got, 2247144487, "scalar_3");
    }

    #[test]
    fn test_fmix32_spec_4() {
        let h = 4294967295u32;
        let got = super::fmix32(h);
        assert_eq!(got, 2180083513, "scalar_4");
    }

    #[test]
    fn test_fmix32_spec_5() {
        let h = 4294967294u32;
        let got = super::fmix32(h);
        assert_eq!(got, 2039857924, "scalar_5");
    }

    #[test]
    fn test_fmix32_spec_6() {
        let h = 2147483647u32;
        let got = super::fmix32(h);
        assert_eq!(got, 4190899880, "scalar_6");
    }

    #[test]
    fn test_fmix32_spec_7() {
        let h = 1431655765u32;
        let got = super::fmix32(h);
        assert_eq!(got, 489116351, "scalar_7");
    }

    #[test]
    fn test_fmix32_spec_8() {
        let h = 4221333571u32;
        let got = super::fmix32(h);
        assert_eq!(got, 2490500260, "scalar_8");
    }

    #[test]
    fn test_fmix32_spec_9() {
        let h = 2523375751u32;
        let got = super::fmix32(h);
        assert_eq!(got, 2562086454, "scalar_9");
    }

    #[test]
    fn test_fmix32_spec_10() {
        let h = 3809187989u32;
        let got = super::fmix32(h);
        assert_eq!(got, 3494542410, "scalar_10");
    }

    #[test]
    fn test_fmix32_spec_11() {
        let h = 2362559676u32;
        let got = super::fmix32(h);
        assert_eq!(got, 830331461, "scalar_11");
    }

    #[test]
    fn test_fmix32_spec_12() {
        let h = 4255686834u32;
        let got = super::fmix32(h);
        assert_eq!(got, 1445810788, "scalar_12");
    }

    #[test]
    fn test_fmix32_spec_13() {
        let h = 2095283571u32;
        let got = super::fmix32(h);
        assert_eq!(got, 980325836, "scalar_13");
    }

    #[test]
    fn test_fmix32_spec_14() {
        let h = 2031606184u32;
        let got = super::fmix32(h);
        assert_eq!(got, 3239751816, "scalar_14");
    }

    #[test]
    fn test_fmix32_spec_15() {
        let h = 3741706877u32;
        let got = super::fmix32(h);
        assert_eq!(got, 773401569, "scalar_15");
    }

    #[test]
    fn test_fmix32_spec_16() {
        let h = 1117707016u32;
        let got = super::fmix32(h);
        assert_eq!(got, 1863758680, "scalar_16");
    }

    #[test]
    fn test_fmix32_spec_17() {
        let h = 3849660456u32;
        let got = super::fmix32(h);
        assert_eq!(got, 2711987259, "scalar_17");
    }

    #[test]
    fn test_fmix32_spec_18() {
        let h = 2406541026u32;
        let got = super::fmix32(h);
        assert_eq!(got, 677230577, "scalar_18");
    }

    #[test]
    fn test_fmix32_spec_19() {
        let h = 2336867141u32;
        let got = super::fmix32(h);
        assert_eq!(got, 1198915782, "scalar_19");
    }

    #[test]
    fn test_fmix32_spec_20() {
        let h = 1707732423u32;
        let got = super::fmix32(h);
        assert_eq!(got, 4129838441, "scalar_20");
    }

    #[test]
    fn test_fmix32_spec_21() {
        let h = 1765045540u32;
        let got = super::fmix32(h);
        assert_eq!(got, 196432207, "scalar_21");
    }

    #[test]
    fn test_fmix32_spec_22() {
        let h = 3828953797u32;
        let got = super::fmix32(h);
        assert_eq!(got, 320986172, "scalar_22");
    }

    #[test]
    fn test_fmix32_spec_23() {
        let h = 3103324054u32;
        let got = super::fmix32(h);
        assert_eq!(got, 3814216145, "scalar_23");
    }

    #[test]
    fn test_fmix32_spec_24() {
        let h = 828673901u32;
        let got = super::fmix32(h);
        assert_eq!(got, 968336108, "scalar_24");
    }

    #[test]
    fn test_fmix32_spec_25() {
        let h = 3984390377u32;
        let got = super::fmix32(h);
        assert_eq!(got, 3435263318, "scalar_25");
    }

    #[test]
    fn test_fmix32_spec_26() {
        let h = 2780125135u32;
        let got = super::fmix32(h);
        assert_eq!(got, 34301465, "scalar_26");
    }

    #[test]
    fn test_fmix32_spec_27() {
        let h = 2135437294u32;
        let got = super::fmix32(h);
        assert_eq!(got, 3307920489, "scalar_27");
    }

    #[test]
    fn test_fmix32_spec_28() {
        let h = 3955744380u32;
        let got = super::fmix32(h);
        assert_eq!(got, 3871436684, "scalar_28");
    }

    #[test]
    fn test_fmix32_spec_29() {
        let h = 3332018165u32;
        let got = super::fmix32(h);
        assert_eq!(got, 2171170466, "scalar_29");
    }

    #[test]
    fn test_fmix32_spec_30() {
        let h = 2652805250u32;
        let got = super::fmix32(h);
        assert_eq!(got, 1568557548, "scalar_30");
    }

    #[test]
    fn test_fmix32_spec_31() {
        let h = 2261097679u32;
        let got = super::fmix32(h);
        assert_eq!(got, 1253582088, "scalar_31");
    }

    #[test]
    fn test_fmix32_spec_32() {
        let h = 4202815858u32;
        let got = super::fmix32(h);
        assert_eq!(got, 780571268, "scalar_32");
    }

    #[test]
    fn test_fmix32_spec_33() {
        let h = 205381322u32;
        let got = super::fmix32(h);
        assert_eq!(got, 3708126444, "scalar_33");
    }

    #[test]
    fn test_fmix32_spec_34() {
        let h = 1469931356u32;
        let got = super::fmix32(h);
        assert_eq!(got, 1098850987, "scalar_34");
    }

    #[test]
    fn test_fmix32_spec_35() {
        let h = 568424119u32;
        let got = super::fmix32(h);
        assert_eq!(got, 2059793421, "scalar_35");
    }

    #[test]
    fn test_fmix32_spec_36() {
        let h = 1775503057u32;
        let got = super::fmix32(h);
        assert_eq!(got, 2742848781, "scalar_36");
    }

    #[test]
    fn test_fmix32_spec_37() {
        let h = 2889404902u32;
        let got = super::fmix32(h);
        assert_eq!(got, 2211312073, "scalar_37");
    }

    #[test]
    fn test_fmix32_spec_38() {
        let h = 1793834719u32;
        let got = super::fmix32(h);
        assert_eq!(got, 3859887884, "scalar_38");
    }

    #[test]
    fn test_fmix32_spec_39() {
        let h = 1023311400u32;
        let got = super::fmix32(h);
        assert_eq!(got, 934200394, "scalar_39");
    }

    #[test]
    fn test_fmix64_spec_0() {
        let k = 0u64;
        let got = super::fmix64(k);
        assert_eq!(got, 0, "scalar_0");
    }

    #[test]
    fn test_fmix64_spec_1() {
        let k = 1u64;
        let got = super::fmix64(k);
        assert_eq!(got, 12994781566227106604, "scalar_1");
    }

    #[test]
    fn test_fmix64_spec_2() {
        let k = 2u64;
        let got = super::fmix64(k);
        assert_eq!(got, 4233148493373801447, "scalar_2");
    }

    #[test]
    fn test_fmix64_spec_3() {
        let k = 3u64;
        let got = super::fmix64(k);
        assert_eq!(got, 815575690806614222, "scalar_3");
    }

    #[test]
    fn test_fmix64_spec_4() {
        let k = 18446744073709551615u64;
        let got = super::fmix64(k);
        assert_eq!(got, 7256831767414464289, "scalar_4");
    }

    #[test]
    fn test_fmix64_spec_5() {
        let k = 18446744073709551614u64;
        let got = super::fmix64(k);
        assert_eq!(got, 4216938840244723755, "scalar_5");
    }

    #[test]
    fn test_fmix64_spec_6() {
        let k = 9223372036854775807u64;
        let got = super::fmix64(k);
        assert_eq!(got, 12373989555017149930, "scalar_6");
    }

    #[test]
    fn test_fmix64_spec_7() {
        let k = 6148914691236517205u64;
        let got = super::fmix64(k);
        assert_eq!(got, 13810126712103999293, "scalar_7");
    }

    #[test]
    fn test_fmix64_spec_8() {
        let k = 1262872539444675860u64;
        let got = super::fmix64(k);
        assert_eq!(got, 2931928056866485454, "scalar_8");
    }

    #[test]
    fn test_fmix64_spec_9() {
        let k = 2037554769358626937u64;
        let got = super::fmix64(k);
        assert_eq!(got, 7503289048197339039, "scalar_9");
    }

    #[test]
    fn test_fmix64_spec_10() {
        let k = 2131880528890846292u64;
        let got = super::fmix64(k);
        assert_eq!(got, 17546459714489644260, "scalar_10");
    }

    #[test]
    fn test_fmix64_spec_11() {
        let k = 527746440087574148u64;
        let got = super::fmix64(k);
        assert_eq!(got, 8124001757971974765, "scalar_11");
    }

    #[test]
    fn test_fmix64_spec_12() {
        let k = 2048652106033787150u64;
        let got = super::fmix64(k);
        assert_eq!(got, 11242530663002752849, "scalar_12");
    }

    #[test]
    fn test_fmix64_spec_13() {
        let k = 260457227638694145u64;
        let got = super::fmix64(k);
        assert_eq!(got, 17478872024841592478, "scalar_13");
    }

    #[test]
    fn test_fmix64_spec_14() {
        let k = 857448613300530131u64;
        let got = super::fmix64(k);
        assert_eq!(got, 18285645187364937073, "scalar_14");
    }

    #[test]
    fn test_fmix64_spec_15() {
        let k = 2295428030787227968u64;
        let got = super::fmix64(k);
        assert_eq!(got, 14986088594424705569, "scalar_15");
    }

    #[test]
    fn test_fmix64_spec_16() {
        let k = 1851198078524950449u64;
        let got = super::fmix64(k);
        assert_eq!(got, 12611205396522812913, "scalar_16");
    }

    #[test]
    fn test_fmix64_spec_17() {
        let k = 1050068612969724178u64;
        let got = super::fmix64(k);
        assert_eq!(got, 3302447837447784601, "scalar_17");
    }

    #[test]
    fn test_fmix64_spec_18() {
        let k = 1509658091810805305u64;
        let got = super::fmix64(k);
        assert_eq!(got, 961288002364517531, "scalar_18");
    }

    #[test]
    fn test_fmix64_spec_19() {
        let k = 1827401271378910917u64;
        let got = super::fmix64(k);
        assert_eq!(got, 754520480596665323, "scalar_19");
    }

    #[test]
    fn test_fmix64_spec_20() {
        let k = 1917124573795328891u64;
        let got = super::fmix64(k);
        assert_eq!(got, 2653272678981441467, "scalar_20");
    }

    #[test]
    fn test_fmix64_spec_21() {
        let k = 453501205188596010u64;
        let got = super::fmix64(k);
        assert_eq!(got, 13203992699050313920, "scalar_21");
    }

    #[test]
    fn test_fmix64_spec_22() {
        let k = 1014520376052447752u64;
        let got = super::fmix64(k);
        assert_eq!(got, 15453354111548806379, "scalar_22");
    }

    #[test]
    fn test_fmix64_spec_23() {
        let k = 1595927935896017809u64;
        let got = super::fmix64(k);
        assert_eq!(got, 1936799410325316486, "scalar_23");
    }

    #[test]
    fn test_fmix64_spec_24() {
        let k = 811863877325539054u64;
        let got = super::fmix64(k);
        assert_eq!(got, 17988861756340363681, "scalar_24");
    }

    #[test]
    fn test_fmix64_spec_25() {
        let k = 1050590575154977227u64;
        let got = super::fmix64(k);
        assert_eq!(got, 12777560059154452122, "scalar_25");
    }

    #[test]
    fn test_fmix64_spec_26() {
        let k = 1436726754915786174u64;
        let got = super::fmix64(k);
        assert_eq!(got, 7825726989935893535, "scalar_26");
    }

    #[test]
    fn test_fmix64_spec_27() {
        let k = 817140123115858982u64;
        let got = super::fmix64(k);
        assert_eq!(got, 2852885357955380269, "scalar_27");
    }

    #[test]
    fn test_fmix64_spec_28() {
        let k = 1346684563861249160u64;
        let got = super::fmix64(k);
        assert_eq!(got, 15746142027362184090, "scalar_28");
    }

    #[test]
    fn test_fmix64_spec_29() {
        let k = 2164240831391665011u64;
        let got = super::fmix64(k);
        assert_eq!(got, 9751779442731848099, "scalar_29");
    }

    #[test]
    fn test_fmix64_spec_30() {
        let k = 74245827408457693u64;
        let got = super::fmix64(k);
        assert_eq!(got, 8800622684040773022, "scalar_30");
    }

    #[test]
    fn test_fmix64_spec_31() {
        let k = 1604212922725973250u64;
        let got = super::fmix64(k);
        assert_eq!(got, 9949251256452859244, "scalar_31");
    }

    #[test]
    fn test_fmix64_spec_32() {
        let k = 966489908936210123u64;
        let got = super::fmix64(k);
        assert_eq!(got, 6011532363858482897, "scalar_32");
    }

    #[test]
    fn test_fmix64_spec_33() {
        let k = 478028029995574948u64;
        let got = super::fmix64(k);
        assert_eq!(got, 2542991546983175705, "scalar_33");
    }

    #[test]
    fn test_fmix64_spec_34() {
        let k = 728881866934290147u64;
        let got = super::fmix64(k);
        assert_eq!(got, 2943170552935955604, "scalar_34");
    }

    #[test]
    fn test_fmix64_spec_35() {
        let k = 1665821072439902887u64;
        let got = super::fmix64(k);
        assert_eq!(got, 10225151466749198373, "scalar_35");
    }

    #[test]
    fn test_fmix64_spec_36() {
        let k = 164281819267420213u64;
        let got = super::fmix64(k);
        assert_eq!(got, 8437378361353298073, "scalar_36");
    }

    #[test]
    fn test_fmix64_spec_37() {
        let k = 1989984267484492764u64;
        let got = super::fmix64(k);
        assert_eq!(got, 3872368234284871316, "scalar_37");
    }

    #[test]
    fn test_fmix64_spec_38() {
        let k = 2189315956455498066u64;
        let got = super::fmix64(k);
        assert_eq!(got, 2646520187111042421, "scalar_38");
    }

    #[test]
    fn test_fmix64_spec_39() {
        let k = 2116707369718725011u64;
        let got = super::fmix64(k);
        assert_eq!(got, 9801861205667953674, "scalar_39");
    }

}
