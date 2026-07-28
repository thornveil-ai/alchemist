#![forbid(unsafe_code)]
#![allow(unused_imports)]
#![no_std]
#[macro_use]
extern crate alloc;
use alloc::vec::Vec;
use alloc::string::String;

pub mod parson;

pub use self::parson::*;

/// Common interface for data_structure functions with matching signature shape.
pub trait Data_Structure {
    /// Computes the data_structure value for the given input. Shared across 3
    /// implementors.
    fn compute(&self) -> Option<JsonValue>;
}

/// Common interface for utility functions with matching signature shape.
pub trait Utility {
    /// Computes the utility value for the given input. Shared across 2 implementors.
    fn compute(&self) -> usize;
}
