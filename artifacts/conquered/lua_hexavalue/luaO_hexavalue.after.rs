//! Hexa
//!
//! Module containing 1 function: luaO_hexavalue

#![allow(unused_variables, unused_imports, dead_code)]

use crate::*;

/// Luao Hexavalue
/// Converts a single hexadecimal character (0-9, a-f, A-F) into its corresponding
/// integer value (0-15).
pub fn lua_o_hexavalue(c: i32) -> i32 {
    if c >= 48 && c <= 57 {
        c.wrapping_sub(48)
    } else {
        let mut lower = c;
        if lower >= 65 && lower <= 90 {
            lower = lower.wrapping_add(32);
        }
        (lower.wrapping_sub(97)).wrapping_add(10)
    }
}

#[cfg(test)]
mod tests {
    #![allow(unused_imports, unused_variables, unused_macros)]
    extern crate alloc;
    use alloc::format;
    use alloc::string::String;

    #[test]
    fn test_lua_o_hexavalue_spec_0() {
        let c = 0i32;
        let got = super::lua_o_hexavalue(c);
        assert_eq!(got, -87, "scalar_0");
    }

    #[test]
    fn test_lua_o_hexavalue_spec_1() {
        let c = 1i32;
        let got = super::lua_o_hexavalue(c);
        assert_eq!(got, -86, "scalar_1");
    }

    #[test]
    fn test_lua_o_hexavalue_spec_2() {
        let c = 2i32;
        let got = super::lua_o_hexavalue(c);
        assert_eq!(got, -85, "scalar_2");
    }

    #[test]
    fn test_lua_o_hexavalue_spec_3() {
        let c = 3i32;
        let got = super::lua_o_hexavalue(c);
        assert_eq!(got, -84, "scalar_3");
    }

    #[test]
    fn test_lua_o_hexavalue_spec_4() {
        let c = 255i32;
        let got = super::lua_o_hexavalue(c);
        assert_eq!(got, 168, "scalar_4");
    }

    #[test]
    fn test_lua_o_hexavalue_spec_5() {
        let c = 254i32;
        let got = super::lua_o_hexavalue(c);
        assert_eq!(got, 167, "scalar_5");
    }

    #[test]
    fn test_lua_o_hexavalue_spec_6() {
        let c = 127i32;
        let got = super::lua_o_hexavalue(c);
        assert_eq!(got, 40, "scalar_6");
    }

    #[test]
    fn test_lua_o_hexavalue_spec_7() {
        let c = 85i32;
        let got = super::lua_o_hexavalue(c);
        assert_eq!(got, 30, "scalar_7");
    }

    #[test]
    fn test_lua_o_hexavalue_spec_8() {
        let c = -1i32;
        let got = super::lua_o_hexavalue(c);
        assert_eq!(got, -88, "scalar_8");
    }

    #[test]
    fn test_lua_o_hexavalue_spec_9() {
        let c = 28i32;
        let got = super::lua_o_hexavalue(c);
        assert_eq!(got, -59, "scalar_9");
    }

    #[test]
    fn test_lua_o_hexavalue_spec_10() {
        let c = 33i32;
        let got = super::lua_o_hexavalue(c);
        assert_eq!(got, -54, "scalar_10");
    }

    #[test]
    fn test_lua_o_hexavalue_spec_11() {
        let c = 119i32;
        let got = super::lua_o_hexavalue(c);
        assert_eq!(got, 32, "scalar_11");
    }

    #[test]
    fn test_lua_o_hexavalue_spec_12() {
        let c = 128i32;
        let got = super::lua_o_hexavalue(c);
        assert_eq!(got, 41, "scalar_12");
    }

    #[test]
    fn test_lua_o_hexavalue_spec_13() {
        let c = 59i32;
        let got = super::lua_o_hexavalue(c);
        assert_eq!(got, -28, "scalar_13");
    }

    #[test]
    fn test_lua_o_hexavalue_spec_14() {
        let c = 248i32;
        let got = super::lua_o_hexavalue(c);
        assert_eq!(got, 161, "scalar_14");
    }

    #[test]
    fn test_lua_o_hexavalue_spec_15() {
        let c = 137i32;
        let got = super::lua_o_hexavalue(c);
        assert_eq!(got, 50, "scalar_15");
    }

    #[test]
    fn test_lua_o_hexavalue_spec_16() {
        let c = 145i32;
        let got = super::lua_o_hexavalue(c);
        assert_eq!(got, 58, "scalar_16");
    }

    #[test]
    fn test_lua_o_hexavalue_spec_17() {
        let c = 21i32;
        let got = super::lua_o_hexavalue(c);
        assert_eq!(got, -66, "scalar_17");
    }

    #[test]
    fn test_lua_o_hexavalue_spec_18() {
        let c = 131i32;
        let got = super::lua_o_hexavalue(c);
        assert_eq!(got, 44, "scalar_18");
    }

    #[test]
    fn test_lua_o_hexavalue_spec_19() {
        let c = 218i32;
        let got = super::lua_o_hexavalue(c);
        assert_eq!(got, 131, "scalar_20");
    }

    #[test]
    fn test_lua_o_hexavalue_spec_20() {
        let c = 103i32;
        let got = super::lua_o_hexavalue(c);
        assert_eq!(got, 16, "scalar_21");
    }

    #[test]
    fn test_lua_o_hexavalue_spec_21() {
        let c = 202i32;
        let got = super::lua_o_hexavalue(c);
        assert_eq!(got, 115, "scalar_23");
    }

    #[test]
    fn test_lua_o_hexavalue_spec_22() {
        let c = 49i32;
        let got = super::lua_o_hexavalue(c);
        assert_eq!(got, 1, "scalar_24");
    }

    #[test]
    fn test_lua_o_hexavalue_spec_23() {
        let c = 213i32;
        let got = super::lua_o_hexavalue(c);
        assert_eq!(got, 126, "scalar_25");
    }

    #[test]
    fn test_lua_o_hexavalue_spec_24() {
        let c = 182i32;
        let got = super::lua_o_hexavalue(c);
        assert_eq!(got, 95, "scalar_26");
    }

    #[test]
    fn test_lua_o_hexavalue_spec_25() {
        let c = 178i32;
        let got = super::lua_o_hexavalue(c);
        assert_eq!(got, 91, "scalar_27");
    }

    #[test]
    fn test_lua_o_hexavalue_spec_26() {
        let c = 211i32;
        let got = super::lua_o_hexavalue(c);
        assert_eq!(got, 124, "scalar_28");
    }

    #[test]
    fn test_lua_o_hexavalue_spec_27() {
        let c = 196i32;
        let got = super::lua_o_hexavalue(c);
        assert_eq!(got, 109, "scalar_29");
    }

    #[test]
    fn test_lua_o_hexavalue_spec_28() {
        let c = 63i32;
        let got = super::lua_o_hexavalue(c);
        assert_eq!(got, -24, "scalar_30");
    }

    #[test]
    fn test_lua_o_hexavalue_spec_29() {
        let c = 129i32;
        let got = super::lua_o_hexavalue(c);
        assert_eq!(got, 42, "scalar_31");
    }

    #[test]
    fn test_lua_o_hexavalue_spec_30() {
        let c = 51i32;
        let got = super::lua_o_hexavalue(c);
        assert_eq!(got, 3, "scalar_33");
    }

    #[test]
    fn test_lua_o_hexavalue_spec_31() {
        let c = 58i32;
        let got = super::lua_o_hexavalue(c);
        assert_eq!(got, -29, "scalar_34");
    }

    #[test]
    fn test_lua_o_hexavalue_spec_32() {
        let c = 154i32;
        let got = super::lua_o_hexavalue(c);
        assert_eq!(got, 67, "scalar_35");
    }

    #[test]
    fn test_lua_o_hexavalue_spec_33() {
        let c = 193i32;
        let got = super::lua_o_hexavalue(c);
        assert_eq!(got, 106, "scalar_36");
    }

    #[test]
    fn test_lua_o_hexavalue_spec_34() {
        let c = 243i32;
        let got = super::lua_o_hexavalue(c);
        assert_eq!(got, 156, "scalar_37");
    }

    #[test]
    fn test_lua_o_hexavalue_spec_35() {
        let c = 9i32;
        let got = super::lua_o_hexavalue(c);
        assert_eq!(got, -78, "scalar_38");
    }

    #[test]
    fn test_lua_o_hexavalue_spec_36() {
        let c = 29i32;
        let got = super::lua_o_hexavalue(c);
        assert_eq!(got, -58, "scalar_39");
    }

}
