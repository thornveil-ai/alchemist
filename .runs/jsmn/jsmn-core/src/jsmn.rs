//! Jsmn
//!
//! Module containing 2 functions: jsmn_parse, jsmn_init

#![allow(unused_variables, unused_imports, dead_code)]

use crate::*;

#[derive(Clone)]
pub struct ParserState {
    pub pos: u32,
    pub toknext: u32,
    pub toksuper: i32,
}
impl Default for ParserState {
    fn default() -> Self { Self { pos: 0, toknext: 0, toksuper: 0 } }
}

#[derive(Clone)]
pub struct Token {
    pub r#type: i32,
    pub start: i32,
    pub end: i32,
    pub size: i32,
    pub parent: i32,
}
impl Default for Token {
    fn default() -> Self { Self { r#type: 0, start: 0, end: 0, size: 0, parent: 0 } }
}

pub fn jsmn_parse(parser: &mut ParserState, js: &str, tokens: Option<&mut [Token]>) -> Result<usize, ParseError> {
    unimplemented!("refused: jsmn_parse — no verified translation")
}

/// Jsmn Init
/// Initializes the state of a JSON parser to its starting configuration.
pub fn jsmn_init(parser: &mut ParserState) {
    parser.pos = 0;
    parser.toknext = 0;
    parser.toksuper = -1;
}

#[cfg(test)]
mod tests {
    #![allow(unused_imports, unused_variables, unused_macros)]
    extern crate alloc;
    use alloc::format;
    use alloc::string::String;

    #[test]
    fn test_jsmn_parse_body_0() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, 0, "return");  }
            Err(_) => { assert!(0 < 0, "expected error return 0"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_1() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[123, 125];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, 1, "return"); assert_eq!(toks[0].r#type as i64, 1, "tok0.type");
        assert_eq!(toks[0].start as i64, 0, "tok0.start");
        assert_eq!(toks[0].end as i64, 2, "tok0.end");
        assert_eq!(toks[0].size as i64, 0, "tok0.size"); }
            Err(_) => { assert!(1 < 0, "expected error return 1"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_2() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[91, 93];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, 1, "return"); assert_eq!(toks[0].r#type as i64, 2, "tok0.type");
        assert_eq!(toks[0].start as i64, 0, "tok0.start");
        assert_eq!(toks[0].end as i64, 2, "tok0.end");
        assert_eq!(toks[0].size as i64, 0, "tok0.size"); }
            Err(_) => { assert!(1 < 0, "expected error return 1"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_3() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[110, 117, 108, 108];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, 1, "return"); assert_eq!(toks[0].r#type as i64, 8, "tok0.type");
        assert_eq!(toks[0].start as i64, 0, "tok0.start");
        assert_eq!(toks[0].end as i64, 4, "tok0.end");
        assert_eq!(toks[0].size as i64, 0, "tok0.size"); }
            Err(_) => { assert!(1 < 0, "expected error return 1"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_4() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[116, 114, 117, 101];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, 1, "return"); assert_eq!(toks[0].r#type as i64, 8, "tok0.type");
        assert_eq!(toks[0].start as i64, 0, "tok0.start");
        assert_eq!(toks[0].end as i64, 4, "tok0.end");
        assert_eq!(toks[0].size as i64, 0, "tok0.size"); }
            Err(_) => { assert!(1 < 0, "expected error return 1"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_5() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[102, 97, 108, 115, 101];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, 1, "return"); assert_eq!(toks[0].r#type as i64, 8, "tok0.type");
        assert_eq!(toks[0].start as i64, 0, "tok0.start");
        assert_eq!(toks[0].end as i64, 5, "tok0.end");
        assert_eq!(toks[0].size as i64, 0, "tok0.size"); }
            Err(_) => { assert!(1 < 0, "expected error return 1"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_6() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[48];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, 1, "return"); assert_eq!(toks[0].r#type as i64, 8, "tok0.type");
        assert_eq!(toks[0].start as i64, 0, "tok0.start");
        assert_eq!(toks[0].end as i64, 1, "tok0.end");
        assert_eq!(toks[0].size as i64, 0, "tok0.size"); }
            Err(_) => { assert!(1 < 0, "expected error return 1"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_7() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[49, 50, 51];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, 1, "return"); assert_eq!(toks[0].r#type as i64, 8, "tok0.type");
        assert_eq!(toks[0].start as i64, 0, "tok0.start");
        assert_eq!(toks[0].end as i64, 3, "tok0.end");
        assert_eq!(toks[0].size as i64, 0, "tok0.size"); }
            Err(_) => { assert!(1 < 0, "expected error return 1"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_8() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[45, 52, 50];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, 1, "return"); assert_eq!(toks[0].r#type as i64, 8, "tok0.type");
        assert_eq!(toks[0].start as i64, 0, "tok0.start");
        assert_eq!(toks[0].end as i64, 3, "tok0.end");
        assert_eq!(toks[0].size as i64, 0, "tok0.size"); }
            Err(_) => { assert!(1 < 0, "expected error return 1"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_9() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[51, 46, 49, 52];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, 1, "return"); assert_eq!(toks[0].r#type as i64, 8, "tok0.type");
        assert_eq!(toks[0].start as i64, 0, "tok0.start");
        assert_eq!(toks[0].end as i64, 4, "tok0.end");
        assert_eq!(toks[0].size as i64, 0, "tok0.size"); }
            Err(_) => { assert!(1 < 0, "expected error return 1"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_10() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[34, 104, 105, 34];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, 1, "return"); assert_eq!(toks[0].r#type as i64, 4, "tok0.type");
        assert_eq!(toks[0].start as i64, 1, "tok0.start");
        assert_eq!(toks[0].end as i64, 3, "tok0.end");
        assert_eq!(toks[0].size as i64, 0, "tok0.size"); }
            Err(_) => { assert!(1 < 0, "expected error return 1"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_11() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[123, 34, 97, 34, 58, 49, 125];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, 3, "return"); assert_eq!(toks[0].r#type as i64, 1, "tok0.type");
        assert_eq!(toks[0].start as i64, 0, "tok0.start");
        assert_eq!(toks[0].end as i64, 7, "tok0.end");
        assert_eq!(toks[0].size as i64, 1, "tok0.size");
        assert_eq!(toks[1].r#type as i64, 4, "tok1.type");
        assert_eq!(toks[1].start as i64, 2, "tok1.start");
        assert_eq!(toks[1].end as i64, 3, "tok1.end");
        assert_eq!(toks[1].size as i64, 1, "tok1.size");
        assert_eq!(toks[2].r#type as i64, 8, "tok2.type");
        assert_eq!(toks[2].start as i64, 5, "tok2.start");
        assert_eq!(toks[2].end as i64, 6, "tok2.end");
        assert_eq!(toks[2].size as i64, 0, "tok2.size"); }
            Err(_) => { assert!(3 < 0, "expected error return 3"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_12() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[91, 49, 44, 50, 44, 51, 93];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, 4, "return"); assert_eq!(toks[0].r#type as i64, 2, "tok0.type");
        assert_eq!(toks[0].start as i64, 0, "tok0.start");
        assert_eq!(toks[0].end as i64, 7, "tok0.end");
        assert_eq!(toks[0].size as i64, 3, "tok0.size");
        assert_eq!(toks[1].r#type as i64, 8, "tok1.type");
        assert_eq!(toks[1].start as i64, 1, "tok1.start");
        assert_eq!(toks[1].end as i64, 2, "tok1.end");
        assert_eq!(toks[1].size as i64, 0, "tok1.size");
        assert_eq!(toks[2].r#type as i64, 8, "tok2.type");
        assert_eq!(toks[2].start as i64, 3, "tok2.start");
        assert_eq!(toks[2].end as i64, 4, "tok2.end");
        assert_eq!(toks[2].size as i64, 0, "tok2.size");
        assert_eq!(toks[3].r#type as i64, 8, "tok3.type");
        assert_eq!(toks[3].start as i64, 5, "tok3.start");
        assert_eq!(toks[3].end as i64, 6, "tok3.end");
        assert_eq!(toks[3].size as i64, 0, "tok3.size"); }
            Err(_) => { assert!(4 < 0, "expected error return 4"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_13() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[123, 34, 107, 34, 58, 34, 118, 34, 44, 34, 110, 34, 58, 52, 50, 44, 34, 98, 34, 58, 116, 114, 117, 101, 44, 34, 122, 34, 58, 110, 117, 108, 108, 125];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, 9, "return"); assert_eq!(toks[0].r#type as i64, 1, "tok0.type");
        assert_eq!(toks[0].start as i64, 0, "tok0.start");
        assert_eq!(toks[0].end as i64, 34, "tok0.end");
        assert_eq!(toks[0].size as i64, 4, "tok0.size");
        assert_eq!(toks[1].r#type as i64, 4, "tok1.type");
        assert_eq!(toks[1].start as i64, 2, "tok1.start");
        assert_eq!(toks[1].end as i64, 3, "tok1.end");
        assert_eq!(toks[1].size as i64, 1, "tok1.size");
        assert_eq!(toks[2].r#type as i64, 4, "tok2.type");
        assert_eq!(toks[2].start as i64, 6, "tok2.start");
        assert_eq!(toks[2].end as i64, 7, "tok2.end");
        assert_eq!(toks[2].size as i64, 0, "tok2.size");
        assert_eq!(toks[3].r#type as i64, 4, "tok3.type");
        assert_eq!(toks[3].start as i64, 10, "tok3.start");
        assert_eq!(toks[3].end as i64, 11, "tok3.end");
        assert_eq!(toks[3].size as i64, 1, "tok3.size");
        assert_eq!(toks[4].r#type as i64, 8, "tok4.type");
        assert_eq!(toks[4].start as i64, 13, "tok4.start");
        assert_eq!(toks[4].end as i64, 15, "tok4.end");
        assert_eq!(toks[4].size as i64, 0, "tok4.size");
        assert_eq!(toks[5].r#type as i64, 4, "tok5.type");
        assert_eq!(toks[5].start as i64, 17, "tok5.start");
        assert_eq!(toks[5].end as i64, 18, "tok5.end");
        assert_eq!(toks[5].size as i64, 1, "tok5.size");
        assert_eq!(toks[6].r#type as i64, 8, "tok6.type");
        assert_eq!(toks[6].start as i64, 20, "tok6.start");
        assert_eq!(toks[6].end as i64, 24, "tok6.end");
        assert_eq!(toks[6].size as i64, 0, "tok6.size");
        assert_eq!(toks[7].r#type as i64, 4, "tok7.type");
        assert_eq!(toks[7].start as i64, 26, "tok7.start");
        assert_eq!(toks[7].end as i64, 27, "tok7.end");
        assert_eq!(toks[7].size as i64, 1, "tok7.size");
        assert_eq!(toks[8].r#type as i64, 8, "tok8.type");
        assert_eq!(toks[8].start as i64, 29, "tok8.start");
        assert_eq!(toks[8].end as i64, 33, "tok8.end");
        assert_eq!(toks[8].size as i64, 0, "tok8.size"); }
            Err(_) => { assert!(9 < 0, "expected error return 9"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_14() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[123, 34, 97, 34, 58, 91, 49, 44, 123, 34, 98, 34, 58, 50, 125, 93, 125];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, 7, "return"); assert_eq!(toks[0].r#type as i64, 1, "tok0.type");
        assert_eq!(toks[0].start as i64, 0, "tok0.start");
        assert_eq!(toks[0].end as i64, 17, "tok0.end");
        assert_eq!(toks[0].size as i64, 1, "tok0.size");
        assert_eq!(toks[1].r#type as i64, 4, "tok1.type");
        assert_eq!(toks[1].start as i64, 2, "tok1.start");
        assert_eq!(toks[1].end as i64, 3, "tok1.end");
        assert_eq!(toks[1].size as i64, 1, "tok1.size");
        assert_eq!(toks[2].r#type as i64, 2, "tok2.type");
        assert_eq!(toks[2].start as i64, 5, "tok2.start");
        assert_eq!(toks[2].end as i64, 16, "tok2.end");
        assert_eq!(toks[2].size as i64, 2, "tok2.size");
        assert_eq!(toks[3].r#type as i64, 8, "tok3.type");
        assert_eq!(toks[3].start as i64, 6, "tok3.start");
        assert_eq!(toks[3].end as i64, 7, "tok3.end");
        assert_eq!(toks[3].size as i64, 0, "tok3.size");
        assert_eq!(toks[4].r#type as i64, 1, "tok4.type");
        assert_eq!(toks[4].start as i64, 8, "tok4.start");
        assert_eq!(toks[4].end as i64, 15, "tok4.end");
        assert_eq!(toks[4].size as i64, 1, "tok4.size");
        assert_eq!(toks[5].r#type as i64, 4, "tok5.type");
        assert_eq!(toks[5].start as i64, 10, "tok5.start");
        assert_eq!(toks[5].end as i64, 11, "tok5.end");
        assert_eq!(toks[5].size as i64, 1, "tok5.size");
        assert_eq!(toks[6].r#type as i64, 8, "tok6.type");
        assert_eq!(toks[6].start as i64, 13, "tok6.start");
        assert_eq!(toks[6].end as i64, 14, "tok6.end");
        assert_eq!(toks[6].size as i64, 0, "tok6.size"); }
            Err(_) => { assert!(7 < 0, "expected error return 7"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_15() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[32, 32, 123, 32, 32, 34, 120, 34, 32, 58, 32, 91, 32, 116, 114, 117, 101, 32, 44, 32, 102, 97, 108, 115, 101, 32, 93, 32, 125, 32, 32];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, 5, "return"); assert_eq!(toks[0].r#type as i64, 1, "tok0.type");
        assert_eq!(toks[0].start as i64, 2, "tok0.start");
        assert_eq!(toks[0].end as i64, 29, "tok0.end");
        assert_eq!(toks[0].size as i64, 1, "tok0.size");
        assert_eq!(toks[1].r#type as i64, 4, "tok1.type");
        assert_eq!(toks[1].start as i64, 6, "tok1.start");
        assert_eq!(toks[1].end as i64, 7, "tok1.end");
        assert_eq!(toks[1].size as i64, 1, "tok1.size");
        assert_eq!(toks[2].r#type as i64, 2, "tok2.type");
        assert_eq!(toks[2].start as i64, 11, "tok2.start");
        assert_eq!(toks[2].end as i64, 27, "tok2.end");
        assert_eq!(toks[2].size as i64, 2, "tok2.size");
        assert_eq!(toks[3].r#type as i64, 8, "tok3.type");
        assert_eq!(toks[3].start as i64, 13, "tok3.start");
        assert_eq!(toks[3].end as i64, 17, "tok3.end");
        assert_eq!(toks[3].size as i64, 0, "tok3.size");
        assert_eq!(toks[4].r#type as i64, 8, "tok4.type");
        assert_eq!(toks[4].start as i64, 20, "tok4.start");
        assert_eq!(toks[4].end as i64, 25, "tok4.end");
        assert_eq!(toks[4].size as i64, 0, "tok4.size"); }
            Err(_) => { assert!(5 < 0, "expected error return 5"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_16() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[123, 34, 110, 101, 115, 116, 101, 100, 34, 58, 123, 34, 100, 101, 101, 112, 34, 58, 123, 34, 120, 34, 58, 91, 49, 44, 50, 44, 91, 51, 93, 93, 125, 125, 125];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, 11, "return"); assert_eq!(toks[0].r#type as i64, 1, "tok0.type");
        assert_eq!(toks[0].start as i64, 0, "tok0.start");
        assert_eq!(toks[0].end as i64, 35, "tok0.end");
        assert_eq!(toks[0].size as i64, 1, "tok0.size");
        assert_eq!(toks[1].r#type as i64, 4, "tok1.type");
        assert_eq!(toks[1].start as i64, 2, "tok1.start");
        assert_eq!(toks[1].end as i64, 8, "tok1.end");
        assert_eq!(toks[1].size as i64, 1, "tok1.size");
        assert_eq!(toks[2].r#type as i64, 1, "tok2.type");
        assert_eq!(toks[2].start as i64, 10, "tok2.start");
        assert_eq!(toks[2].end as i64, 34, "tok2.end");
        assert_eq!(toks[2].size as i64, 1, "tok2.size");
        assert_eq!(toks[3].r#type as i64, 4, "tok3.type");
        assert_eq!(toks[3].start as i64, 12, "tok3.start");
        assert_eq!(toks[3].end as i64, 16, "tok3.end");
        assert_eq!(toks[3].size as i64, 1, "tok3.size");
        assert_eq!(toks[4].r#type as i64, 1, "tok4.type");
        assert_eq!(toks[4].start as i64, 18, "tok4.start");
        assert_eq!(toks[4].end as i64, 33, "tok4.end");
        assert_eq!(toks[4].size as i64, 1, "tok4.size");
        assert_eq!(toks[5].r#type as i64, 4, "tok5.type");
        assert_eq!(toks[5].start as i64, 20, "tok5.start");
        assert_eq!(toks[5].end as i64, 21, "tok5.end");
        assert_eq!(toks[5].size as i64, 1, "tok5.size");
        assert_eq!(toks[6].r#type as i64, 2, "tok6.type");
        assert_eq!(toks[6].start as i64, 23, "tok6.start");
        assert_eq!(toks[6].end as i64, 32, "tok6.end");
        assert_eq!(toks[6].size as i64, 3, "tok6.size");
        assert_eq!(toks[7].r#type as i64, 8, "tok7.type");
        assert_eq!(toks[7].start as i64, 24, "tok7.start");
        assert_eq!(toks[7].end as i64, 25, "tok7.end");
        assert_eq!(toks[7].size as i64, 0, "tok7.size");
        assert_eq!(toks[8].r#type as i64, 8, "tok8.type");
        assert_eq!(toks[8].start as i64, 26, "tok8.start");
        assert_eq!(toks[8].end as i64, 27, "tok8.end");
        assert_eq!(toks[8].size as i64, 0, "tok8.size");
        assert_eq!(toks[9].r#type as i64, 2, "tok9.type");
        assert_eq!(toks[9].start as i64, 28, "tok9.start");
        assert_eq!(toks[9].end as i64, 31, "tok9.end");
        assert_eq!(toks[9].size as i64, 1, "tok9.size");
        assert_eq!(toks[10].r#type as i64, 8, "tok10.type");
        assert_eq!(toks[10].start as i64, 29, "tok10.start");
        assert_eq!(toks[10].end as i64, 30, "tok10.end");
        assert_eq!(toks[10].size as i64, 0, "tok10.size"); }
            Err(_) => { assert!(11 < 0, "expected error return 11"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_17() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[91, 34, 97, 34, 44, 34, 98, 34, 44, 34, 99, 34, 93];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, 4, "return"); assert_eq!(toks[0].r#type as i64, 2, "tok0.type");
        assert_eq!(toks[0].start as i64, 0, "tok0.start");
        assert_eq!(toks[0].end as i64, 13, "tok0.end");
        assert_eq!(toks[0].size as i64, 3, "tok0.size");
        assert_eq!(toks[1].r#type as i64, 4, "tok1.type");
        assert_eq!(toks[1].start as i64, 2, "tok1.start");
        assert_eq!(toks[1].end as i64, 3, "tok1.end");
        assert_eq!(toks[1].size as i64, 0, "tok1.size");
        assert_eq!(toks[2].r#type as i64, 4, "tok2.type");
        assert_eq!(toks[2].start as i64, 6, "tok2.start");
        assert_eq!(toks[2].end as i64, 7, "tok2.end");
        assert_eq!(toks[2].size as i64, 0, "tok2.size");
        assert_eq!(toks[3].r#type as i64, 4, "tok3.type");
        assert_eq!(toks[3].start as i64, 10, "tok3.start");
        assert_eq!(toks[3].end as i64, 11, "tok3.end");
        assert_eq!(toks[3].size as i64, 0, "tok3.size"); }
            Err(_) => { assert!(4 < 0, "expected error return 4"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_18() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[123, 34, 34, 58, 48, 125];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, 3, "return"); assert_eq!(toks[0].r#type as i64, 1, "tok0.type");
        assert_eq!(toks[0].start as i64, 0, "tok0.start");
        assert_eq!(toks[0].end as i64, 6, "tok0.end");
        assert_eq!(toks[0].size as i64, 1, "tok0.size");
        assert_eq!(toks[1].r#type as i64, 4, "tok1.type");
        assert_eq!(toks[1].start as i64, 2, "tok1.start");
        assert_eq!(toks[1].end as i64, 2, "tok1.end");
        assert_eq!(toks[1].size as i64, 1, "tok1.size");
        assert_eq!(toks[2].r#type as i64, 8, "tok2.type");
        assert_eq!(toks[2].start as i64, 4, "tok2.start");
        assert_eq!(toks[2].end as i64, 5, "tok2.end");
        assert_eq!(toks[2].size as i64, 0, "tok2.size"); }
            Err(_) => { assert!(3 < 0, "expected error return 3"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_19() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[123];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, -3, "return");  }
            Err(_) => { assert!(-3 < 0, "expected error return -3"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_20() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[91];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, -3, "return");  }
            Err(_) => { assert!(-3 < 0, "expected error return -3"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_21() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[91, 49, 44];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, -3, "return");  }
            Err(_) => { assert!(-3 < 0, "expected error return -3"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_22() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[123, 34, 97, 34, 58, 125];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, 2, "return"); assert_eq!(toks[0].r#type as i64, 1, "tok0.type");
        assert_eq!(toks[0].start as i64, 0, "tok0.start");
        assert_eq!(toks[0].end as i64, 6, "tok0.end");
        assert_eq!(toks[0].size as i64, 1, "tok0.size");
        assert_eq!(toks[1].r#type as i64, 4, "tok1.type");
        assert_eq!(toks[1].start as i64, 2, "tok1.start");
        assert_eq!(toks[1].end as i64, 3, "tok1.end");
        assert_eq!(toks[1].size as i64, 0, "tok1.size"); }
            Err(_) => { assert!(2 < 0, "expected error return 2"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_23() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[123, 34, 97, 34];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, -3, "return");  }
            Err(_) => { assert!(-3 < 0, "expected error return -3"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_24() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[116, 114, 117];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, 1, "return"); assert_eq!(toks[0].r#type as i64, 8, "tok0.type");
        assert_eq!(toks[0].start as i64, 0, "tok0.start");
        assert_eq!(toks[0].end as i64, 3, "tok0.end");
        assert_eq!(toks[0].size as i64, 0, "tok0.size"); }
            Err(_) => { assert!(1 < 0, "expected error return 1"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_25() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[49, 50, 51, 97, 98, 99];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, 1, "return"); assert_eq!(toks[0].r#type as i64, 8, "tok0.type");
        assert_eq!(toks[0].start as i64, 0, "tok0.start");
        assert_eq!(toks[0].end as i64, 6, "tok0.end");
        assert_eq!(toks[0].size as i64, 0, "tok0.size"); }
            Err(_) => { assert!(1 < 0, "expected error return 1"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_26() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[34, 117, 110, 116, 101, 114, 109];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, -3, "return");  }
            Err(_) => { assert!(-3 < 0, "expected error return -3"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_27() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[125];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, -2, "return");  }
            Err(_) => { assert!(-2 < 0, "expected error return -2"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_28() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[93];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, -2, "return");  }
            Err(_) => { assert!(-2 < 0, "expected error return -2"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_29() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[44];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, 0, "return");  }
            Err(_) => { assert!(0 < 0, "expected error return 0"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_30() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[58];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, 0, "return");  }
            Err(_) => { assert!(0 < 0, "expected error return 0"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_31() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[123, 34, 97, 34, 58, 49, 44, 125];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, 3, "return"); assert_eq!(toks[0].r#type as i64, 1, "tok0.type");
        assert_eq!(toks[0].start as i64, 0, "tok0.start");
        assert_eq!(toks[0].end as i64, 8, "tok0.end");
        assert_eq!(toks[0].size as i64, 1, "tok0.size");
        assert_eq!(toks[1].r#type as i64, 4, "tok1.type");
        assert_eq!(toks[1].start as i64, 2, "tok1.start");
        assert_eq!(toks[1].end as i64, 3, "tok1.end");
        assert_eq!(toks[1].size as i64, 1, "tok1.size");
        assert_eq!(toks[2].r#type as i64, 8, "tok2.type");
        assert_eq!(toks[2].start as i64, 5, "tok2.start");
        assert_eq!(toks[2].end as i64, 6, "tok2.end");
        assert_eq!(toks[2].size as i64, 0, "tok2.size"); }
            Err(_) => { assert!(3 < 0, "expected error return 3"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_32() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[91, 44, 93];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, 1, "return"); assert_eq!(toks[0].r#type as i64, 2, "tok0.type");
        assert_eq!(toks[0].start as i64, 0, "tok0.start");
        assert_eq!(toks[0].end as i64, 3, "tok0.end");
        assert_eq!(toks[0].size as i64, 0, "tok0.size"); }
            Err(_) => { assert!(1 < 0, "expected error return 1"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_33() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[123, 123, 123, 123];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, -3, "return");  }
            Err(_) => { assert!(-3 < 0, "expected error return -3"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_34() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[91, 91, 91, 91, 91, 91, 91, 91, 91, 91];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, -3, "return");  }
            Err(_) => { assert!(-3 < 0, "expected error return -3"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_35() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[0, 1, 2];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, 0, "return");  }
            Err(_) => { assert!(0 < 0, "expected error return 0"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_36() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[123, 34, 97, 34, 58, 34, 98, 34];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, -3, "return");  }
            Err(_) => { assert!(-3 < 0, "expected error return -3"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_37() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[32, 32, 9, 10, 32, 32];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, 0, "return");  }
            Err(_) => { assert!(0 < 0, "expected error return 0"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_38() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[123, 34, 120, 34, 58, 45, 125];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, 3, "return"); assert_eq!(toks[0].r#type as i64, 1, "tok0.type");
        assert_eq!(toks[0].start as i64, 0, "tok0.start");
        assert_eq!(toks[0].end as i64, 7, "tok0.end");
        assert_eq!(toks[0].size as i64, 1, "tok0.size");
        assert_eq!(toks[1].r#type as i64, 4, "tok1.type");
        assert_eq!(toks[1].start as i64, 2, "tok1.start");
        assert_eq!(toks[1].end as i64, 3, "tok1.end");
        assert_eq!(toks[1].size as i64, 1, "tok1.size");
        assert_eq!(toks[2].r#type as i64, 8, "tok2.type");
        assert_eq!(toks[2].start as i64, 5, "tok2.start");
        assert_eq!(toks[2].end as i64, 6, "tok2.end");
        assert_eq!(toks[2].size as i64, 0, "tok2.size"); }
            Err(_) => { assert!(3 < 0, "expected error return 3"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_39() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[91, 49, 32, 50, 32, 51, 93];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, 4, "return"); assert_eq!(toks[0].r#type as i64, 2, "tok0.type");
        assert_eq!(toks[0].start as i64, 0, "tok0.start");
        assert_eq!(toks[0].end as i64, 7, "tok0.end");
        assert_eq!(toks[0].size as i64, 3, "tok0.size");
        assert_eq!(toks[1].r#type as i64, 8, "tok1.type");
        assert_eq!(toks[1].start as i64, 1, "tok1.start");
        assert_eq!(toks[1].end as i64, 2, "tok1.end");
        assert_eq!(toks[1].size as i64, 0, "tok1.size");
        assert_eq!(toks[2].r#type as i64, 8, "tok2.type");
        assert_eq!(toks[2].start as i64, 3, "tok2.start");
        assert_eq!(toks[2].end as i64, 4, "tok2.end");
        assert_eq!(toks[2].size as i64, 0, "tok2.size");
        assert_eq!(toks[3].r#type as i64, 8, "tok3.type");
        assert_eq!(toks[3].start as i64, 5, "tok3.start");
        assert_eq!(toks[3].end as i64, 6, "tok3.end");
        assert_eq!(toks[3].size as i64, 0, "tok3.size"); }
            Err(_) => { assert!(4 < 0, "expected error return 4"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_40() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[68, 55, 118, 70, 75, 99, 62, 44, 76, 110, 121, 84, 98, 86, 67, 100, 45, 87, 60, 126, 115, 109, 83, 42, 42, 65, 124, 72, 118, 116, 61, 70, 93, 43];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, -2, "return");  }
            Err(_) => { assert!(-2 < 0, "expected error return -2"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_41() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[74, 69, 59, 51, 73, 98, 84, 119, 122, 108, 51, 66, 98, 126, 102, 67, 34, 95, 121, 63, 104, 46, 45];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, 1, "return"); assert_eq!(toks[0].r#type as i64, 8, "tok0.type");
        assert_eq!(toks[0].start as i64, 0, "tok0.start");
        assert_eq!(toks[0].end as i64, 23, "tok0.end");
        assert_eq!(toks[0].size as i64, 0, "tok0.size"); }
            Err(_) => { assert!(1 < 0, "expected error return 1"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_42() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[84, 116, 74, 35, 38, 115, 41, 50, 64, 84, 89, 69, 46, 107, 107, 52, 72, 81, 40, 82, 124, 100, 121, 43, 110, 34, 92, 71, 100];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, 1, "return"); assert_eq!(toks[0].r#type as i64, 8, "tok0.type");
        assert_eq!(toks[0].start as i64, 0, "tok0.start");
        assert_eq!(toks[0].end as i64, 29, "tok0.end");
        assert_eq!(toks[0].size as i64, 0, "tok0.size"); }
            Err(_) => { assert!(1 < 0, "expected error return 1"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_43() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[86, 65, 53, 96, 47, 79, 80, 44, 50, 70, 83, 86, 121, 56, 78, 126, 114, 90, 54, 44, 38, 102, 68, 38, 32, 43, 35];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, 4, "return"); assert_eq!(toks[0].r#type as i64, 8, "tok0.type");
        assert_eq!(toks[0].start as i64, 0, "tok0.start");
        assert_eq!(toks[0].end as i64, 7, "tok0.end");
        assert_eq!(toks[0].size as i64, 0, "tok0.size");
        assert_eq!(toks[1].r#type as i64, 8, "tok1.type");
        assert_eq!(toks[1].start as i64, 8, "tok1.start");
        assert_eq!(toks[1].end as i64, 19, "tok1.end");
        assert_eq!(toks[1].size as i64, 0, "tok1.size");
        assert_eq!(toks[2].r#type as i64, 8, "tok2.type");
        assert_eq!(toks[2].start as i64, 20, "tok2.start");
        assert_eq!(toks[2].end as i64, 24, "tok2.end");
        assert_eq!(toks[2].size as i64, 0, "tok2.size");
        assert_eq!(toks[3].r#type as i64, 8, "tok3.type");
        assert_eq!(toks[3].start as i64, 25, "tok3.start");
        assert_eq!(toks[3].end as i64, 27, "tok3.end");
        assert_eq!(toks[3].size as i64, 0, "tok3.size"); }
            Err(_) => { assert!(4 < 0, "expected error return 4"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_44() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[58, 42, 51];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, 1, "return"); assert_eq!(toks[0].r#type as i64, 8, "tok0.type");
        assert_eq!(toks[0].start as i64, 1, "tok0.start");
        assert_eq!(toks[0].end as i64, 3, "tok0.end");
        assert_eq!(toks[0].size as i64, 0, "tok0.size"); }
            Err(_) => { assert!(1 < 0, "expected error return 1"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_45() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[93, 34, 103, 102, 104, 38, 37, 103, 101, 107, 52, 95, 46, 48, 101, 78, 109, 39, 71, 98, 43, 105, 65, 94, 92, 115, 37, 43, 124, 82, 69];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, -2, "return");  }
            Err(_) => { assert!(-2 < 0, "expected error return -2"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_46() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[72, 68, 98, 125, 79, 61, 84, 65, 42, 83, 111, 77, 73, 102, 54, 57, 92, 111, 125, 44, 89, 122, 82, 52, 81, 109, 58, 60, 90, 98, 95, 32, 36, 67, 93, 126, 78];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, -2, "return");  }
            Err(_) => { assert!(-2 < 0, "expected error return -2"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_47() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[57, 123, 61, 57, 53, 109, 80, 88, 40, 105, 67, 116, 88, 78, 104, 89, 113, 102, 116, 107, 74, 91, 42, 92, 122];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, 1, "return"); assert_eq!(toks[0].r#type as i64, 8, "tok0.type");
        assert_eq!(toks[0].start as i64, 0, "tok0.start");
        assert_eq!(toks[0].end as i64, 25, "tok0.end");
        assert_eq!(toks[0].size as i64, 0, "tok0.size"); }
            Err(_) => { assert!(1 < 0, "expected error return 1"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_48() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[95, 74, 61, 45, 56, 62, 103, 114, 48, 125, 105, 105, 50, 100, 93, 64, 81, 46, 76, 59, 43, 103, 74, 39, 70];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, -2, "return");  }
            Err(_) => { assert!(-2 < 0, "expected error return -2"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_49() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[111];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, 1, "return"); assert_eq!(toks[0].r#type as i64, 8, "tok0.type");
        assert_eq!(toks[0].start as i64, 0, "tok0.start");
        assert_eq!(toks[0].end as i64, 1, "tok0.end");
        assert_eq!(toks[0].size as i64, 0, "tok0.size"); }
            Err(_) => { assert!(1 < 0, "expected error return 1"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_50() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[89, 93, 74, 52, 118, 87, 51];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, -2, "return");  }
            Err(_) => { assert!(-2 < 0, "expected error return -2"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_51() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[63, 93, 96, 108, 71, 103, 115, 66, 107, 84, 96, 85, 117, 38];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, -2, "return");  }
            Err(_) => { assert!(-2 < 0, "expected error return -2"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_52() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[45, 112, 109, 54];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, 1, "return"); assert_eq!(toks[0].r#type as i64, 8, "tok0.type");
        assert_eq!(toks[0].start as i64, 0, "tok0.start");
        assert_eq!(toks[0].end as i64, 4, "tok0.end");
        assert_eq!(toks[0].size as i64, 0, "tok0.size"); }
            Err(_) => { assert!(1 < 0, "expected error return 1"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_53() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[111, 66, 120, 45, 63, 53, 59, 105];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, 1, "return"); assert_eq!(toks[0].r#type as i64, 8, "tok0.type");
        assert_eq!(toks[0].start as i64, 0, "tok0.start");
        assert_eq!(toks[0].end as i64, 8, "tok0.end");
        assert_eq!(toks[0].size as i64, 0, "tok0.size"); }
            Err(_) => { assert!(1 < 0, "expected error return 1"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_54() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[51, 58, 67, 79, 123];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, 2, "return"); assert_eq!(toks[0].r#type as i64, 8, "tok0.type");
        assert_eq!(toks[0].start as i64, 0, "tok0.start");
        assert_eq!(toks[0].end as i64, 1, "tok0.end");
        assert_eq!(toks[0].size as i64, 1, "tok0.size");
        assert_eq!(toks[1].r#type as i64, 8, "tok1.type");
        assert_eq!(toks[1].start as i64, 2, "tok1.start");
        assert_eq!(toks[1].end as i64, 5, "tok1.end");
        assert_eq!(toks[1].size as i64, 0, "tok1.size"); }
            Err(_) => { assert!(2 < 0, "expected error return 2"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_55() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[124, 89, 78, 73, 124, 123, 85, 116, 59, 50, 90, 71, 64, 51, 92, 111, 119, 84, 116, 88, 81, 78, 86, 46, 47, 54, 120, 106, 53, 108];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, 1, "return"); assert_eq!(toks[0].r#type as i64, 8, "tok0.type");
        assert_eq!(toks[0].start as i64, 0, "tok0.start");
        assert_eq!(toks[0].end as i64, 30, "tok0.end");
        assert_eq!(toks[0].size as i64, 0, "tok0.size"); }
            Err(_) => { assert!(1 < 0, "expected error return 1"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_56() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[32, 94, 69, 61, 126, 118, 86, 70, 125, 34, 113, 85, 68, 73, 38, 42, 124, 40, 65];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, -2, "return");  }
            Err(_) => { assert!(-2 < 0, "expected error return -2"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_57() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[71, 68, 120, 46, 58, 50, 39, 84, 113, 93, 91, 59, 53, 36, 91, 119, 113, 32, 93, 47, 60, 87, 106];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, -2, "return");  }
            Err(_) => { assert!(-2 < 0, "expected error return -2"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_58() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[74, 72, 104, 58, 32, 45, 97, 64, 34, 55, 63, 120, 79, 77, 84, 101, 115, 57, 40, 77, 63, 39, 122, 84, 65, 58, 58, 45, 120];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, 3, "return"); assert_eq!(toks[0].r#type as i64, 8, "tok0.type");
        assert_eq!(toks[0].start as i64, 0, "tok0.start");
        assert_eq!(toks[0].end as i64, 3, "tok0.end");
        assert_eq!(toks[0].size as i64, 1, "tok0.size");
        assert_eq!(toks[1].r#type as i64, 8, "tok1.type");
        assert_eq!(toks[1].start as i64, 5, "tok1.start");
        assert_eq!(toks[1].end as i64, 25, "tok1.end");
        assert_eq!(toks[1].size as i64, 1, "tok1.size");
        assert_eq!(toks[2].r#type as i64, 8, "tok2.type");
        assert_eq!(toks[2].start as i64, 27, "tok2.start");
        assert_eq!(toks[2].end as i64, 29, "tok2.end");
        assert_eq!(toks[2].size as i64, 0, "tok2.size"); }
            Err(_) => { assert!(3 < 0, "expected error return 3"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_59() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[119, 35, 61, 58, 67, 50, 101, 106, 53, 86, 70, 111, 87, 91, 72, 67, 92, 48, 43, 37, 45, 33, 50, 81, 106, 50, 55, 71];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, 2, "return"); assert_eq!(toks[0].r#type as i64, 8, "tok0.type");
        assert_eq!(toks[0].start as i64, 0, "tok0.start");
        assert_eq!(toks[0].end as i64, 3, "tok0.end");
        assert_eq!(toks[0].size as i64, 1, "tok0.size");
        assert_eq!(toks[1].r#type as i64, 8, "tok1.type");
        assert_eq!(toks[1].start as i64, 4, "tok1.start");
        assert_eq!(toks[1].end as i64, 28, "tok1.end");
        assert_eq!(toks[1].size as i64, 0, "tok1.size"); }
            Err(_) => { assert!(2 < 0, "expected error return 2"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_60() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[105];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, 1, "return"); assert_eq!(toks[0].r#type as i64, 8, "tok0.type");
        assert_eq!(toks[0].start as i64, 0, "tok0.start");
        assert_eq!(toks[0].end as i64, 1, "tok0.end");
        assert_eq!(toks[0].size as i64, 0, "tok0.size"); }
            Err(_) => { assert!(1 < 0, "expected error return 1"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_61() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[33, 112, 74, 113, 105, 42, 32, 37, 52, 96, 54, 92, 101, 100];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, 2, "return"); assert_eq!(toks[0].r#type as i64, 8, "tok0.type");
        assert_eq!(toks[0].start as i64, 0, "tok0.start");
        assert_eq!(toks[0].end as i64, 6, "tok0.end");
        assert_eq!(toks[0].size as i64, 0, "tok0.size");
        assert_eq!(toks[1].r#type as i64, 8, "tok1.type");
        assert_eq!(toks[1].start as i64, 7, "tok1.start");
        assert_eq!(toks[1].end as i64, 14, "tok1.end");
        assert_eq!(toks[1].size as i64, 0, "tok1.size"); }
            Err(_) => { assert!(2 < 0, "expected error return 2"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_62() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[37, 48, 73, 84, 125, 110, 61, 45, 44, 69, 76, 120, 82, 100, 125, 90, 104, 40, 88, 81, 120, 88, 45, 69, 68, 121, 82, 35];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, -2, "return");  }
            Err(_) => { assert!(-2 < 0, "expected error return -2"); }
        }
    }

    #[test]
    fn test_jsmn_parse_body_63() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        let ibytes: &[u8] = &[75, 52, 58, 53, 94, 32, 84, 82, 91];
        let input = core::str::from_utf8(ibytes).unwrap();
        const MAX: usize = 128;
        let mut toks: alloc::vec::Vec<super::Token> = alloc::vec![super::Token::default(); MAX];
        match super::jsmn_parse(&mut st, input, Some(&mut toks)) {
            Ok(n) => { assert_eq!(n as i64, 3, "return"); assert_eq!(toks[0].r#type as i64, 8, "tok0.type");
        assert_eq!(toks[0].start as i64, 0, "tok0.start");
        assert_eq!(toks[0].end as i64, 2, "tok0.end");
        assert_eq!(toks[0].size as i64, 2, "tok0.size");
        assert_eq!(toks[1].r#type as i64, 8, "tok1.type");
        assert_eq!(toks[1].start as i64, 3, "tok1.start");
        assert_eq!(toks[1].end as i64, 5, "tok1.end");
        assert_eq!(toks[1].size as i64, 0, "tok1.size");
        assert_eq!(toks[2].r#type as i64, 8, "tok2.type");
        assert_eq!(toks[2].start as i64, 6, "tok2.start");
        assert_eq!(toks[2].end as i64, 9, "tok2.end");
        assert_eq!(toks[2].size as i64, 0, "tok2.size"); }
            Err(_) => { assert!(3 < 0, "expected error return 3"); }
        }
    }

    #[test]
    fn test_jsmn_init_body_0() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        assert_eq!(st.pos as i64, 0, "field pos");
        assert_eq!(st.toknext as i64, 0, "field toknext");
        assert_eq!(st.toksuper as i64, -1, "field toksuper");
    }

    #[test]
    fn test_jsmn_init_body_1() {
        let mut st = super::ParserState::default();
        super::jsmn_init(&mut st);
        assert_eq!(st.pos as i64, 0, "field pos");
        assert_eq!(st.toknext as i64, 0, "field toknext");
        assert_eq!(st.toksuper as i64, -1, "field toksuper");
    }

}
