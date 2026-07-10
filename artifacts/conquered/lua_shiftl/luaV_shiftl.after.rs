//! Shiftl
//!
//! Module containing 1 function: luaV_shiftl

#![allow(unused_variables, unused_imports, dead_code)]

use crate::*;

/// #define NBITS 64
pub const NBITS: i32 = 64;


/// Luav Shiftl
/// Performs a bitwise shift on an integer where the direction (left or right) is
/// determined by the sign of the shift amount.
pub fn lua_v_shiftl(x: isize, y: isize) -> isize {
    const NBITS: isize = 64;
    if y < 0 {
        if y <= -NBITS {
            0
        } else {
            let shift_amount = (-y) as u32;
            ((x as usize) >> shift_amount) as isize
        }
    } else {
        if y >= NBITS {
            0
        } else {
            let shift_amount = y as u32;
            ((x as usize) << shift_amount) as isize
        }
    }
}

#[cfg(test)]
mod tests {
    #![allow(unused_imports, unused_variables, unused_macros)]
    extern crate alloc;
    use alloc::format;
    use alloc::string::String;

    #[test]
    fn test_lua_v_shiftl_spec_0() {
        let x = 0isize;
        let y = 0isize;
        let got = super::lua_v_shiftl(x, y);
        assert_eq!(got, 0, "scalar_0");
    }

    #[test]
    fn test_lua_v_shiftl_spec_1() {
        let x = 1isize;
        let y = 1isize;
        let got = super::lua_v_shiftl(x, y);
        assert_eq!(got, 2, "scalar_1");
    }

    #[test]
    fn test_lua_v_shiftl_spec_2() {
        let x = 2isize;
        let y = 2isize;
        let got = super::lua_v_shiftl(x, y);
        assert_eq!(got, 8, "scalar_2");
    }

    #[test]
    fn test_lua_v_shiftl_spec_3() {
        let x = 3isize;
        let y = 3isize;
        let got = super::lua_v_shiftl(x, y);
        assert_eq!(got, 24, "scalar_3");
    }

    #[test]
    fn test_lua_v_shiftl_spec_4() {
        let x = 9223372036854775807isize;
        let y = 9223372036854775807isize;
        let got = super::lua_v_shiftl(x, y);
        assert_eq!(got, 0, "scalar_4");
    }

    #[test]
    fn test_lua_v_shiftl_spec_5() {
        let x = 9223372036854775806isize;
        let y = 9223372036854775806isize;
        let got = super::lua_v_shiftl(x, y);
        assert_eq!(got, 0, "scalar_5");
    }

    #[test]
    fn test_lua_v_shiftl_spec_6() {
        let x = 4611686018427387903isize;
        let y = 4611686018427387903isize;
        let got = super::lua_v_shiftl(x, y);
        assert_eq!(got, 0, "scalar_6");
    }

    #[test]
    fn test_lua_v_shiftl_spec_7() {
        let x = 3074457345618258602isize;
        let y = 3074457345618258602isize;
        let got = super::lua_v_shiftl(x, y);
        assert_eq!(got, 0, "scalar_7");
    }

    #[test]
    fn test_lua_v_shiftl_spec_8() {
        let x = -9223372036854775808isize;
        let y = -9223372036854775808isize;
        let got = super::lua_v_shiftl(x, y);
        assert_eq!(got, 0, "scalar_8");
    }

    #[test]
    fn test_lua_v_shiftl_spec_9() {
        let x = -9223372036854775807isize;
        let y = -9223372036854775807isize;
        let got = super::lua_v_shiftl(x, y);
        assert_eq!(got, 0, "scalar_9");
    }

    #[test]
    fn test_lua_v_shiftl_spec_10() {
        let x = -1isize;
        let y = -1isize;
        let got = super::lua_v_shiftl(x, y);
        assert_eq!(got, 9223372036854775807, "scalar_10");
    }

    #[test]
    fn test_lua_v_shiftl_spec_11() {
        let x = -2isize;
        let y = -2isize;
        let got = super::lua_v_shiftl(x, y);
        assert_eq!(got, 4611686018427387903, "scalar_11");
    }

    #[test]
    fn test_lua_v_shiftl_spec_12() {
        let x = -7587656018583407197isize;
        let y = -8186493476819114939isize;
        let got = super::lua_v_shiftl(x, y);
        assert_eq!(got, 0, "scalar_12");
    }

    #[test]
    fn test_lua_v_shiftl_spec_13() {
        let x = -8957582080893670835isize;
        let y = -8233064556368213174isize;
        let got = super::lua_v_shiftl(x, y);
        assert_eq!(got, 0, "scalar_13");
    }

    #[test]
    fn test_lua_v_shiftl_spec_14() {
        let x = -8671223297842539854isize;
        let y = -7105094394134875789isize;
        let got = super::lua_v_shiftl(x, y);
        assert_eq!(got, 0, "scalar_14");
    }

    #[test]
    fn test_lua_v_shiftl_spec_15() {
        let x = -8171535086693361989isize;
        let y = -8989928896455471572isize;
        let got = super::lua_v_shiftl(x, y);
        assert_eq!(got, 0, "scalar_15");
    }

    #[test]
    fn test_lua_v_shiftl_spec_16() {
        let x = -9086375997657361452isize;
        let y = -7867277072190901813isize;
        let got = super::lua_v_shiftl(x, y);
        assert_eq!(got, 0, "scalar_16");
    }

    #[test]
    fn test_lua_v_shiftl_spec_17() {
        let x = -8773331519938000813isize;
        let y = -7286343125168921233isize;
        let got = super::lua_v_shiftl(x, y);
        assert_eq!(got, 0, "scalar_17");
    }

    #[test]
    fn test_lua_v_shiftl_spec_18() {
        let x = -9202720708826836137isize;
        let y = -8905069488849951395isize;
        let got = super::lua_v_shiftl(x, y);
        assert_eq!(got, 0, "scalar_18");
    }

    #[test]
    fn test_lua_v_shiftl_spec_19() {
        let x = -9020992040872489179isize;
        let y = -9063301338370636828isize;
        let got = super::lua_v_shiftl(x, y);
        assert_eq!(got, 0, "scalar_19");
    }

    #[test]
    fn test_lua_v_shiftl_spec_20() {
        let x = -8538743344501206004isize;
        let y = -8080325040383743302isize;
        let got = super::lua_v_shiftl(x, y);
        assert_eq!(got, 0, "scalar_20");
    }

    #[test]
    fn test_lua_v_shiftl_spec_21() {
        let x = -7648800575788344894isize;
        let y = -9115248076722915109isize;
        let got = super::lua_v_shiftl(x, y);
        assert_eq!(got, 0, "scalar_21");
    }

    #[test]
    fn test_lua_v_shiftl_spec_22() {
        let x = -7391943900323924669isize;
        let y = -9216869130837466384isize;
        let got = super::lua_v_shiftl(x, y);
        assert_eq!(got, 0, "scalar_22");
    }

    #[test]
    fn test_lua_v_shiftl_spec_23() {
        let x = -7404678633474631368isize;
        let y = -8551317302942383067isize;
        let got = super::lua_v_shiftl(x, y);
        assert_eq!(got, 0, "scalar_23");
    }

    #[test]
    fn test_lua_v_shiftl_spec_24() {
        let x = -7533895679738886451isize;
        let y = -8105126645936654960isize;
        let got = super::lua_v_shiftl(x, y);
        assert_eq!(got, 0, "scalar_24");
    }

    #[test]
    fn test_lua_v_shiftl_spec_25() {
        let x = -8945859668424735464isize;
        let y = -8430203699971569136isize;
        let got = super::lua_v_shiftl(x, y);
        assert_eq!(got, 0, "scalar_25");
    }

    #[test]
    fn test_lua_v_shiftl_spec_26() {
        let x = -8382810631447429896isize;
        let y = -7524031153298180950isize;
        let got = super::lua_v_shiftl(x, y);
        assert_eq!(got, 0, "scalar_26");
    }

    #[test]
    fn test_lua_v_shiftl_spec_27() {
        let x = -7510114394125648014isize;
        let y = -8855544403977836691isize;
        let got = super::lua_v_shiftl(x, y);
        assert_eq!(got, 0, "scalar_27");
    }

    #[test]
    fn test_lua_v_shiftl_spec_28() {
        let x = -8831203112982330219isize;
        let y = -6996007270393175857isize;
        let got = super::lua_v_shiftl(x, y);
        assert_eq!(got, 0, "scalar_28");
    }

    #[test]
    fn test_lua_v_shiftl_spec_29() {
        let x = -8165465125546993449isize;
        let y = -6945032904949471860isize;
        let got = super::lua_v_shiftl(x, y);
        assert_eq!(got, 0, "scalar_29");
    }

    #[test]
    fn test_lua_v_shiftl_spec_30() {
        let x = -7775640573271591180isize;
        let y = -7541253933382234867isize;
        let got = super::lua_v_shiftl(x, y);
        assert_eq!(got, 0, "scalar_30");
    }

    #[test]
    fn test_lua_v_shiftl_spec_31() {
        let x = -8419421892025748395isize;
        let y = -7565879307866010050isize;
        let got = super::lua_v_shiftl(x, y);
        assert_eq!(got, 0, "scalar_31");
    }

    #[test]
    fn test_lua_v_shiftl_spec_32() {
        let x = -8764977918664380954isize;
        let y = -7258631318870170891isize;
        let got = super::lua_v_shiftl(x, y);
        assert_eq!(got, 0, "scalar_32");
    }

    #[test]
    fn test_lua_v_shiftl_spec_33() {
        let x = -7202019399012349059isize;
        let y = -8424024415276425263isize;
        let got = super::lua_v_shiftl(x, y);
        assert_eq!(got, 0, "scalar_33");
    }

    #[test]
    fn test_lua_v_shiftl_spec_34() {
        let x = -8774683724328126535isize;
        let y = -7675426041921845609isize;
        let got = super::lua_v_shiftl(x, y);
        assert_eq!(got, 0, "scalar_34");
    }

    #[test]
    fn test_lua_v_shiftl_spec_35() {
        let x = -7711646966964186529isize;
        let y = -9163505246612463338isize;
        let got = super::lua_v_shiftl(x, y);
        assert_eq!(got, 0, "scalar_35");
    }

    #[test]
    fn test_lua_v_shiftl_spec_36() {
        let x = -7248780242600596674isize;
        let y = -9097114592963765628isize;
        let got = super::lua_v_shiftl(x, y);
        assert_eq!(got, 0, "scalar_36");
    }

    #[test]
    fn test_lua_v_shiftl_spec_37() {
        let x = -8719234934682911860isize;
        let y = -7546792504001342115isize;
        let got = super::lua_v_shiftl(x, y);
        assert_eq!(got, 0, "scalar_37");
    }

    #[test]
    fn test_lua_v_shiftl_spec_38() {
        let x = -8203795368209212475isize;
        let y = -7573419278393154614isize;
        let got = super::lua_v_shiftl(x, y);
        assert_eq!(got, 0, "scalar_38");
    }

    #[test]
    fn test_lua_v_shiftl_spec_39() {
        let x = -7103968526412194798isize;
        let y = -8281690921485430665isize;
        let got = super::lua_v_shiftl(x, y);
        assert_eq!(got, 0, "scalar_39");
    }

}
