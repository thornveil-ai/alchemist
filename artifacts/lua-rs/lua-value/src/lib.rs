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

// ---- L3: number PARSING (luaO_str2num), byte-exact vs C-lua ----

/// `l_str2int`: parse an integer literal (decimal or `0x` hex). Hex overflow
/// WRAPS (Lua semantics); decimal overflow returns None (Lua then tries float).
/// Leading/trailing ASCII space is allowed; the whole (trimmed) string must be
/// consumed.
pub fn str2int(s: &[u8]) -> Option<i64> {
    let t = trim_spaces(s);
    if t.is_empty() {
        return None;
    }
    let (neg, rest) = sign(t);
    if rest.is_empty() {
        return None;
    }
    let (val, consumed) = if rest.len() >= 2 && rest[0] == b'0' && (rest[1] | 0x20) == b'x' {
        // Hex: wrapping accumulate; at least one hex digit.
        let hex = &rest[2..];
        let mut a: u64 = 0;
        let mut n = 0;
        for &c in hex {
            let d = hex_val(c)?;
            a = a.wrapping_mul(16).wrapping_add(d as u64);
            n += 1;
        }
        if n == 0 {
            return None;
        }
        (a as i64, ())
    } else {
        // Decimal: overflow -> None (fall through to float in str2num).
        let mut a: i64 = 0;
        let mut n = 0;
        for &c in rest {
            if !c.is_ascii_digit() {
                return None;
            }
            a = a.checked_mul(10)?.checked_add((c - b'0') as i64)?;
            n += 1;
        }
        if n == 0 {
            return None;
        }
        (a, ())
    };
    let _ = consumed;
    Some(if neg { val.wrapping_neg() } else { val })
}

/// `l_str2d`: parse a float literal (decimal or hex-float `0x1p4`). Rejects any
/// string containing 'n'/'N' — which is exactly how C-lua rejects `inf`/`nan`.
pub fn str2d(s: &[u8]) -> Option<f64> {
    let t = trim_spaces(s);
    if t.is_empty() {
        return None;
    }
    // Reject inf/nan the way Lua does: presence of 'n'/'N'.
    if t.iter().any(|&c| c == b'n' || c == b'N') {
        return None;
    }
    let (neg, body) = sign(t);
    let v = if body.len() >= 2 && body[0] == b'0' && (body[1] | 0x20) == b'x' {
        parse_hex_float(&body[2..])?
    } else {
        std::str::from_utf8(body).ok()?.parse::<f64>().ok()?
    };
    Some(if neg { -v } else { v })
}

/// `luaO_str2num`: integer first, else float, else not-a-number.
pub fn str2num(s: &[u8]) -> Option<LuaValue> {
    if let Some(i) = str2int(s) {
        return Some(LuaValue::Integer(i));
    }
    str2d(s).map(LuaValue::Number)
}

fn trim_spaces(s: &[u8]) -> &[u8] {
    let mut a = 0;
    let mut b = s.len();
    while a < b && s[a].is_ascii_whitespace() {
        a += 1;
    }
    while b > a && s[b - 1].is_ascii_whitespace() {
        b -= 1;
    }
    &s[a..b]
}

fn sign(s: &[u8]) -> (bool, &[u8]) {
    match s.first() {
        Some(b'-') => (true, &s[1..]),
        Some(b'+') => (false, &s[1..]),
        _ => (false, s),
    }
}

fn hex_val(c: u8) -> Option<u32> {
    match c {
        b'0'..=b'9' => Some((c - b'0') as u32),
        b'a'..=b'f' => Some((c - b'a' + 10) as u32),
        b'A'..=b'F' => Some((c - b'A' + 10) as u32),
        _ => None,
    }
}

/// Hex float `HHH.HHHpEE` (Lua/C99). Mantissa in hex, binary exponent after 'p'.
fn parse_hex_float(s: &[u8]) -> Option<f64> {
    let mut mant = 0.0f64;
    let mut any = false;
    let mut i = 0;
    while i < s.len() {
        if let Some(d) = hex_val(s[i]) {
            mant = mant * 16.0 + d as f64;
            any = true;
            i += 1;
        } else {
            break;
        }
    }
    if i < s.len() && s[i] == b'.' {
        i += 1;
        let mut scale = 1.0 / 16.0;
        while i < s.len() {
            if let Some(d) = hex_val(s[i]) {
                mant += d as f64 * scale;
                scale /= 16.0;
                any = true;
                i += 1;
            } else {
                break;
            }
        }
    }
    if !any {
        return None;
    }
    let mut exp = 0i32;
    if i < s.len() && (s[i] | 0x20) == b'p' {
        i += 1;
        let (eneg, erest) = sign(&s[i..]);
        if erest.is_empty() {
            return None;
        }
        for &c in erest {
            if !c.is_ascii_digit() {
                return None;
            }
            exp = exp.checked_mul(10)?.checked_add((c - b'0') as i32)?;
        }
        if eneg {
            exp = -exp;
        }
        i = s.len();
    }
    if i != s.len() {
        return None;
    }
    Some(mant * 2f64.powi(exp))
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
    fn number_parsing_matches_c_lua() {
        // Integers (subtype preserved).
        assert!(matches!(str2num(b"42"), Some(LuaValue::Integer(42))));
        assert!(matches!(str2num(b"  10  "), Some(LuaValue::Integer(10))));
        assert!(matches!(str2num(b"0x1A"), Some(LuaValue::Integer(26))));
        assert!(matches!(str2num(b"-7"), Some(LuaValue::Integer(-7))));
        // Hex integer overflow WRAPS (0xFFFF...F == -1).
        assert!(matches!(str2num(b"0xFFFFFFFFFFFFFFFF"), Some(LuaValue::Integer(-1))));
        // Floats (have '.', exponent, or overflow decimal).
        assert!(matches!(str2num(b"3.14"), Some(LuaValue::Number(_))));
        assert_eq!(lua_number2str(match str2num(b"1e3").unwrap() { LuaValue::Number(n)=>n, _=>0.0 }), "1000.0");
        assert!(matches!(str2num(b".5"), Some(LuaValue::Number(_))));
        assert!(matches!(str2num(b"10."), Some(LuaValue::Number(_))));
        // Hex float.
        assert!(matches!(str2num(b"0x1p4"), Some(LuaValue::Number(n)) if n == 16.0));
        // Decimal overflow -> float, not error.
        assert!(matches!(str2num(b"99999999999999999999999"), Some(LuaValue::Number(_))));
        // Rejections: inf/nan (via 'n'), garbage, empty.
        assert!(str2num(b"inf").is_none());
        assert!(str2num(b"nan").is_none());
        assert!(str2num(b"abc").is_none());
        assert!(str2num(b"").is_none());
        assert!(str2num(b"0x").is_none());
        assert!(str2num(b"1 2").is_none());
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
