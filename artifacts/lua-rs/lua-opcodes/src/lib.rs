//! lua-opcodes — Lua 5.4 bytecode ISA (Phase C, lopcodes.h/.c).
//!
//! The instruction set the parser (lcode) emits and the VM (lvm) consumes.
//! Everything downstream — parser, VM, dump/undump — depends on this being
//! BYTE-EXACT, so the encoding is a literal transcription of lopcodes.h and the
//! OpCode order is the ORDER OP invariant (OP_MOVE=0 .. OP_EXTRAARG=82).
#![allow(non_camel_case_types)]

/// A bytecode instruction word (`Instruction` in Lua = 32-bit unsigned).
pub type Instruction = u32;

// Field sizes / positions (lopcodes.h). Layout: C(8)|B(8)|k(1)|A(8)|Op(7).
pub const SIZE_OP: u32 = 7;
pub const SIZE_A: u32 = 8;
pub const SIZE_B: u32 = 8;
pub const SIZE_C: u32 = 8;
pub const SIZE_BX: u32 = SIZE_C + SIZE_B + 1; // 17
pub const SIZE_AX: u32 = SIZE_BX + SIZE_A; // 25
pub const SIZE_SJ: u32 = SIZE_BX + SIZE_A; // 25

pub const POS_OP: u32 = 0;
pub const POS_A: u32 = POS_OP + SIZE_OP; // 7
pub const POS_K: u32 = POS_A + SIZE_A; // 15
pub const POS_B: u32 = POS_K + 1; // 16
pub const POS_C: u32 = POS_B + SIZE_B; // 24
pub const POS_BX: u32 = POS_K; // 15
pub const POS_AX: u32 = POS_A; // 7
pub const POS_SJ: u32 = POS_A; // 7

pub const MAXARG_A: i32 = (1 << SIZE_A) - 1; // 255
pub const MAXARG_B: i32 = (1 << SIZE_B) - 1; // 255
pub const MAXARG_C: i32 = (1 << SIZE_C) - 1; // 255
pub const MAXARG_BX: i32 = (1 << SIZE_BX) - 1; // 131071
pub const MAXARG_AX: i32 = (1i32.wrapping_shl(SIZE_AX)).wrapping_sub(1); // 2^25-1
pub const OFFSET_SBX: i32 = MAXARG_BX >> 1; // 65535
pub const OFFSET_SC: i32 = MAXARG_C >> 1; // 127
pub const OFFSET_SJ: i32 = ((1i64 << SIZE_SJ) - 1) as i32 >> 1;

#[inline]
fn mask1(n: u32) -> u32 {
    !((!0u32) << n)
}
#[inline]
fn getarg(i: Instruction, pos: u32, size: u32) -> i32 {
    ((i >> pos) & mask1(size)) as i32
}

// ---- decode ----
pub fn get_opcode(i: Instruction) -> OpCode {
    OpCode::from_u8((i & mask1(SIZE_OP)) as u8)
}
pub fn getarg_a(i: Instruction) -> i32 { getarg(i, POS_A, SIZE_A) }
pub fn getarg_b(i: Instruction) -> i32 { getarg(i, POS_B, SIZE_B) }
pub fn getarg_c(i: Instruction) -> i32 { getarg(i, POS_C, SIZE_C) }
pub fn getarg_k(i: Instruction) -> i32 { getarg(i, POS_K, 1) }
pub fn getarg_bx(i: Instruction) -> i32 { getarg(i, POS_BX, SIZE_BX) }
pub fn getarg_sbx(i: Instruction) -> i32 { getarg(i, POS_BX, SIZE_BX) - OFFSET_SBX }
pub fn getarg_ax(i: Instruction) -> i32 { getarg(i, POS_AX, SIZE_AX) }
pub fn getarg_sj(i: Instruction) -> i32 { getarg(i, POS_SJ, SIZE_SJ) - OFFSET_SJ }
pub fn sc2int(c: i32) -> i32 { c - OFFSET_SC }
pub fn int2sc(c: i32) -> i32 { c + OFFSET_SC }

// ---- encode (CREATE_* macros) ----
pub fn create_abck(o: OpCode, a: i32, b: i32, c: i32, k: i32) -> Instruction {
    ((o as u32) << POS_OP)
        | ((a as u32) << POS_A)
        | ((b as u32) << POS_B)
        | ((c as u32) << POS_C)
        | ((k as u32) << POS_K)
}
pub fn create_abx(o: OpCode, a: i32, bc: i32) -> Instruction {
    ((o as u32) << POS_OP) | ((a as u32) << POS_A) | ((bc as u32) << POS_BX)
}
pub fn create_asbx(o: OpCode, a: i32, sbx: i32) -> Instruction {
    create_abx(o, a, sbx + OFFSET_SBX)
}
pub fn create_ax(o: OpCode, a: i32) -> Instruction {
    ((o as u32) << POS_OP) | ((a as u32) << POS_AX)
}
pub fn create_sj(o: OpCode, j: i32, k: i32) -> Instruction {
    ((o as u32) << POS_OP) | ((j as u32) << POS_SJ) | ((k as u32) << POS_K)
}

/// The 83 opcodes in EXACT Lua 5.4 order (the ORDER OP invariant). `repr(u8)`
/// so `OP_MOVE == 0` matches `GET_OPCODE`.
#[repr(u8)]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum OpCode {
    OP_MOVE, OP_LOADI, OP_LOADF, OP_LOADK, OP_LOADKX, OP_LOADFALSE, OP_LFALSESKIP,
    OP_LOADTRUE, OP_LOADNIL, OP_GETUPVAL, OP_SETUPVAL, OP_GETTABUP, OP_GETTABLE,
    OP_GETI, OP_GETFIELD, OP_SETTABUP, OP_SETTABLE, OP_SETI, OP_SETFIELD,
    OP_NEWTABLE, OP_SELF, OP_ADDI, OP_ADDK, OP_SUBK, OP_MULK, OP_MODK, OP_POWK,
    OP_DIVK, OP_IDIVK, OP_BANDK, OP_BORK, OP_BXORK, OP_SHRI, OP_SHLI, OP_ADD,
    OP_SUB, OP_MUL, OP_MOD, OP_POW, OP_DIV, OP_IDIV, OP_BAND, OP_BOR, OP_BXOR,
    OP_SHL, OP_SHR, OP_MMBIN, OP_MMBINI, OP_MMBINK, OP_UNM, OP_BNOT, OP_NOT,
    OP_LEN, OP_CONCAT, OP_CLOSE, OP_TBC, OP_JMP, OP_EQ, OP_LT, OP_LE, OP_EQK,
    OP_EQI, OP_LTI, OP_LEI, OP_GTI, OP_GEI, OP_TEST, OP_TESTSET, OP_CALL,
    OP_TAILCALL, OP_RETURN, OP_RETURN0, OP_RETURN1, OP_FORLOOP, OP_FORPREP,
    OP_TFORPREP, OP_TFORCALL, OP_TFORLOOP, OP_SETLIST, OP_CLOSURE, OP_VARARG,
    OP_VARARGPREP, OP_EXTRAARG,
}

pub const NUM_OPCODES: usize = 83;

impl OpCode {
    pub fn from_u8(v: u8) -> OpCode {
        assert!((v as usize) < NUM_OPCODES, "opcode out of range");
        // Safe: repr(u8), contiguous 0..83, bounds-checked above.
        unsafe { std::mem::transmute(v) }
    }
    /// Opcode mnemonic exactly as `luaP_opnames` / `luac -l` prints it.
    pub fn name(self) -> &'static str {
        OPNAMES[self as usize]
    }
}

/// `luaP_opnames` — mnemonics in opcode order (matches `luac -l` output).
pub const OPNAMES: [&str; NUM_OPCODES] = [
    "MOVE", "LOADI", "LOADF", "LOADK", "LOADKX", "LOADFALSE", "LFALSESKIP",
    "LOADTRUE", "LOADNIL", "GETUPVAL", "SETUPVAL", "GETTABUP", "GETTABLE",
    "GETI", "GETFIELD", "SETTABUP", "SETTABLE", "SETI", "SETFIELD", "NEWTABLE",
    "SELF", "ADDI", "ADDK", "SUBK", "MULK", "MODK", "POWK", "DIVK", "IDIVK",
    "BANDK", "BORK", "BXORK", "SHRI", "SHLI", "ADD", "SUB", "MUL", "MOD", "POW",
    "DIV", "IDIV", "BAND", "BOR", "BXOR", "SHL", "SHR", "MMBIN", "MMBINI",
    "MMBINK", "UNM", "BNOT", "NOT", "LEN", "CONCAT", "CLOSE", "TBC", "JMP",
    "EQ", "LT", "LE", "EQK", "EQI", "LTI", "LEI", "GTI", "GEI", "TEST",
    "TESTSET", "CALL", "TAILCALL", "RETURN", "RETURN0", "RETURN1", "FORLOOP",
    "FORPREP", "TFORPREP", "TFORCALL", "TFORLOOP", "SETLIST", "CLOSURE",
    "VARARG", "VARARGPREP", "EXTRAARG",
];

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn opcode_order_invariant() {
        assert_eq!(OpCode::OP_MOVE as u8, 0);
        assert_eq!(OpCode::OP_LOADK as u8, 3);
        assert_eq!(OpCode::OP_CALL as u8, 68);
        assert_eq!(OpCode::OP_EXTRAARG as u8, 82);
        assert_eq!(NUM_OPCODES, 83);
        assert_eq!(OpCode::OP_CALL.name(), "CALL");
        assert_eq!(OpCode::from_u8(68), OpCode::OP_CALL);
    }

    #[test]
    fn constants_match_lopcodes_h() {
        assert_eq!(POS_A, 7);
        assert_eq!(POS_K, 15);
        assert_eq!(POS_B, 16);
        assert_eq!(POS_C, 24);
        assert_eq!(SIZE_BX, 17);
        assert_eq!(OFFSET_SBX, 65535);
        assert_eq!(OFFSET_SC, 127);
        assert_eq!(MAXARG_BX, 131071);
    }

    #[test]
    fn abc_encode_decode_roundtrip() {
        let i = create_abck(OpCode::OP_ADD, 5, 200, 17, 1);
        assert_eq!(get_opcode(i), OpCode::OP_ADD);
        assert_eq!(getarg_a(i), 5);
        assert_eq!(getarg_b(i), 200);
        assert_eq!(getarg_c(i), 17);
        assert_eq!(getarg_k(i), 1);
    }

    #[test]
    fn abx_asbx_ax_roundtrip() {
        let i = create_abx(OpCode::OP_LOADK, 3, 100000);
        assert_eq!(get_opcode(i), OpCode::OP_LOADK);
        assert_eq!(getarg_a(i), 3);
        assert_eq!(getarg_bx(i), 100000);

        let j = create_asbx(OpCode::OP_FORPREP, 2, -5);
        assert_eq!(getarg_sbx(j), -5);
        assert_eq!(getarg_a(j), 2);

        let k = create_ax(OpCode::OP_EXTRAARG, 1234567);
        assert_eq!(get_opcode(k), OpCode::OP_EXTRAARG);
        assert_eq!(getarg_ax(k), 1234567);
    }

    #[test]
    fn encoding_is_byte_identical_to_c_lua() {
        // Golden u32 values captured from reference C-lua's CREATE_* macros
        // (gcc + lopcodes.h). Our encoding must reproduce them bit-for-bit.
        assert_eq!(create_abck(OpCode::OP_ADD, 5, 200, 17, 1), 298353314);
        assert_eq!(create_abx(OpCode::OP_LOADK, 3, 100000), 3276800387);
        assert_eq!(create_asbx(OpCode::OP_FORPREP, 2, -5), 2147287370);
        assert_eq!(create_ax(OpCode::OP_EXTRAARG, 1234567), 158024658);
    }

    #[test]
    fn signed_c_helpers() {
        assert_eq!(sc2int(int2sc(0)), 0);
        assert_eq!(sc2int(int2sc(-100)), -100);
        assert_eq!(int2sc(0), 127);
    }
}
