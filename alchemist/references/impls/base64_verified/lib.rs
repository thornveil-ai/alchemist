#![allow(dead_code, clippy::needless_range_loop)]
// base64 (public domain, WEI Zhicheng) — coherent Rust skeleton.
// Tables + constants provided (pure data); the 2 FUNCTIONS are for the model.
pub const BASE64_PAD: u8 = b'=';
pub const BASE64EN: [u8; 64] = *b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
pub const BASE64DE: [u8; 128] = [255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,62,255,255,255,63,52,53,54,55,56,57,58,59,60,61,255,255,255,255,255,255,255,0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,255,255,255,255,255,255,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,255,255,255,255,255];

// C: unsigned int base64_encode(const unsigned char *in, unsigned int inlen, char *out)
//   -> coherent: take the input slice, RETURN the encoded bytes (the C `out`).
pub fn base64_encode(input: &[u8]) -> Vec<u8> {
    let mut out = Vec::new();
    let mut s = 0;
    let mut l = 0u8;

    for &c in input {
        match s {
            0 => {
                s = 1;
                out.push(BASE64EN[((c >> 2) & 0x3F) as usize]);
            }
            1 => {
                s = 2;
                out.push(BASE64EN[(((l & 0x3) << 4) | ((c >> 4) & 0xF)) as usize]);
            }
            2 => {
                s = 0;
                out.push(BASE64EN[(((l & 0xF) << 2) | ((c >> 6) & 0x3)) as usize]);
                out.push(BASE64EN[(c & 0x3F) as usize]);
            }
            _ => unreachable!(),
        }
        l = c;
    }

    match s {
        1 => {
            out.push(BASE64EN[((l & 0x3) << 4) as usize]);
            out.push(BASE64_PAD);
            out.push(BASE64_PAD);
        }
        2 => {
            out.push(BASE64EN[((l & 0xF) << 2) as usize]);
            out.push(BASE64_PAD);
        }
        _ => {}
    }

    out
}

// C: unsigned int base64_decode(const char *in, unsigned int inlen, unsigned char *out)
pub fn base64_decode(input: &[u8]) -> Vec<u8> {
    let inlen = input.len();
    if inlen & 0x3 != 0 {
        return Vec::new();
    }

    let mut out = vec![0u8; inlen];
    let mut j = 0;

    for i in 0..inlen {
        let b = input[i];
        if b == BASE64_PAD {
            break;
        }
        if b < 43 || b > 122 {
            return Vec::new();
        }

        let c = BASE64DE[b as usize];
        if c == 255 {
            return Vec::new();
        }

        match i & 0x3 {
            0 => {
                out[j] = (c << 2) & 0xFF;
            }
            1 => {
                out[j] |= (c >> 4) & 0x3;
                j += 1;
                out[j] = (c & 0xF) << 4;
            }
            2 => {
                out[j] |= (c >> 2) & 0xF;
                j += 1;
                out[j] = (c & 0x3) << 6;
            }
            3 => {
                out[j] |= c;
                j += 1;
            }
            _ => unreachable!(),
        }
    }

    out.truncate(j);
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn test_encode_0() { assert_eq!(base64_encode(&[]), &[]); }
    #[test]
    fn test_roundtrip_0() { let e=base64_encode(&[]); assert_eq!(base64_decode(&e), &[]); }
    #[test]
    fn test_encode_1() { assert_eq!(base64_encode(&[102]), &[90,103,61,61]); }
    #[test]
    fn test_roundtrip_1() { let e=base64_encode(&[102]); assert_eq!(base64_decode(&e), &[102]); }
    #[test]
    fn test_encode_2() { assert_eq!(base64_encode(&[102,111]), &[90,109,56,61]); }
    #[test]
    fn test_roundtrip_2() { let e=base64_encode(&[102,111]); assert_eq!(base64_decode(&e), &[102,111]); }
    #[test]
    fn test_encode_3() { assert_eq!(base64_encode(&[102,111,111]), &[90,109,57,118]); }
    #[test]
    fn test_roundtrip_3() { let e=base64_encode(&[102,111,111]); assert_eq!(base64_decode(&e), &[102,111,111]); }
    #[test]
    fn test_encode_4() { assert_eq!(base64_encode(&[102,111,111,98]), &[90,109,57,118,89,103,61,61]); }
    #[test]
    fn test_roundtrip_4() { let e=base64_encode(&[102,111,111,98]); assert_eq!(base64_decode(&e), &[102,111,111,98]); }
    #[test]
    fn test_encode_5() { assert_eq!(base64_encode(&[102,111,111,98,97]), &[90,109,57,118,89,109,69,61]); }
    #[test]
    fn test_roundtrip_5() { let e=base64_encode(&[102,111,111,98,97]); assert_eq!(base64_decode(&e), &[102,111,111,98,97]); }
    #[test]
    fn test_encode_6() { assert_eq!(base64_encode(&[102,111,111,98,97,114]), &[90,109,57,118,89,109,70,121]); }
    #[test]
    fn test_roundtrip_6() { let e=base64_encode(&[102,111,111,98,97,114]); assert_eq!(base64_decode(&e), &[102,111,111,98,97,114]); }
    #[test]
    fn test_encode_7() { assert_eq!(base64_encode(&[0,255,128,1,2]), &[65,80,43,65,65,81,73,61]); }
    #[test]
    fn test_roundtrip_7() { let e=base64_encode(&[0,255,128,1,2]); assert_eq!(base64_decode(&e), &[0,255,128,1,2]); }
    #[test]
    fn test_encode_8() { assert_eq!(base64_encode(&[0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19]), &[65,65,69,67,65,119,81,70,66,103,99,73,67,81,111,76,68,65,48,79,68,120,65,82,69,104,77,61]); }
    #[test]
    fn test_roundtrip_8() { let e=base64_encode(&[0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19]); assert_eq!(base64_decode(&e), &[0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19]); }
    #[test]
    fn test_encode_9() { assert_eq!(base64_encode(&[77,97,110,121,32,104,97,110,100,115,32,109,97,107,101,32,108,105,103,104,116,32,119,111,114,107,46]), &[84,87,70,117,101,83,66,111,89,87,53,107,99,121,66,116,89,87,116,108,73,71,120,112,90,50,104,48,73,72,100,118,99,109,115,117]); }
    #[test]
    fn test_roundtrip_9() { let e=base64_encode(&[77,97,110,121,32,104,97,110,100,115,32,109,97,107,101,32,108,105,103,104,116,32,119,111,114,107,46]); assert_eq!(base64_decode(&e), &[77,97,110,121,32,104,97,110,100,115,32,109,97,107,101,32,108,105,103,104,116,32,119,111,114,107,46]); }
    #[test]
    fn test_encode_10() { assert_eq!(base64_encode(&[59,3,46,17,42,50,181,121,8,15,8,177,247,237,76,46,93,58,7,249,127,33,238,35,45,23,138,32,154]), &[79,119,77,117,69,83,111,121,116,88,107,73,68,119,105,120,57,43,49,77,76,108,48,54,66,47,108,47,73,101,52,106,76,82,101,75,73,74,111,61]); }
    #[test]
    fn test_roundtrip_10() { let e=base64_encode(&[59,3,46,17,42,50,181,121,8,15,8,177,247,237,76,46,93,58,7,249,127,33,238,35,45,23,138,32,154]); assert_eq!(base64_decode(&e), &[59,3,46,17,42,50,181,121,8,15,8,177,247,237,76,46,93,58,7,249,127,33,238,35,45,23,138,32,154]); }
    #[test]
    fn test_encode_11() { assert_eq!(base64_encode(&[181,136,127,102,232,9,36,2,170,73,242,193,85,27,39,254,83,38,110,73,13,177,56,72,156,232,20,213,141,20,90]), &[116,89,104,47,90,117,103,74,74,65,75,113,83,102,76,66,86,82,115,110,47,108,77,109,98,107,107,78,115,84,104,73,110,79,103,85,49,89,48,85,87,103,61,61]); }
    #[test]
    fn test_roundtrip_11() { let e=base64_encode(&[181,136,127,102,232,9,36,2,170,73,242,193,85,27,39,254,83,38,110,73,13,177,56,72,156,232,20,213,141,20,90]); assert_eq!(base64_decode(&e), &[181,136,127,102,232,9,36,2,170,73,242,193,85,27,39,254,83,38,110,73,13,177,56,72,156,232,20,213,141,20,90]); }
    #[test]
    fn test_encode_12() { assert_eq!(base64_encode(&[79,153,79,237,21,197,178,253,174,239,243,23,241,87,225,224,151,140]), &[84,53,108,80,55,82,88,70,115,118,50,117,55,47,77,88,56,86,102,104,52,74,101,77]); }
    #[test]
    fn test_roundtrip_12() { let e=base64_encode(&[79,153,79,237,21,197,178,253,174,239,243,23,241,87,225,224,151,140]); assert_eq!(base64_decode(&e), &[79,153,79,237,21,197,178,253,174,239,243,23,241,87,225,224,151,140]); }
    #[test]
    fn test_encode_13() { assert_eq!(base64_encode(&[95,213,223,61,52,248,192,130]), &[88,57,88,102,80,84,84,52,119,73,73,61]); }
    #[test]
    fn test_roundtrip_13() { let e=base64_encode(&[95,213,223,61,52,248,192,130]); assert_eq!(base64_decode(&e), &[95,213,223,61,52,248,192,130]); }
    #[test]
    fn test_encode_14() { assert_eq!(base64_encode(&[176,55,80,137,79,165,228,36,40,202,109,24,146]), &[115,68,100,81,105,85,43,108,53,67,81,111,121,109,48,89,107,103,61,61]); }
    #[test]
    fn test_roundtrip_14() { let e=base64_encode(&[176,55,80,137,79,165,228,36,40,202,109,24,146]); assert_eq!(base64_decode(&e), &[176,55,80,137,79,165,228,36,40,202,109,24,146]); }
    #[test]
    fn test_encode_15() { assert_eq!(base64_encode(&[112,44,162]), &[99,67,121,105]); }
    #[test]
    fn test_roundtrip_15() { let e=base64_encode(&[112,44,162]); assert_eq!(base64_decode(&e), &[112,44,162]); }
}
