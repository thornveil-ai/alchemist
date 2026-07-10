//! Ceil
//!
//! Module containing 1 function: luaO_ceillog2

#![allow(unused_variables, unused_imports, dead_code)]

use crate::*;

/// static const lu_byte log_2[256]
pub const log_2: [u8; 256] = [0, 1, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 4, 4, 4, 4, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8];


/// Luao Ceillog2
/// Calculates the ceiling of the base-2 logarithm of an unsigned integer.
/// Effectively finds the minimum number of bits required to represent the value
/// x-1.
pub fn lua_o_ceillog2(x: u32) -> i32 {
    let mut l: i32 = 0;
    let mut x = x.wrapping_sub(1);
    while x >= 256 {
        l = l.wrapping_add(8);
        x >>= 8;
    }
    l.wrapping_add(log_2[x as usize] as i32)
}

#[cfg(test)]
mod tests {
    #![allow(unused_imports, unused_variables, unused_macros)]
    extern crate alloc;
    use alloc::format;
    use alloc::string::String;

    #[test]
    fn test_lua_o_ceillog2_spec_0() {
        let x = 0u32;
        let got = super::lua_o_ceillog2(x);
        assert_eq!(got, 32, "scalar_0");
    }

    #[test]
    fn test_lua_o_ceillog2_spec_1() {
        let x = 1u32;
        let got = super::lua_o_ceillog2(x);
        assert_eq!(got, 0, "scalar_1");
    }

    #[test]
    fn test_lua_o_ceillog2_spec_2() {
        let x = 2u32;
        let got = super::lua_o_ceillog2(x);
        assert_eq!(got, 1, "scalar_2");
    }

    #[test]
    fn test_lua_o_ceillog2_spec_3() {
        let x = 3u32;
        let got = super::lua_o_ceillog2(x);
        assert_eq!(got, 2, "scalar_3");
    }

    #[test]
    fn test_lua_o_ceillog2_spec_4() {
        let x = 4294967295u32;
        let got = super::lua_o_ceillog2(x);
        assert_eq!(got, 32, "scalar_4");
    }

    #[test]
    fn test_lua_o_ceillog2_spec_5() {
        let x = 4294967294u32;
        let got = super::lua_o_ceillog2(x);
        assert_eq!(got, 32, "scalar_5");
    }

    #[test]
    fn test_lua_o_ceillog2_spec_6() {
        let x = 2147483647u32;
        let got = super::lua_o_ceillog2(x);
        assert_eq!(got, 31, "scalar_6");
    }

    #[test]
    fn test_lua_o_ceillog2_spec_7() {
        let x = 1431655765u32;
        let got = super::lua_o_ceillog2(x);
        assert_eq!(got, 31, "scalar_7");
    }

    #[test]
    fn test_lua_o_ceillog2_spec_8() {
        let x = 1460894022u32;
        let got = super::lua_o_ceillog2(x);
        assert_eq!(got, 31, "scalar_8");
    }

    #[test]
    fn test_lua_o_ceillog2_spec_9() {
        let x = 3721636701u32;
        let got = super::lua_o_ceillog2(x);
        assert_eq!(got, 32, "scalar_9");
    }

    #[test]
    fn test_lua_o_ceillog2_spec_10() {
        let x = 3734041113u32;
        let got = super::lua_o_ceillog2(x);
        assert_eq!(got, 32, "scalar_10");
    }

    #[test]
    fn test_lua_o_ceillog2_spec_11() {
        let x = 935785791u32;
        let got = super::lua_o_ceillog2(x);
        assert_eq!(got, 30, "scalar_11");
    }

    #[test]
    fn test_lua_o_ceillog2_spec_12() {
        let x = 3417009310u32;
        let got = super::lua_o_ceillog2(x);
        assert_eq!(got, 32, "scalar_12");
    }

    #[test]
    fn test_lua_o_ceillog2_spec_13() {
        let x = 650434924u32;
        let got = super::lua_o_ceillog2(x);
        assert_eq!(got, 30, "scalar_13");
    }

    #[test]
    fn test_lua_o_ceillog2_spec_14() {
        let x = 4081040421u32;
        let got = super::lua_o_ceillog2(x);
        assert_eq!(got, 32, "scalar_14");
    }

    #[test]
    fn test_lua_o_ceillog2_spec_15() {
        let x = 1610820850u32;
        let got = super::lua_o_ceillog2(x);
        assert_eq!(got, 31, "scalar_15");
    }

    #[test]
    fn test_lua_o_ceillog2_spec_16() {
        let x = 2798077055u32;
        let got = super::lua_o_ceillog2(x);
        assert_eq!(got, 32, "scalar_16");
    }

    #[test]
    fn test_lua_o_ceillog2_spec_17() {
        let x = 1181526882u32;
        let got = super::lua_o_ceillog2(x);
        assert_eq!(got, 31, "scalar_17");
    }

    #[test]
    fn test_lua_o_ceillog2_spec_18() {
        let x = 2808180218u32;
        let got = super::lua_o_ceillog2(x);
        assert_eq!(got, 32, "scalar_18");
    }

    #[test]
    fn test_lua_o_ceillog2_spec_19() {
        let x = 3621149388u32;
        let got = super::lua_o_ceillog2(x);
        assert_eq!(got, 32, "scalar_19");
    }

    #[test]
    fn test_lua_o_ceillog2_spec_20() {
        let x = 2295478631u32;
        let got = super::lua_o_ceillog2(x);
        assert_eq!(got, 32, "scalar_20");
    }

    #[test]
    fn test_lua_o_ceillog2_spec_21() {
        let x = 2200670145u32;
        let got = super::lua_o_ceillog2(x);
        assert_eq!(got, 32, "scalar_21");
    }

    #[test]
    fn test_lua_o_ceillog2_spec_22() {
        let x = 2168124438u32;
        let got = super::lua_o_ceillog2(x);
        assert_eq!(got, 32, "scalar_22");
    }

    #[test]
    fn test_lua_o_ceillog2_spec_23() {
        let x = 288461135u32;
        let got = super::lua_o_ceillog2(x);
        assert_eq!(got, 29, "scalar_23");
    }

    #[test]
    fn test_lua_o_ceillog2_spec_24() {
        let x = 3587836888u32;
        let got = super::lua_o_ceillog2(x);
        assert_eq!(got, 32, "scalar_24");
    }

    #[test]
    fn test_lua_o_ceillog2_spec_25() {
        let x = 1349246215u32;
        let got = super::lua_o_ceillog2(x);
        assert_eq!(got, 31, "scalar_25");
    }

    #[test]
    fn test_lua_o_ceillog2_spec_26() {
        let x = 3823567611u32;
        let got = super::lua_o_ceillog2(x);
        assert_eq!(got, 32, "scalar_26");
    }

    #[test]
    fn test_lua_o_ceillog2_spec_27() {
        let x = 3318876921u32;
        let got = super::lua_o_ceillog2(x);
        assert_eq!(got, 32, "scalar_27");
    }

    #[test]
    fn test_lua_o_ceillog2_spec_28() {
        let x = 547849296u32;
        let got = super::lua_o_ceillog2(x);
        assert_eq!(got, 30, "scalar_28");
    }

    #[test]
    fn test_lua_o_ceillog2_spec_29() {
        let x = 3379581366u32;
        let got = super::lua_o_ceillog2(x);
        assert_eq!(got, 32, "scalar_29");
    }

    #[test]
    fn test_lua_o_ceillog2_spec_30() {
        let x = 2535626535u32;
        let got = super::lua_o_ceillog2(x);
        assert_eq!(got, 32, "scalar_30");
    }

    #[test]
    fn test_lua_o_ceillog2_spec_31() {
        let x = 3383994956u32;
        let got = super::lua_o_ceillog2(x);
        assert_eq!(got, 32, "scalar_31");
    }

    #[test]
    fn test_lua_o_ceillog2_spec_32() {
        let x = 1985934161u32;
        let got = super::lua_o_ceillog2(x);
        assert_eq!(got, 31, "scalar_32");
    }

    #[test]
    fn test_lua_o_ceillog2_spec_33() {
        let x = 470455372u32;
        let got = super::lua_o_ceillog2(x);
        assert_eq!(got, 29, "scalar_33");
    }

    #[test]
    fn test_lua_o_ceillog2_spec_34() {
        let x = 2464249116u32;
        let got = super::lua_o_ceillog2(x);
        assert_eq!(got, 32, "scalar_34");
    }

    #[test]
    fn test_lua_o_ceillog2_spec_35() {
        let x = 4289427910u32;
        let got = super::lua_o_ceillog2(x);
        assert_eq!(got, 32, "scalar_35");
    }

    #[test]
    fn test_lua_o_ceillog2_spec_36() {
        let x = 2200482137u32;
        let got = super::lua_o_ceillog2(x);
        assert_eq!(got, 32, "scalar_36");
    }

    #[test]
    fn test_lua_o_ceillog2_spec_37() {
        let x = 297382731u32;
        let got = super::lua_o_ceillog2(x);
        assert_eq!(got, 29, "scalar_37");
    }

    #[test]
    fn test_lua_o_ceillog2_spec_38() {
        let x = 3140135256u32;
        let got = super::lua_o_ceillog2(x);
        assert_eq!(got, 32, "scalar_38");
    }

    #[test]
    fn test_lua_o_ceillog2_spec_39() {
        let x = 1118448617u32;
        let got = super::lua_o_ceillog2(x);
        assert_eq!(got, 31, "scalar_39");
    }

}
