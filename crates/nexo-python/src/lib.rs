//! Optional PyO3 adapter. The nexo-core crate owns the wire protocol.
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyAny, PyModule};
use serde_json::Value;

fn json_input(py: Python<'_>, input: &Bound<'_, PyAny>) -> PyResult<Value> {
    py.import("nexo.codec")?.getattr("_validate")?.call1((input,))?;
    let source: String = py.import("json")?.call_method1("dumps", (input,))?.extract()?;
    serde_json::from_str(&source).map_err(|e| PyValueError::new_err(e.to_string()))
}

#[pyfunction]
fn encode_text(py: Python<'_>, input: &Bound<'_, PyAny>) -> PyResult<String> {
    nexo_core::encode_text(&json_input(py, input)?)
        .map_err(|e| PyValueError::new_err(e.to_string()))
}

#[pyfunction]
fn encode_binary(py: Python<'_>, input: &Bound<'_, PyAny>) -> PyResult<Vec<u8>> {
    nexo_core::encode_binary(&json_input(py, input)?)
        .map_err(|e| PyValueError::new_err(e.to_string()))
}

#[pyfunction]
fn decode(py: Python<'_>, input: &Bound<'_, PyAny>) -> PyResult<PyObject> {
    let raw: Vec<u8> = match input.extract::<String>() {
        Ok(text) => text.into_bytes(),
        Err(_) => input.extract::<Vec<u8>>()?,
    };
    let value = nexo_core::decode(&raw).map_err(|e| PyValueError::new_err(e.to_string()))?;
    let json_text = serde_json::to_string(&value)
        .map_err(|e| PyValueError::new_err(e.to_string()))?;
    Ok(py.import("json")?.call_method1("loads", (json_text,))?.unbind())
}

#[pymodule]
fn nexo_native(_py: Python<'_>, module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(encode_text, module)?)?;
    module.add_function(wrap_pyfunction!(encode_binary, module)?)?;
    module.add_function(wrap_pyfunction!(decode, module)?)?;
    Ok(())
}
