"""Solves resistive/reactive electrical networks of arbitrary topology using
Modified Nodal Analysis (MNA) — the general technique behind most circuit
simulators (e.g. SPICE), not a special-cased series/parallel calculator.

Node "0" is always ground (0 V reference), matching SPICE convention. DC
analysis (`frequency_hz=0`) uses real arithmetic; AC/phasor analysis
(`frequency_hz>0`) uses complex arithmetic, with inductors/capacitors
represented by their frequency-dependent impedance.

Deterministic and side-effect-free: given the same netlist, always returns
the same answer — no LLM involved in the actual computation, matching how
ai/calculator.py handles arithmetic.
"""

import cmath
import math
from dataclasses import dataclass
from typing import Literal

import numpy as np

ElementType = Literal["R", "L", "C", "V", "I"]


class CircuitError(ValueError):
    """Raised for an invalid or unsolvable circuit."""


@dataclass
class Element:
    type: ElementType
    name: str
    node_pos: str
    node_neg: str
    value: float
    phase_degrees: float = 0.0


def _phasor(element: Element, is_ac: bool) -> complex | float:
    if not is_ac:
        return element.value
    return cmath.rect(element.value, math.radians(element.phase_degrees))


def solve_circuit(elements: list[Element], frequency_hz: float = 0.0) -> dict:
    """Solve a circuit's node voltages and voltage-source currents.

    Returns {"is_ac": bool, "frequency_hz": float, "node_voltages": {node:
    value}, "source_currents": {name: value}} where each value is a plain
    float for DC or a complex number for AC. Raises CircuitError for an
    invalid netlist (bad references, non-positive R/L/C, a floating/
    unsolvable network) rather than returning a nonsensical answer.
    """
    if not elements:
        raise CircuitError("A circuit needs at least one element")

    is_ac = frequency_hz > 0
    omega = 2 * math.pi * frequency_hz
    dtype = complex if is_ac else float

    for el in elements:
        if el.node_pos == el.node_neg:
            raise CircuitError(f"{el.name}: both terminals are on the same node ({el.node_pos})")
        if el.type in ("R", "L", "C") and el.value <= 0:
            raise CircuitError(f"{el.name}: {el.type} value must be positive, got {el.value}")
        if el.type in ("L", "C") and not is_ac:
            kind = "inductor" if el.type == "L" else "capacitor"
            shortcut = "a 0-ohm wire" if el.type == "L" else "an open circuit (omit it)"
            raise CircuitError(
                f"{el.name}: {kind}s need frequency_hz > 0 for AC analysis — "
                f"at DC steady state, model it as {shortcut} instead"
            )

    nodes = sorted({n for el in elements for n in (el.node_pos, el.node_neg) if n != "0"})
    if not nodes:
        raise CircuitError("Circuit has no non-ground nodes to solve for")
    node_index = {node: i for i, node in enumerate(nodes)}
    n = len(nodes)

    voltage_sources = [el for el in elements if el.type == "V"]
    vsrc_index = {el.name: n + i for i, el in enumerate(voltage_sources)}
    m = len(voltage_sources)

    size = n + m
    A = np.zeros((size, size), dtype=dtype)
    z = np.zeros(size, dtype=dtype)

    def stamp_admittance(node_pos: str, node_neg: str, y: complex | float) -> None:
        if node_pos != "0":
            i = node_index[node_pos]
            A[i, i] += y
            if node_neg != "0":
                A[i, node_index[node_neg]] -= y
        if node_neg != "0":
            j = node_index[node_neg]
            A[j, j] += y
            if node_pos != "0":
                A[j, node_index[node_pos]] -= y

    for el in elements:
        if el.type == "R":
            stamp_admittance(el.node_pos, el.node_neg, 1 / el.value)
        elif el.type == "L":
            stamp_admittance(el.node_pos, el.node_neg, 1 / (1j * omega * el.value))
        elif el.type == "C":
            stamp_admittance(el.node_pos, el.node_neg, 1j * omega * el.value)
        elif el.type == "I":
            # Positive `value` means the source injects current into
            # node_pos and draws it from node_neg (the intuitive "current
            # source pumping current into a node" direction).
            value = _phasor(el, is_ac)
            if el.node_pos != "0":
                z[node_index[el.node_pos]] += value
            if el.node_neg != "0":
                z[node_index[el.node_neg]] -= value
        elif el.type == "V":
            k = vsrc_index[el.name]
            value = _phasor(el, is_ac)
            if el.node_pos != "0":
                i = node_index[el.node_pos]
                A[i, k] += 1
                A[k, i] += 1
            if el.node_neg != "0":
                j = node_index[el.node_neg]
                A[j, k] -= 1
                A[k, j] -= 1
            z[k] = value
        else:
            raise CircuitError(f"{el.name}: unsupported element type {el.type!r}")

    try:
        x = np.linalg.solve(A, z)
    except np.linalg.LinAlgError as e:
        raise CircuitError(
            "Circuit has no unique solution — check that every node has a DC path to "
            "ground and that no two independent voltage sources conflict"
        ) from e

    node_voltages: dict[str, complex | float] = {node: dtype(x[i]) for node, i in node_index.items()}
    node_voltages["0"] = dtype(0)
    # The raw MNA unknown is the current flowing from node_neg to node_pos
    # through the source; negated here so a positive result means what a
    # student expects — current the source delivers into the circuit at
    # node_pos.
    source_currents = {el.name: -dtype(x[vsrc_index[el.name]]) for el in voltage_sources}

    return {
        "is_ac": is_ac,
        "frequency_hz": frequency_hz,
        "node_voltages": node_voltages,
        "source_currents": source_currents,
    }
