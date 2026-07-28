#![forbid(unsafe_code)]
#![allow(unused_imports)]
#![no_std]
#[macro_use]
extern crate alloc;
use alloc::vec::Vec;
use alloc::string::String;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ValidationError {
    /// The value does not match the type specified in the schema.
    TypeMismatch(String),
    /// A required field defined in the schema is missing.
    MissingRequiredField(String),
}

impl core::fmt::Display for ValidationError {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        core::fmt::Debug::fmt(self, f)
    }
}
