#![forbid(unsafe_code)]
#![allow(unused_imports)]
#![no_std]
#[macro_use]
extern crate alloc;
use alloc::vec::Vec;
use alloc::string::String;

/// Trait for types that can be serialized into a JSON format.
pub trait JsonSerializable {
    /// Serializes the value into the provided buffer.
    fn serialize(&self, buf: &mut [u8]) -> Result<usize, SerializationError>;
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SerializationError {
    /// The provided buffer is insufficient to hold the serialized output.
    BufferTooSmall(usize),
}

impl core::fmt::Display for SerializationError {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        core::fmt::Debug::fmt(self, f)
    }
}
