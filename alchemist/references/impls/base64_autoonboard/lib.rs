#![allow(dead_code, clippy::needless_range_loop, unused_variables)]
// Auto-onboarded from base64.c. Tables provided as data; functions for the model.
pub const BASE64_PAD: u8 = 61;
pub const BASE64DE_FIRST: u8 = 43;
pub const BASE64DE_LAST: u8 = 122;
pub const BASE64EN: [u8; 64] = [65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 43, 47];
pub const BASE64DE: [u8; 128] = [255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 62, 255, 255, 255, 63, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 255, 255, 255, 255, 255, 255, 255, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 255, 255, 255, 255, 255, 255, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 255, 255, 255, 255, 255];

pub fn base64_encode(data: &[u8]) -> Vec<u8> {
    let mut out = Vec::new();
    let mut s = 0;
    let mut l = 0u8;

    for &c in data {
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
pub fn base64_decode(data: &[u8]) -> Vec<u8> {
    let inlen = data.len();
    if inlen & 0x3 != 0 {
        return Vec::new();
    }

    let mut out = vec![0u8; inlen * 3 / 4];
    let mut i = 0;
    let mut j = 0;

    while i < inlen {
        let b = data[i];
        if b == BASE64_PAD {
            break;
        }
        if b < BASE64DE_FIRST || b > BASE64DE_LAST {
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
        i += 1;
    }

    out[..j].to_vec()
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn t_base64_encode_0(){ assert_eq!(base64_encode(&[]).as_slice(), &[]); }
    #[test]
    fn t_base64_encode_1(){ assert_eq!(base64_encode(&[89, 81, 61, 61]).as_slice(), &[87, 86, 69, 57, 80, 81, 61, 61]); }
    #[test]
    fn t_base64_encode_2(){ assert_eq!(base64_encode(&[89, 87, 74, 106]).as_slice(), &[87, 86, 100, 75, 97, 103, 61, 61]); }
    #[test]
    fn t_base64_encode_3(){ assert_eq!(base64_encode(&[83, 71, 86, 115, 98, 71, 56, 104]).as_slice(), &[85, 48, 100, 87, 99, 50, 74, 72, 79, 71, 103, 61]); }
    #[test]
    fn t_base64_encode_4(){ assert_eq!(base64_encode(&[55, 117, 100, 104, 88, 118, 78, 102, 77, 79, 83, 98, 83, 67, 52, 86, 121, 117, 100, 81]).as_slice(), &[78, 51, 86, 107, 97, 70, 104, 50, 84, 109, 90, 78, 84, 49, 78, 105, 85, 48, 77, 48, 86, 110, 108, 49, 90, 70, 69, 61]); }
    #[test]
    fn t_base64_encode_5(){ assert_eq!(base64_encode(&[73, 65, 61, 61]).as_slice(), &[83, 85, 69, 57, 80, 81, 61, 61]); }
    #[test]
    fn t_base64_encode_6(){ assert_eq!(base64_encode(&[69, 109, 69, 61]).as_slice(), &[82, 87, 49, 70, 80, 81, 61, 61]); }
    #[test]
    fn t_base64_encode_7(){ assert_eq!(base64_encode(&[68, 43, 50, 110, 52, 87, 82, 51, 108, 118, 56, 61]).as_slice(), &[82, 67, 115, 121, 98, 106, 82, 88, 85, 106, 78, 115, 100, 106, 103, 57]); }
    #[test]
    fn t_base64_encode_8(){ assert_eq!(base64_encode(&[75, 119, 61, 61]).as_slice(), &[83, 51, 99, 57, 80, 81, 61, 61]); }
    #[test]
    fn t_base64_encode_9(){ assert_eq!(base64_encode(&[106, 116, 65, 113, 103, 113, 70, 49, 107, 119, 56, 106, 78, 56, 48, 51, 108, 77, 85, 105]).as_slice(), &[97, 110, 82, 66, 99, 87, 100, 120, 82, 106, 70, 114, 100, 122, 104, 113, 84, 106, 103, 119, 77, 50, 120, 78, 86, 87, 107, 61]); }
    #[test]
    fn t_base64_encode_10(){ assert_eq!(base64_encode(&[65, 65, 61, 61]).as_slice(), &[81, 85, 69, 57, 80, 81, 61, 61]); }
    #[test]
    fn t_base64_encode_11(){ assert_eq!(base64_encode(&[97, 120, 114, 119, 119, 77, 118, 87, 74, 81, 61, 61]).as_slice(), &[89, 88, 104, 121, 100, 51, 100, 78, 100, 108, 100, 75, 85, 84, 48, 57]); }
    #[test]
    fn t_base64_decode_0(){ assert_eq!(base64_decode(&[]).as_slice(), &[]); }
    #[test]
    fn t_base64_decode_1(){ assert_eq!(base64_decode(&[89, 81, 61, 61]).as_slice(), &[97]); }
    #[test]
    fn t_base64_decode_2(){ assert_eq!(base64_decode(&[89, 87, 74, 106]).as_slice(), &[97, 98, 99]); }
    #[test]
    fn t_base64_decode_3(){ assert_eq!(base64_decode(&[83, 71, 86, 115, 98, 71, 56, 104]).as_slice(), &[72, 101, 108, 108, 111, 33]); }
    #[test]
    fn t_base64_decode_4(){ assert_eq!(base64_decode(&[55, 117, 100, 104, 88, 118, 78, 102, 77, 79, 83, 98, 83, 67, 52, 86, 121, 117, 100, 81]).as_slice(), &[238, 231, 97, 94, 243, 95, 48, 228, 155, 72, 46, 21, 202, 231, 80]); }
    #[test]
    fn t_base64_decode_5(){ assert_eq!(base64_decode(&[73, 65, 61, 61]).as_slice(), &[32]); }
    #[test]
    fn t_base64_decode_6(){ assert_eq!(base64_decode(&[69, 109, 69, 61]).as_slice(), &[18, 97]); }
    #[test]
    fn t_base64_decode_7(){ assert_eq!(base64_decode(&[68, 43, 50, 110, 52, 87, 82, 51, 108, 118, 56, 61]).as_slice(), &[15, 237, 167, 225, 100, 119, 150, 255]); }
    #[test]
    fn t_base64_decode_8(){ assert_eq!(base64_decode(&[75, 119, 61, 61]).as_slice(), &[43]); }
    #[test]
    fn t_base64_decode_9(){ assert_eq!(base64_decode(&[106, 116, 65, 113, 103, 113, 70, 49, 107, 119, 56, 106, 78, 56, 48, 51, 108, 77, 85, 105]).as_slice(), &[142, 208, 42, 130, 161, 117, 147, 15, 35, 55, 205, 55, 148, 197, 34]); }
    #[test]
    fn t_base64_decode_10(){ assert_eq!(base64_decode(&[65, 65, 61, 61]).as_slice(), &[0]); }
    #[test]
    fn t_base64_decode_11(){ assert_eq!(base64_decode(&[97, 120, 114, 119, 119, 77, 118, 87, 74, 81, 61, 61]).as_slice(), &[107, 26, 240, 192, 203, 214, 37]); }
}
