//! lua-table — Lua 5.4 table: array part + hash part (Phase C, ltable.c).
//!
//! A Lua table is a hybrid: a dense array part for integer keys `1..=n` and a
//! hash part for everything else. Key semantics that MUST match C-lua:
//!  * float keys with an exact integer value collapse to integer keys
//!    (`t[2.0]` is `t[2]`);
//!  * `nil` and `NaN` are invalid keys;
//!  * the length operator `#` returns a *border* `n` (`t[n]~=nil, t[n+1]==nil`).
//! Verified against C-lua via the C2 oracle (03_tables) + unit tests.

use std::collections::HashMap;
use lua_value::LuaValue;

/// A normalized, hashable table key. `nil`/`NaN` are rejected before boxing.
#[derive(Clone)]
enum Key {
    Int(i64),
    Num(u64), // f64 bits, only for non-integer floats
    Bool(bool),
    Str(std::rc::Rc<[u8]>),
}

impl PartialEq for Key {
    fn eq(&self, o: &Self) -> bool {
        match (self, o) {
            (Key::Int(a), Key::Int(b)) => a == b,
            (Key::Num(a), Key::Num(b)) => a == b,
            (Key::Bool(a), Key::Bool(b)) => a == b,
            (Key::Str(a), Key::Str(b)) => a == b,
            _ => false,
        }
    }
}
impl Eq for Key {}
impl std::hash::Hash for Key {
    fn hash<H: std::hash::Hasher>(&self, h: &mut H) {
        match self {
            Key::Int(i) => { 0u8.hash(h); i.hash(h); }
            Key::Num(b) => { 1u8.hash(h); b.hash(h); }
            Key::Bool(b) => { 2u8.hash(h); b.hash(h); }
            Key::Str(s) => { 3u8.hash(h); s.hash(h); }
        }
    }
}

/// Collapse a key to its canonical form; `None` for invalid (`nil`/`NaN`).
/// Returns `Ok(Some(i))` when the key normalizes to integer `i` (array-eligible).
fn to_key(v: &LuaValue) -> Option<(Key, Option<i64>)> {
    match v {
        LuaValue::Nil => None,
        LuaValue::Boolean(b) => Some((Key::Bool(*b), None)),
        LuaValue::Integer(i) => Some((Key::Int(*i), Some(*i))),
        LuaValue::Number(f) => {
            if f.is_nan() {
                return None;
            }
            // Float with exact integer value -> integer key (Lua 5.4 rule).
            if f.floor() == *f && f.is_finite() && *f >= i64::MIN as f64 && *f <= i64::MAX as f64 {
                let i = *f as i64;
                Some((Key::Int(i), Some(i)))
            } else {
                Some((Key::Num(f.to_bits()), None))
            }
        }
        LuaValue::Str(s) => Some((Key::Str(s.clone()), None)),
    }
}

/// Lua table (`Table` in lobject.h).
#[derive(Default)]
pub struct Table {
    array: Vec<LuaValue>, // 1-based: array[i-1] holds key i, for i in 1..=array.len()
    hash: HashMap<Key, LuaValue>,
}

impl Table {
    pub fn new() -> Self {
        Table::default()
    }

    /// `luaH_get` — raw get (no metamethods). Missing keys read as `nil`.
    pub fn get(&self, key: &LuaValue) -> LuaValue {
        match to_key(key) {
            None => LuaValue::Nil,
            Some((_, Some(i))) if i >= 1 && (i as usize) <= self.array.len() => {
                self.array[(i - 1) as usize].clone()
            }
            Some((k, _)) => self.hash.get(&k).cloned().unwrap_or(LuaValue::Nil),
        }
    }

    pub fn get_int(&self, i: i64) -> LuaValue {
        self.get(&LuaValue::Integer(i))
    }

    /// `luaH_set` — raw set (no metamethods). Setting `nil` deletes the key.
    /// Panics-free; returns false for an invalid key (`nil`/`NaN`), which the
    /// caller surfaces as the Lua error "table index is nil/NaN".
    pub fn set(&mut self, key: LuaValue, val: LuaValue) -> bool {
        let (k, as_int) = match to_key(&key) {
            None => return false,
            Some(x) => x,
        };
        if let Some(i) = as_int {
            let n = self.array.len() as i64;
            if i >= 1 && i <= n {
                self.array[(i - 1) as usize] = val;
                return true;
            }
            if i == n + 1 && !matches!(val, LuaValue::Nil) {
                // Append; then migrate any now-contiguous keys from the hash part.
                self.array.push(val);
                self.absorb_from_hash();
                return true;
            }
        }
        if matches!(val, LuaValue::Nil) {
            self.hash.remove(&k);
        } else {
            self.hash.insert(k, val);
        }
        true
    }

    pub fn set_int(&mut self, i: i64, val: LuaValue) -> bool {
        self.set(LuaValue::Integer(i), val)
    }

    /// Pull keys `array.len()+1, +2, ...` out of the hash part into the array
    /// once an append makes them contiguous (mirrors C-lua's rehash growth in
    /// its observable effect on `#`).
    fn absorb_from_hash(&mut self) {
        loop {
            let next = self.array.len() as i64 + 1;
            match self.hash.remove(&Key::Int(next)) {
                Some(v) => self.array.push(v),
                None => break,
            }
        }
    }

    /// `luaH_getn` — the length operator `#`: a border `n` with `t[n]~=nil` and
    /// `t[n+1]==nil`. For a proper sequence this is the count; with trailing
    /// nils in the array we binary-search a border, matching C-lua.
    pub fn len(&self) -> i64 {
        let n = self.array.len();
        if n > 0 && matches!(self.array[n - 1], LuaValue::Nil) {
            // Binary search for a border within the array [0, n].
            let (mut lo, mut hi) = (0usize, n);
            while hi - lo > 1 {
                let mid = (lo + hi) / 2;
                if matches!(self.array[mid - 1], LuaValue::Nil) {
                    hi = mid;
                } else {
                    lo = mid;
                }
            }
            return lo as i64;
        }
        // Array part is full; probe the hash part for a continuation border.
        if self.hash.is_empty() {
            return n as i64;
        }
        let mut i = n as i64;
        let mut j = i + 1;
        while !matches!(self.hash_get_int(j), LuaValue::Nil) {
            i = j;
            if j > i64::MAX / 2 {
                // Degenerate; linear scan (rare).
                let mut k = i + 1;
                while !matches!(self.hash_get_int(k), LuaValue::Nil) {
                    k += 1;
                }
                return k - 1;
            }
            j *= 2;
        }
        while j - i > 1 {
            let m = (i + j) / 2;
            if matches!(self.hash_get_int(m), LuaValue::Nil) {
                j = m;
            } else {
                i = m;
            }
        }
        i
    }

    fn hash_get_int(&self, i: i64) -> LuaValue {
        self.hash.get(&Key::Int(i)).cloned().unwrap_or(LuaValue::Nil)
    }

    pub fn is_empty(&self) -> bool {
        self.hash.is_empty() && self.array.iter().all(|v| matches!(v, LuaValue::Nil))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::rc::Rc;

    fn s(b: &str) -> LuaValue {
        LuaValue::Str(Rc::from(b.as_bytes()))
    }

    #[test]
    fn array_get_set_and_length() {
        let mut t = Table::new();
        for i in 1..=5 {
            t.set_int(i, LuaValue::Integer(i * i));
        }
        assert_eq!(t.len(), 5);
        assert!(matches!(t.get_int(3), LuaValue::Integer(9)));
        assert!(matches!(t.get_int(6), LuaValue::Nil));
    }

    #[test]
    fn float_key_collapses_to_integer() {
        let mut t = Table::new();
        t.set(LuaValue::Number(2.0), s("two"));
        // t[2] must read what t[2.0] wrote.
        assert!(matches!(t.get_int(2), LuaValue::Str(_)));
        assert_eq!(t.get_int(2).tostring(), "two");
        assert_eq!(t.len(), 0); // key 1 absent -> border 0 (2 is in array? no; 1 missing)
    }

    #[test]
    fn hash_part_and_mixed_keys() {
        let mut t = Table::new();
        t.set(s("name"), s("lua"));
        t.set(LuaValue::Boolean(true), LuaValue::Integer(1));
        t.set_int(100, LuaValue::Integer(7)); // sparse -> hash
        assert_eq!(t.get(&s("name")).tostring(), "lua");
        assert!(matches!(t.get(&LuaValue::Boolean(true)), LuaValue::Integer(1)));
        assert!(matches!(t.get_int(100), LuaValue::Integer(7)));
        assert!(matches!(t.get_int(1), LuaValue::Nil));
    }

    #[test]
    fn nil_deletes_and_invalid_keys_rejected() {
        let mut t = Table::new();
        t.set_int(1, LuaValue::Integer(10));
        t.set_int(2, LuaValue::Integer(20));
        assert_eq!(t.len(), 2);
        t.set_int(2, LuaValue::Nil); // delete tail
        assert_eq!(t.len(), 1);
        assert!(!t.set(LuaValue::Nil, LuaValue::Integer(1))); // nil key rejected
        assert!(!t.set(LuaValue::Number(f64::NAN), LuaValue::Integer(1))); // NaN rejected
    }

    #[test]
    fn append_absorbs_contiguous_hash_keys() {
        let mut t = Table::new();
        t.set_int(1, LuaValue::Integer(1));
        t.set_int(3, LuaValue::Integer(3)); // goes to hash (gap at 2)
        t.set_int(2, LuaValue::Integer(2)); // append -> should absorb 3
        assert_eq!(t.len(), 3);
        assert!(matches!(t.get_int(3), LuaValue::Integer(3)));
    }
}
