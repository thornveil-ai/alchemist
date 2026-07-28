#![forbid(unsafe_code)]
#![allow(unused_imports)]
#![no_std]
#[macro_use]
extern crate alloc;
use alloc::vec::Vec;
use alloc::string::String;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ParseError {
    /// The input string does not conform to JSON syntax.
    InvalidSyntax(usize),
    /// The input contains invalid UTF-8 sequences.
    InvalidUtf8,
}

impl core::fmt::Display for ParseError {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        core::fmt::Debug::fmt(self, f)
    }
}
