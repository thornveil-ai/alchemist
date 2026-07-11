//! lua-lexer — Lua 5.4 lexical scanner (Phase C, llex.c).
//!
//! Source bytes -> token stream. Consumes the byte-exact `str2num` (numerals)
//! and the same string-escape rules as C-lua. Faithful to `llex.c`: same
//! keyword set, same operator set, long-bracket strings/comments `[==[ ]==]`,
//! `\ddd`/`\xHH`/`\u{}`/`\z` escapes, int-vs-float numeral subtype.

use lua_value::{str2num, LuaValue};

#[derive(Debug, Clone, PartialEq)]
pub enum Tok {
    // literals
    Int(i64),
    Flt(f64),
    Str(Vec<u8>),
    Name(String),
    // keywords
    And, Break, Do, Else, Elseif, End, False, For, Function, Goto, If, In,
    Local, Nil, Not, Or, Repeat, Return, Then, True, Until, While,
    // symbols
    Plus, Minus, Star, Slash, DSlash, Percent, Caret, Hash,
    Amp, Tilde, Pipe, Shl, Shr,
    Eq, Ne, Le, Ge, Lt, Gt, Assign,
    LParen, RParen, LBrace, RBrace, LBrack, RBrack,
    DColon, Semi, Colon, Comma, Dot, Concat, Ellipsis,
    Eos,
}

#[derive(Debug)]
pub struct LexError {
    pub msg: String,
    pub line: u32,
}

fn keyword(s: &str) -> Option<Tok> {
    Some(match s {
        "and" => Tok::And, "break" => Tok::Break, "do" => Tok::Do,
        "else" => Tok::Else, "elseif" => Tok::Elseif, "end" => Tok::End,
        "false" => Tok::False, "for" => Tok::For, "function" => Tok::Function,
        "goto" => Tok::Goto, "if" => Tok::If, "in" => Tok::In,
        "local" => Tok::Local, "nil" => Tok::Nil, "not" => Tok::Not,
        "or" => Tok::Or, "repeat" => Tok::Repeat, "return" => Tok::Return,
        "then" => Tok::Then, "true" => Tok::True, "until" => Tok::Until,
        "while" => Tok::While,
        _ => return None,
    })
}

struct Lexer<'a> {
    s: &'a [u8],
    i: usize,
    line: u32,
}

impl<'a> Lexer<'a> {
    fn err(&self, m: &str) -> LexError {
        LexError { msg: m.to_string(), line: self.line }
    }
    fn peek(&self) -> u8 {
        if self.i < self.s.len() { self.s[self.i] } else { 0 }
    }
    fn peek2(&self) -> u8 {
        if self.i + 1 < self.s.len() { self.s[self.i + 1] } else { 0 }
    }
    fn bump(&mut self) -> u8 {
        let c = self.peek();
        self.i += 1;
        c
    }
    fn newline(&mut self) {
        // \n, \r, \n\r, \r\n all count as ONE line increment (llex curr_is_newline).
        let old = self.s[self.i];
        self.i += 1;
        let c = self.peek();
        if (c == b'\n' || c == b'\r') && c != old {
            self.i += 1;
        }
        self.line += 1;
    }

    /// A long bracket opener `[==[` returns Some(level); else None (rewinds).
    fn check_long_bracket(&mut self) -> Option<usize> {
        let start = self.i;
        if self.peek() != b'[' {
            return None;
        }
        self.i += 1;
        let mut level = 0;
        while self.peek() == b'=' {
            level += 1;
            self.i += 1;
        }
        if self.peek() == b'[' {
            self.i += 1;
            Some(level)
        } else {
            self.i = start;
            None
        }
    }

    fn read_long(&mut self, level: usize) -> Result<Vec<u8>, LexError> {
        let mut out = Vec::new();
        // A newline right after the opener is skipped.
        if self.peek() == b'\n' || self.peek() == b'\r' {
            self.newline();
        }
        loop {
            match self.peek() {
                0 => return Err(self.err("unfinished long string/comment")),
                b']' => {
                    let save = self.i;
                    self.i += 1;
                    let mut n = 0;
                    while self.peek() == b'=' {
                        n += 1;
                        self.i += 1;
                    }
                    if n == level && self.peek() == b']' {
                        self.i += 1;
                        return Ok(out);
                    }
                    self.i = save;
                    out.push(self.bump());
                }
                b'\n' | b'\r' => {
                    out.push(b'\n');
                    self.newline();
                }
                _ => out.push(self.bump()),
            }
        }
    }

    fn read_string(&mut self, quote: u8) -> Result<Vec<u8>, LexError> {
        let mut out = Vec::new();
        loop {
            let c = self.peek();
            match c {
                0 | b'\n' | b'\r' => return Err(self.err("unfinished string")),
                _ if c == quote => {
                    self.i += 1;
                    return Ok(out);
                }
                b'\\' => {
                    self.i += 1;
                    let e = self.peek();
                    match e {
                        b'n' => { out.push(b'\n'); self.i += 1; }
                        b't' => { out.push(b'\t'); self.i += 1; }
                        b'r' => { out.push(b'\r'); self.i += 1; }
                        b'a' => { out.push(7); self.i += 1; }
                        b'b' => { out.push(8); self.i += 1; }
                        b'f' => { out.push(12); self.i += 1; }
                        b'v' => { out.push(11); self.i += 1; }
                        b'\\' => { out.push(b'\\'); self.i += 1; }
                        b'"' => { out.push(b'"'); self.i += 1; }
                        b'\'' => { out.push(b'\''); self.i += 1; }
                        b'\n' | b'\r' => { out.push(b'\n'); self.newline(); }
                        b'x' => {
                            self.i += 1;
                            let mut v = 0u32;
                            for _ in 0..2 {
                                let h = hexd(self.peek()).ok_or_else(|| self.err("hexadecimal digit expected"))?;
                                v = v * 16 + h;
                                self.i += 1;
                            }
                            out.push(v as u8);
                        }
                        b'z' => {
                            self.i += 1;
                            while self.peek().is_ascii_whitespace() {
                                if self.peek() == b'\n' || self.peek() == b'\r' {
                                    self.newline();
                                } else {
                                    self.i += 1;
                                }
                            }
                        }
                        b'0'..=b'9' => {
                            let mut v = 0u32;
                            for _ in 0..3 {
                                if !self.peek().is_ascii_digit() {
                                    break;
                                }
                                v = v * 10 + (self.bump() - b'0') as u32;
                            }
                            if v > 255 {
                                return Err(self.err("decimal escape too large"));
                            }
                            out.push(v as u8);
                        }
                        _ => return Err(self.err("invalid escape sequence")),
                    }
                }
                _ => out.push(self.bump()),
            }
        }
    }

    fn read_numeral(&mut self) -> Result<Tok, LexError> {
        let start = self.i;
        let hex = self.peek() == b'0' && (self.peek2() | 0x20) == b'x';
        if hex {
            self.i += 2;
        }
        let (exp_e, exp_p): (&[u8], &[u8]) = if hex { (b"pP", b"pP") } else { (b"eE", b"eE") };
        let _ = exp_p;
        loop {
            let c = self.peek();
            if c == b'.' || is_digit_for(c, hex) {
                self.i += 1;
            } else if exp_e.contains(&c) {
                self.i += 1;
                if self.peek() == b'+' || self.peek() == b'-' {
                    self.i += 1;
                }
            } else {
                break;
            }
        }
        let text = &self.s[start..self.i];
        match str2num(text) {
            Some(LuaValue::Integer(n)) => Ok(Tok::Int(n)),
            Some(LuaValue::Number(f)) => Ok(Tok::Flt(f)),
            _ => Err(self.err("malformed number")),
        }
    }
}

fn hexd(c: u8) -> Option<u32> {
    match c {
        b'0'..=b'9' => Some((c - b'0') as u32),
        b'a'..=b'f' => Some((c - b'a' + 10) as u32),
        b'A'..=b'F' => Some((c - b'A' + 10) as u32),
        _ => None,
    }
}
fn is_digit_for(c: u8, hex: bool) -> bool {
    if hex { c.is_ascii_hexdigit() } else { c.is_ascii_digit() }
}

/// Tokenize a whole chunk. Returns tokens (line info folded away for now) ending
/// in `Eos`, or the first lexical error.
pub fn tokenize(src: &[u8]) -> Result<Vec<Tok>, LexError> {
    let mut lx = Lexer { s: src, i: 0, line: 1 };
    let mut out = Vec::new();
    // Skip a shebang line.
    if lx.s.starts_with(b"#") {
        while lx.peek() != b'\n' && lx.peek() != 0 {
            lx.i += 1;
        }
    }
    loop {
        let c = lx.peek();
        match c {
            0 => { out.push(Tok::Eos); return Ok(out); }
            b' ' | b'\t' | 0x0b | 0x0c => { lx.i += 1; }
            b'\n' | b'\r' => lx.newline(),
            b'-' if lx.peek2() == b'-' => {
                lx.i += 2;
                if let Some(level) = lx.check_long_bracket() {
                    lx.read_long(level)?; // long comment
                } else {
                    while lx.peek() != b'\n' && lx.peek() != b'\r' && lx.peek() != 0 {
                        lx.i += 1;
                    }
                }
            }
            b'"' | b'\'' => { lx.i += 1; let s = lx.read_string(c)?; out.push(Tok::Str(s)); }
            b'[' if lx.peek2() == b'[' || lx.peek2() == b'=' => {
                if let Some(level) = lx.check_long_bracket() {
                    let s = lx.read_long(level)?;
                    out.push(Tok::Str(s));
                } else {
                    lx.i += 1;
                    out.push(Tok::LBrack);
                }
            }
            b'0'..=b'9' => out.push(lx.read_numeral()?),
            b'.' if lx.peek2().is_ascii_digit() => out.push(lx.read_numeral()?),
            c if c == b'_' || c.is_ascii_alphabetic() => {
                let start = lx.i;
                while { let d = lx.peek(); d == b'_' || d.is_ascii_alphanumeric() } {
                    lx.i += 1;
                }
                let name = std::str::from_utf8(&lx.s[start..lx.i]).unwrap().to_string();
                out.push(keyword(&name).unwrap_or(Tok::Name(name)));
            }
            _ => out.push(lx.read_symbol()?),
        }
    }
}

impl<'a> Lexer<'a> {
    fn read_symbol(&mut self) -> Result<Tok, LexError> {
        let c = self.bump();
        let t = match c {
            b'+' => Tok::Plus,
            b'-' => Tok::Minus,
            b'*' => Tok::Star,
            b'/' => if self.peek() == b'/' { self.i += 1; Tok::DSlash } else { Tok::Slash },
            b'%' => Tok::Percent,
            b'^' => Tok::Caret,
            b'#' => Tok::Hash,
            b'&' => Tok::Amp,
            b'~' => if self.peek() == b'=' { self.i += 1; Tok::Ne } else { Tok::Tilde },
            b'|' => Tok::Pipe,
            b'<' => match self.peek() {
                b'<' => { self.i += 1; Tok::Shl }
                b'=' => { self.i += 1; Tok::Le }
                _ => Tok::Lt,
            },
            b'>' => match self.peek() {
                b'>' => { self.i += 1; Tok::Shr }
                b'=' => { self.i += 1; Tok::Ge }
                _ => Tok::Gt,
            },
            b'=' => if self.peek() == b'=' { self.i += 1; Tok::Eq } else { Tok::Assign },
            b'(' => Tok::LParen,
            b')' => Tok::RParen,
            b'{' => Tok::LBrace,
            b'}' => Tok::RBrace,
            b'[' => Tok::LBrack,
            b']' => Tok::RBrack,
            b';' => Tok::Semi,
            b':' => if self.peek() == b':' { self.i += 1; Tok::DColon } else { Tok::Colon },
            b',' => Tok::Comma,
            b'.' => {
                if self.peek() == b'.' {
                    self.i += 1;
                    if self.peek() == b'.' { self.i += 1; Tok::Ellipsis } else { Tok::Concat }
                } else {
                    Tok::Dot
                }
            }
            _ => return Err(self.err("unexpected symbol")),
        };
        Ok(t)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn lex(s: &str) -> Vec<Tok> {
        tokenize(s.as_bytes()).unwrap()
    }

    #[test]
    fn keywords_names_ops() {
        assert_eq!(
            lex("local x = 1 + 2"),
            vec![Tok::Local, Tok::Name("x".into()), Tok::Assign, Tok::Int(1), Tok::Plus, Tok::Int(2), Tok::Eos]
        );
    }

    #[test]
    fn numerals_int_vs_float() {
        assert_eq!(lex("42"), vec![Tok::Int(42), Tok::Eos]);
        assert_eq!(lex("3.14"), vec![Tok::Flt(3.14), Tok::Eos]);
        assert_eq!(lex("0x1A"), vec![Tok::Int(26), Tok::Eos]);
        assert_eq!(lex("1e3"), vec![Tok::Flt(1000.0), Tok::Eos]);
        assert_eq!(lex("0x1p4"), vec![Tok::Flt(16.0), Tok::Eos]);
        assert_eq!(lex(".5"), vec![Tok::Flt(0.5), Tok::Eos]);
    }

    #[test]
    fn strings_and_escapes() {
        assert_eq!(lex(r#""hi\n\tthere""#), vec![Tok::Str(b"hi\n\tthere".to_vec()), Tok::Eos]);
        assert_eq!(lex(r#""\65\66""#), vec![Tok::Str(b"AB".to_vec()), Tok::Eos]);
        assert_eq!(lex(r#""\x48\x49""#), vec![Tok::Str(b"HI".to_vec()), Tok::Eos]);
        assert_eq!(lex("[[raw\nstring]]"), vec![Tok::Str(b"raw\nstring".to_vec()), Tok::Eos]);
        assert_eq!(lex("[==[a]]b]==]"), vec![Tok::Str(b"a]]b".to_vec()), Tok::Eos]);
    }

    #[test]
    fn comments_and_all_operators() {
        assert_eq!(lex("-- line comment\n5"), vec![Tok::Int(5), Tok::Eos]);
        assert_eq!(lex("--[[ block\ncomment ]] 6"), vec![Tok::Int(6), Tok::Eos]);
        assert_eq!(
            lex("// % ^ # & ~ | << >> == ~= <= >= .. ... ::"),
            vec![Tok::DSlash, Tok::Percent, Tok::Caret, Tok::Hash, Tok::Amp,
                 Tok::Tilde, Tok::Pipe, Tok::Shl, Tok::Shr, Tok::Eq, Tok::Ne,
                 Tok::Le, Tok::Ge, Tok::Concat, Tok::Ellipsis, Tok::DColon, Tok::Eos]
        );
    }

    #[test]
    fn a_whole_function() {
        let toks = lex("function f(a, b) return a + b end");
        assert_eq!(toks[0], Tok::Function);
        assert_eq!(toks[1], Tok::Name("f".into()));
        assert_eq!(*toks.last().unwrap(), Tok::Eos);
        assert!(toks.contains(&Tok::Return));
    }
}
