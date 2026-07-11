//! lua-value — the Lua 5.4 value universe in safe Rust (Phase C / C1).
//!
//! `LuaValue` is the safe-Rust mapping of C's `TValue` tagged union (ADR-1).
//! This crate owns the byte-exact *observable* numeric/string semantics that
//! the whole interpreter depends on — number formatting (`%.14g` + Lua's `.0`
//! rule), integer/float subtypes, floor-div / modulo / pow, overflow wrap.
//! Everything here is verified against reference C-lua via the C2 oracle.
#![allow(clippy::needless_return)]

use std::rc::Rc;

/// Lua's value model. Tag (C `tt_`) → enum discriminant; union → payload (ADR-1).
/// Integer vs Number preserves Lua's observable numeric subtype (`math.type`).
#[derive(Clone)]
pub enum LuaValue {
    Nil,
    Boolean(bool),
    Integer(i64),          // lua_Integer, LUA_VNUMINT
    Number(f64),           // lua_Number,  LUA_VNUMFLT
    Str(Rc<[u8]>),         // interned byte string (ADR-4)
    // Table/Function/UserData/Thread land as later C3 crates carry their types.
}

impl LuaValue {
    /// `type(v)` — the basic type name (8 basic types).
    pub fn type_name(&self) -> &'static str {
        match self {
            LuaValue::Nil => "nil",
            LuaValue::Boolean(_) => "boolean",
            LuaValue::Integer(_) | LuaValue::Number(_) => "number",
            LuaValue::Str(_) => "string",
        }
    }

    /// `math.type(v)` — "integer" | "float" | nil(None) for non-numbers.
    pub fn math_type(&self) -> Option<&'static str> {
        match self {
            LuaValue::Integer(_) => Some("integer"),
            LuaValue::Number(_) => Some("float"),
            _ => None,
        }
    }

    /// Lua truthiness: only `nil` and `false` are falsy.
    pub fn is_truthy(&self) -> bool {
        !matches!(self, LuaValue::Nil | LuaValue::Boolean(false))
    }

    /// `tostring(v)` for the primitive cases (string/number/nil/bool).
    pub fn tostring(&self) -> String {
        match self {
            LuaValue::Nil => "nil".to_string(),
            LuaValue::Boolean(b) => if *b { "true".into() } else { "false".into() },
            LuaValue::Integer(i) => i.to_string(),
            LuaValue::Number(n) => lua_number2str(*n),
            LuaValue::Str(s) => String::from_utf8_lossy(s).into_owned(),
        }
    }
}

/// C `%.14g` (Lua's `LUAI_NUMFFORMAT`) in safe Rust — the byte-exact-hard piece.
/// %g: precision = significant digits; picks %f when `-4 <= exp < P`, else %e;
/// strips trailing zeros and a trailing '.'. Also matches glibc `inf`/`nan`.
pub fn fmt_g(n: f64, prec: usize) -> String {
    if n.is_nan() {
        return if n.is_sign_negative() { "-nan".into() } else { "nan".into() };
    }
    if n.is_infinite() {
        return if n < 0.0 { "-inf".into() } else { "inf".into() };
    }
    let p = if prec == 0 { 1 } else { prec };
    if n == 0.0 {
        return if n.is_sign_negative() { "-0".into() } else { "0".into() };
    }
    // Decimal exponent X from the %e form with (p-1) fraction digits (this also
    // applies %e's round-half-to-even at the right precision).
    let e_form = format!("{:.*e}", p - 1, n); // e.g. "3.3333333333333e-1"
    let exp: i32 = e_form
        .rsplit('e')
        .next()
        .and_then(|s| s.parse().ok())
        .unwrap_or(0);
    if exp >= -4 && (exp as i64) < p as i64 {
        // %f branch: (p-1-exp) fraction digits, then strip trailing zeros/'.'
        let frac = (p as i32 - 1 - exp).max(0) as usize;
        let s = format!("{:.*}", frac, n);
        strip_trailing(&s)
    } else {
        // %e branch: mantissa stripped, C-style exponent `e[+-]NN` (>=2 digits).
        let (mant, e) = e_form.split_once('e').unwrap();
        let mant = strip_trailing(mant);
        let sign = if e.starts_with('-') { '-' } else { '+' };
        let digits = e.trim_start_matches(['-', '+']);
        let digits = if digits.len() < 2 { format!("0{digits}") } else { digits.to_string() };
        format!("{mant}e{sign}{digits}")
    }
}

fn strip_trailing(s: &str) -> String {
    if !s.contains('.') {
        return s.to_string();
    }
    let t = s.trim_end_matches('0');
    let t = t.trim_end_matches('.');
    t.to_string()
}

/// `lua_number2str`: format a float with `%.14g`, then append `.0` when the
/// result reads as a plain integer (so `1024.0`, `inf` stays `inf`).
pub fn lua_number2str(n: f64) -> String {
    let s = fmt_g(n, 14);
    // Append ".0" only if the whole thing is [-]digits (an int-looking float).
    let looks_int = {
        let body = s.strip_prefix('-').unwrap_or(&s);
        !body.is_empty() && body.bytes().all(|b| b.is_ascii_digit())
    };
    if looks_int { format!("{s}.0") } else { s }
}

// ---- Lua 5.4 integer/float arithmetic (observable semantics) ----

/// Floor division for integers (Lua `//`): rounds toward -inf; wraps like C.
pub fn iflordiv(a: i64, b: i64) -> Option<i64> {
    if b == 0 {
        return None; // caller raises "attempt to perform 'n//0'"
    }
    // Rust `/` truncates toward zero; adjust to floor for mixed signs.
    let q = a.wrapping_div(b);
    let r = a.wrapping_rem(b);
    if (r != 0) && ((r < 0) != (b < 0)) {
        Some(q - 1)
    } else {
        Some(q)
    }
}

/// Integer modulo (Lua `%`): result has the sign of the divisor.
pub fn imod(a: i64, b: i64) -> Option<i64> {
    if b == 0 {
        return None;
    }
    let r = a.wrapping_rem(b);
    if r != 0 && ((r < 0) != (b < 0)) {
        Some(r + b)
    } else {
        Some(r)
    }
}

/// Float floor division (Lua `//` on floats): `floor(a/b)`.
pub fn ffloordiv(a: f64, b: f64) -> f64 {
    (a / b).floor()
}

/// Float modulo (Lua `%` on floats): `a - floor(a/b)*b`, with Lua's edge rules.
pub fn fmod_lua(a: f64, b: f64) -> f64 {
    let m = a % b;
    if m != 0.0 && (m < 0.0) != (b < 0.0) {
        m + b
    } else {
        m
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn number_formatting_matches_c_lua() {
        // Golden values captured from C-lua 5.4.7 (subjects/lua/oracle).
        assert_eq!(lua_number2str(1024.0), "1024.0"); // 2^10
        assert_eq!(lua_number2str(3.5), "3.5");
        assert_eq!(lua_number2str(3.0), "3.0"); // 7.0//2
        assert_eq!(lua_number2str(0.5), "0.5");
        assert_eq!(lua_number2str(3.14), "3.14");
        assert_eq!(lua_number2str(1.0 / 3.0), "0.33333333333333");
        assert_eq!(lua_number2str(f64::INFINITY), "inf");
        assert_eq!(lua_number2str(f64::NEG_INFINITY), "-inf");
        assert_eq!(fmt_g(1000.0, 14), "1000"); // %.14g of 1e3, before .0 rule
        assert_eq!(lua_number2str(1000.0), "1000.0");
    }

    #[test]
    fn big_and_small_use_e_notation_like_c() {
        assert_eq!(fmt_g(1e20, 14), "1e+20");
        assert_eq!(fmt_g(1e-10, 14), "1e-10");
        assert_eq!(fmt_g(1.5e300, 14), "1.5e+300");
    }

    #[test]
    fn integer_semantics() {
        assert_eq!(i64::MAX.wrapping_add(1), i64::MIN); // maxinteger+1 wraps
        assert_eq!(iflordiv(20, 6), Some(3));
        assert_eq!(iflordiv(-20, 6), Some(-4)); // floor toward -inf
        assert_eq!(imod(20, 6), Some(2));
        assert_eq!(imod(-1, 3), Some(2)); // sign of divisor
        assert_eq!(iflordiv(1, 0), None);
    }

    #[test]
    fn subtypes_and_truth() {
        assert_eq!(LuaValue::Integer(3).math_type(), Some("integer"));
        assert_eq!(LuaValue::Number(3.0).math_type(), Some("float"));
        assert_eq!(LuaValue::Str(Rc::from(&b"x"[..])).math_type(), None);
        assert!(!LuaValue::Nil.is_truthy());
        assert!(!LuaValue::Boolean(false).is_truthy());
        assert!(LuaValue::Integer(0).is_truthy()); // 0 is truthy in Lua
    }
}
