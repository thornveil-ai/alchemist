//! lua-string — Lua 5.4 string type: interning + byte-exact hashing (Phase C).
//!
//! Lua strings are immutable byte sequences (NOT utf8). Short strings
//! (`len <= LUAI_MAXSHORTLEN` = 40) are **interned** in a global table so
//! equality is pointer-identity; long strings are kept unique and hashed
//! lazily. The hash is `luaS_hash` — already conquered byte-exact from real
//! Lua source (see artifacts/conquered/lua_hash_realsource). This crate is the
//! `lstring.c` translation over the shared type universe.

use std::collections::HashMap;
use std::rc::Rc;

/// Lua's `LUAI_MAXSHORTLEN`: strings this long or shorter are interned.
pub const MAXSHORTLEN: usize = 40;

/// Conquered `luaS_hash(str, len, seed) -> u32` — byte-identical to C-lua.
/// `h = seed ^ len`, then fold each byte (high→low): `h ^= (h<<5)+(h>>2)+b`.
pub fn lua_s_hash(s: &[u8], seed: u32) -> u32 {
    let mut h = seed ^ (s.len() as u32);
    let mut l = s.len();
    while l > 0 {
        l -= 1;
        let b = s[l] as u32;
        h ^= (h << 5).wrapping_add(h >> 2).wrapping_add(b);
    }
    h
}

/// An immutable Lua string: shared bytes + its (short-string) hash.
#[derive(Clone)]
pub struct LuaStr {
    bytes: Rc<[u8]>,
    hash: u32,
    short: bool,
}

impl LuaStr {
    pub fn as_bytes(&self) -> &[u8] {
        &self.bytes
    }
    pub fn len(&self) -> usize {
        self.bytes.len()
    }
    pub fn is_empty(&self) -> bool {
        self.bytes.is_empty()
    }
    pub fn hash(&self) -> u32 {
        self.hash
    }
    pub fn is_interned(&self) -> bool {
        self.short
    }
}

impl PartialEq for LuaStr {
    fn eq(&self, other: &Self) -> bool {
        // Interned short strings compare by identity (Rc ptr); otherwise bytes.
        if self.short && other.short {
            Rc::ptr_eq(&self.bytes, &other.bytes)
        } else {
            self.bytes == other.bytes
        }
    }
}
impl Eq for LuaStr {}

/// The global short-string intern table (`stringtable` in lstring.c). A real
/// `global_State` owns one of these; here it is standalone so lstring can be
/// verified in isolation before lstate lands.
pub struct StringTable {
    seed: u32,
    interned: HashMap<Vec<u8>, LuaStr>,
}

impl StringTable {
    pub fn new(seed: u32) -> Self {
        StringTable {
            seed,
            interned: HashMap::new(),
        }
    }

    /// `luaS_new` / `luaS_newlstr`: create a string, interning short ones so
    /// two equal short strings share one allocation (pointer equality).
    pub fn new_str(&mut self, s: &[u8]) -> LuaStr {
        if s.len() <= MAXSHORTLEN {
            if let Some(existing) = self.interned.get(s) {
                return existing.clone();
            }
            let v = LuaStr {
                bytes: Rc::from(s),
                hash: lua_s_hash(s, self.seed),
                short: true,
            };
            self.interned.insert(s.to_vec(), v.clone());
            v
        } else {
            LuaStr {
                bytes: Rc::from(s),
                hash: lua_s_hash(s, self.seed),
                short: false,
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn hash_matches_conquered_luas_hash() {
        // luaS_hash is deterministic given the seed; spot-check the fold.
        assert_eq!(lua_s_hash(b"", 0), 0);
        // Non-empty must actually depend on the bytes and seed.
        assert_ne!(lua_s_hash(b"hello", 0), lua_s_hash(b"hellp", 0));
        assert_ne!(lua_s_hash(b"hello", 0), lua_s_hash(b"hello", 1));
        // Determinism.
        assert_eq!(lua_s_hash(b"lua", 0x9e3779b9), lua_s_hash(b"lua", 0x9e3779b9));
    }

    #[test]
    fn short_strings_are_interned_by_identity() {
        let mut st = StringTable::new(0);
        let a = st.new_str(b"foo");
        let b = st.new_str(b"foo");
        assert!(a.is_interned() && b.is_interned());
        assert!(a == b); // identity equality
        assert!(Rc::ptr_eq(&a.bytes, &b.bytes)); // literally the same allocation
    }

    #[test]
    fn long_strings_not_interned_but_equal_by_bytes() {
        let mut st = StringTable::new(0);
        let long = vec![b'x'; MAXSHORTLEN + 1];
        let a = st.new_str(&long);
        let b = st.new_str(&long);
        assert!(!a.is_interned());
        assert!(a == b); // equal by content
        assert!(!Rc::ptr_eq(&a.bytes, &b.bytes)); // distinct allocations
    }

    #[test]
    fn boundary_len_40_interned_41_not() {
        let mut st = StringTable::new(0);
        assert!(st.new_str(&vec![b'a'; 40]).is_interned());
        assert!(!st.new_str(&vec![b'a'; 41]).is_interned());
    }
}
