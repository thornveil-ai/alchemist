#![forbid(unsafe_code)]
#![allow(unused_imports)]
#![no_std]
#[macro_use]
extern crate alloc;
use alloc::vec::Vec;
use alloc::string::String;

pub mod jsmn;

pub use self::jsmn::*;

/// Interface for parsing a JSON string into a sequence of tokens without
/// allocating memory for values.
pub trait JsonTokenizer {
    /// Parses the input string and populates the provided token slice.
    fn parse<'a>(&mut self, input: &'a str, tokens: &mut [Token]) -> Result<usize, ParseError>;
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ParseError {
    /// The input string is not valid JSON.
    InvalidJson,
    /// The provided token slice was too small to hold all tokens.
    BufferTooSmall,
}

impl core::fmt::Display for ParseError {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        core::fmt::Debug::fmt(self, f)
    }
}
