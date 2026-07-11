//! jsmn (JSON tokenizer) — autonomously translated C->Rust, differential-verified.
#![allow(dead_code, unused_variables, non_camel_case_types)]

#[derive(Clone, Copy, PartialEq, Eq, Debug, Default)]
pub enum JsmnType { #[default] Undefined = 0, Object = 1, Array = 2, String = 4, Primitive = 8 }

#[derive(Clone, Copy, Default, Debug)]
pub struct JsmnTok { pub typ: JsmnType, pub start: i32, pub end: i32, pub size: i32 }

#[derive(Clone, Default)]
pub struct JsmnParser { pub pos: usize, pub toknext: usize, pub toksuper: i32 }

pub const JSMN_ERROR_NOMEM: i32 = -1;
pub const JSMN_ERROR_INVAL: i32 = -2;
pub const JSMN_ERROR_PART: i32 = -3;

pub fn jsmn_init(parser: &mut JsmnParser) {
  parser.pos = 0;
  parser.toknext = 0;
  parser.toksuper = -1;
}

pub fn jsmn_alloc_token(parser: &mut JsmnParser, tokens: &mut [JsmnTok], num_tokens: usize) -> i32 {
  if parser.toknext >= num_tokens {
    return -1;
  }
  let tok_idx = parser.toknext;
  parser.toknext += 1;
  let tok = &mut tokens[tok_idx];
  tok.start = -1;
  tok.end = -1;
  tok.size = 0;
  tok_idx as i32
}

pub fn jsmn_fill_token(token: &mut JsmnTok, typ: JsmnType, start: i32, end: i32) {
  token.typ = typ;
  token.start = start;
  token.end = end;
  token.size = 0;
}

pub fn jsmn_parse_primitive(parser: &mut JsmnParser, js: &[u8], tokens: &mut [JsmnTok], num_tokens: usize) -> i32 {
    let start = parser.pos;
    let len = js.len();

    'found: loop {
        if parser.pos >= len || js[parser.pos] == 0 {
            // In strict mode (not implemented here as per C #ifdef), 
            // it would return JSMN_ERROR_PART. 
            // The C code provided has #ifdef JSMN_STRICT around the return JSMN_ERROR_PART.
            // Since the Rust environment doesn't define JSMN_STRICT, we follow the non-strict path.
            break 'found;
        }

        match js[parser.pos] {
            b'\t' | b'\r' | b'\n' | b' ' | b',' | b']' | b'}' => break 'found,
            _ => {},
        }

        let c = js[parser.pos];
        if c < 32 || c >= 127 {
            parser.pos = start;
            return JSMN_ERROR_INVAL;
        }
        parser.pos += 1;
    }

    // The C code has a 'found' label. If tokens is NULL, it decrements pos and returns 0.
    // In Rust, tokens is a slice, so we check if it's empty or if the logic requires a null check.
    // However, the C reference checks `if (tokens == NULL)`. In this Rust signature, 
    // tokens is &mut [JsmnTok], which cannot be null. 
    // But we must simulate the logic. If the slice is empty, it's effectively NULL.
    if tokens.is_empty() {
        if parser.pos > 0 {
            parser.pos -= 1;
        }
        return 0;
    }

    let token_idx = jsmn_alloc_token(parser, tokens, num_tokens);
    if token_idx < 0 {
        parser.pos = start;
        return JSMN_ERROR_NOMEM;
    }

    jsmn_fill_token(&mut tokens[token_idx as usize], JsmnType::Primitive, start as i32, parser.pos as i32);
    
    // JSMN_PARENT_LINKS is not defined in the provided Rust types, so we skip token->parent = parser->toksuper

    if parser.pos > 0 {
        parser.pos -= 1;
    }
    0
}

pub fn jsmn_parse_string(parser: &mut JsmnParser, js: &[u8], tokens: &mut [JsmnTok], num_tokens: usize) -> i32 {
    let start = parser.pos;

    /* Skip starting quote */
    parser.pos += 1;

    let len = js.len();
    while parser.pos < len && js[parser.pos] != 0 {
        let c = js[parser.pos];

        /* Quote: end of string */
        if c == b'"' {
            let token_idx = jsmn_alloc_token(parser, tokens, num_tokens);
            if token_idx < 0 {
                parser.pos = start;
                return JSMN_ERROR_NOMEM;
            }

            jsmn_fill_token(&mut tokens[token_idx as usize], JsmnType::String, (start + 1) as i32, parser.pos as i32);

            return 0;
        }

        /* Backslash: Quoted symbol expected */
        if c == b'\\' && parser.pos + 1 < len {
            parser.pos += 1;
            match js[parser.pos] {
                b'"' | b'/' | b'\\' | b'b' | b'f' | b'r' | b'n' | b't' => {
                    // Allowed escaped symbols
                }
                b'u' => {
                    parser.pos += 1;
                    for _ in 0..4 {
                        if parser.pos >= len || js[parser.pos] == 0 {
                            break;
                        }
                        let hex = js[parser.pos];
                        if !((hex >= b'0' && hex <= b'9') ||
                             (hex >= b'A' && hex <= b'F') ||
                             (hex >= b'a' && hex <= b'f')) {
                            parser.pos = start;
                            return JSMN_ERROR_INVAL;
                        }
                        parser.pos += 1;
                    }
                    parser.pos -= 1;
                }
                _ => {
                    parser.pos = start;
                    return JSMN_ERROR_INVAL;
                }
            }
        }
        parser.pos += 1;
    }
    parser.pos = start;
    JSMN_ERROR_PART
}

pub fn jsmn_parse(parser: &mut JsmnParser, js: &[u8], tokens: &mut [JsmnTok], num_tokens: usize) -> i32 {
    let mut count = parser.toknext as i32;

    while parser.pos < js.len() && js[parser.pos] != 0 {
        let c = js[parser.pos];

        match c {
            b'{' | b'[' => {
                count += 1;
                let token_idx = jsmn_alloc_token(parser, tokens, num_tokens);
                if token_idx < 0 {
                    return JSMN_ERROR_NOMEM;
                }
                if parser.toksuper != -1 {
                    let super_idx = parser.toksuper as usize;
                    tokens[super_idx].size += 1;
                }
                let typ = if c == b'{' { JsmnType::Object } else { JsmnType::Array };
                tokens[token_idx as usize].typ = typ;
                tokens[token_idx as usize].start = parser.pos as i32;
                tokens[token_idx as usize].end = -1;
                tokens[token_idx as usize].size = 0;
                parser.toksuper = (parser.toknext - 1) as i32;
            }
            b'}' | b']' => {
                let expected_type = if c == b'}' { JsmnType::Object } else { JsmnType::Array };
                let mut i = (parser.toknext as i32) - 1;
                let mut found = false;
                while i >= 0 {
                    if tokens[i as usize].start != -1 && tokens[i as usize].end == -1 {
                        if tokens[i as usize].typ != expected_type {
                            return JSMN_ERROR_INVAL;
                        }
                        parser.toksuper = -1;
                        tokens[i as usize].end = (parser.pos + 1) as i32;
                        found = true;
                        break;
                    }
                    i -= 1;
                }
                if !found {
                    return JSMN_ERROR_INVAL;
                }
                let mut i = (parser.toknext as i32) - 1;
                while i >= 0 {
                    if tokens[i as usize].start != -1 && tokens[i as usize].end == -1 {
                        parser.toksuper = i;
                        break;
                    }
                    i -= 1;
                }
            }
            b'"' => {
                let r = jsmn_parse_string(parser, js, tokens, num_tokens);
                if r < 0 {
                    return r;
                }
                count += 1;
                if parser.toksuper != -1 {
                    tokens[parser.toksuper as usize].size += 1;
                }
            }
            b'\t' | b'\r' | b'\n' | b' ' => {}
            b':' => {
                parser.toksuper = (parser.toknext - 1) as i32;
            }
            b',' => {
                if parser.toksuper != -1 {
                    let super_tok = &tokens[parser.toksuper as usize];
                    if super_tok.typ != JsmnType::Array && super_tok.typ != JsmnType::Object {
                        let mut i = (parser.toknext as i32) - 1;
                        while i >= 0 {
                            let tok = &tokens[i as usize];
                            if (tok.typ == JsmnType::Array || tok.typ == JsmnType::Object) && tok.start != -1 && tok.end == -1 {
                                parser.toksuper = i;
                                break;
                            }
                            i -= 1;
                        }
                    }
                }
            }
            _ => {
                let r = jsmn_parse_primitive(parser, js, tokens, num_tokens);
                if r < 0 {
                    return r;
                }
                count += 1;
                if parser.toksuper != -1 {
                    tokens[parser.toksuper as usize].size += 1;
                }
            }
        }
        parser.pos += 1;
    }

    for i in (0..parser.toknext).rev() {
        if tokens[i].start != -1 && tokens[i].end == -1 {
            return JSMN_ERROR_PART;
        }
    }

    count
}

/// Differential harness: parse + dump (type,start,end,size) per token, matching the C jsmn_ref.
pub fn parse_dump(js: &[u8]) -> Vec<(i32,i32,i32,i32)> {
    let mut p = JsmnParser::default();
    jsmn_init(&mut p);
    let mut toks = vec![JsmnTok::default(); 256];
    let r = jsmn_parse(&mut p, js, &mut toks, 256);
    (0..r.max(0) as usize).map(|i| (toks[i].typ as i32, toks[i].start, toks[i].end, toks[i].size)).collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn test_parse_0() {
        let toks = parse_dump(r#"{"a":1}"#.as_bytes());
        let expected: Vec<(i32,i32,i32,i32)> = vec![(1,0,7,1), (4,2,3,1), (8,5,6,0)];
        assert_eq!(toks, expected, "case 0");
    }
    #[test]
    fn test_parse_1() {
        let toks = parse_dump(r#"[1,2,3]"#.as_bytes());
        let expected: Vec<(i32,i32,i32,i32)> = vec![(2,0,7,3), (8,1,2,0), (8,3,4,0), (8,5,6,0)];
        assert_eq!(toks, expected, "case 1");
    }
    #[test]
    fn test_parse_2() {
        let toks = parse_dump(r#""hello""#.as_bytes());
        let expected: Vec<(i32,i32,i32,i32)> = vec![(4,1,6,0)];
        assert_eq!(toks, expected, "case 2");
    }
    #[test]
    fn test_parse_3() {
        let toks = parse_dump(r#"{"k":[true,null]}"#.as_bytes());
        let expected: Vec<(i32,i32,i32,i32)> = vec![(1,0,17,1), (4,2,3,1), (2,5,16,2), (8,6,10,0), (8,11,15,0)];
        assert_eq!(toks, expected, "case 3");
    }
    #[test]
    fn test_parse_4() {
        let toks = parse_dump(r#"123"#.as_bytes());
        let expected: Vec<(i32,i32,i32,i32)> = vec![(8,0,3,0)];
        assert_eq!(toks, expected, "case 4");
    }
    #[test]
    fn test_parse_5() {
        let toks = parse_dump(r#"true"#.as_bytes());
        let expected: Vec<(i32,i32,i32,i32)> = vec![(8,0,4,0)];
        assert_eq!(toks, expected, "case 5");
    }
    #[test]
    fn test_parse_6() {
        let toks = parse_dump(r#"{}"#.as_bytes());
        let expected: Vec<(i32,i32,i32,i32)> = vec![(1,0,2,0)];
        assert_eq!(toks, expected, "case 6");
    }
    #[test]
    fn test_parse_7() {
        let toks = parse_dump(r#"[]"#.as_bytes());
        let expected: Vec<(i32,i32,i32,i32)> = vec![(2,0,2,0)];
        assert_eq!(toks, expected, "case 7");
    }
    #[test]
    fn test_parse_8() {
        let toks = parse_dump(r#"{"x":{"y":2}}"#.as_bytes());
        let expected: Vec<(i32,i32,i32,i32)> = vec![(1,0,13,1), (4,2,3,1), (1,5,12,1), (4,7,8,1), (8,10,11,0)];
        assert_eq!(toks, expected, "case 8");
    }
    #[test]
    fn test_parse_9() {
        let toks = parse_dump(r#"[{"a":1},{"b":2}]"#.as_bytes());
        let expected: Vec<(i32,i32,i32,i32)> = vec![(2,0,17,2), (1,1,8,1), (4,3,4,1), (8,6,7,0), (1,9,16,1), (4,11,12,1), (8,14,15,0)];
        assert_eq!(toks, expected, "case 9");
    }
    #[test]
    fn test_parse_10() {
        let toks = parse_dump(r#""a\"b""#.as_bytes());
        let expected: Vec<(i32,i32,i32,i32)> = vec![(4,1,5,0)];
        assert_eq!(toks, expected, "case 10");
    }
    #[test]
    fn test_parse_11() {
        let toks = parse_dump(r#"-4.5e3"#.as_bytes());
        let expected: Vec<(i32,i32,i32,i32)> = vec![(8,0,6,0)];
        assert_eq!(toks, expected, "case 11");
    }
    #[test]
    fn test_parse_12() {
        let toks = parse_dump(r#"{"name":"jsmn","n":42,"ok":true,"vals":[1,2,3],"nested":{"deep":null}}"#.as_bytes());
        let expected: Vec<(i32,i32,i32,i32)> = vec![(1,0,70,5), (4,2,6,1), (4,9,13,0), (4,16,17,1), (8,19,21,0), (4,23,25,1), (8,27,31,0), (4,33,37,1), (2,39,46,3), (8,40,41,0), (8,42,43,0), (8,44,45,0), (4,48,54,1), (1,56,69,1), (4,58,62,1), (8,64,68,0)];
        assert_eq!(toks, expected, "case 12");
    }
}
