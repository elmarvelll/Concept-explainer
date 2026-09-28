import cmath
import math

import pytest

from ai.circuit_solver import CircuitError, Element, solve_circuit


def test_single_resistor_across_voltage_source():
    # 12V source across a 4-ohm resistor: V(node1) = 12V, I = 3A.
    elements = [
        Element("V", "V1", "1", "0", 12),
        Element("R", "R1", "1", "0", 4),
    ]
    result = solve_circuit(elements)
    assert result["node_voltages"]["1"] == pytest.approx(12)
    # Positive: the source is delivering 3A into the circuit at node 1.
    assert result["source_currents"]["V1"] == pytest.approx(3)


def test_voltage_divider():
    # 12V source, R1=1k from node1->node2, R2=2k from node2->ground.
    # V(node2) = 12 * R2/(R1+R2) = 8V.
    elements = [
        Element("V", "V1", "1", "0", 12),
        Element("R", "R1", "1", "2", 1000),
        Element("R", "R2", "2", "0", 2000),
    ]
    result = solve_circuit(elements)
    assert result["node_voltages"]["1"] == pytest.approx(12)
    assert result["node_voltages"]["2"] == pytest.approx(8)


def test_parallel_resistors_with_current_source():
    # 6A current source into a node with two parallel resistors (2 ohm and
    # 3 ohm) to ground. Combined resistance = 2*3/5 = 1.2 ohm.
    # V = I * R = 6 * 1.2 = 7.2V.
    elements = [
        Element("I", "I1", "1", "0", 6),
        Element("R", "R1", "1", "0", 2),
        Element("R", "R2", "1", "0", 3),
    ]
    result = solve_circuit(elements)
    assert result["node_voltages"]["1"] == pytest.approx(7.2)


def test_wheatstone_bridge_unbalanced():
    # A classic bridge that can't be solved by simple series/parallel
    # reduction — this is exactly what MNA is for. Cross-check against an
    # independently hand-derived nodal-analysis solution.
    #    node1 --R1(1k)-- node2 --R2(1k)-- node0(gnd)
    #    node1 --R3(2k)-- node3 --R4(1k)-- node0(gnd)
    #    node2 --R5(1k, bridge)-- node3
    #    V1: node1 -> node0, 10V
    elements = [
        Element("V", "V1", "1", "0", 10),
        Element("R", "R1", "1", "2", 1000),
        Element("R", "R2", "2", "0", 1000),
        Element("R", "R3", "1", "3", 2000),
        Element("R", "R4", "3", "0", 1000),
        Element("R", "R5", "2", "3", 1000),
    ]
    result = solve_circuit(elements)

    # Independently verify via raw nodal-analysis KCL equations (not reusing
    # solve_circuit's own machinery) at node2 and node3, with V(node1)=10
    # fixed by the source:
    v1 = 10
    # KCL at node2: (v2-v1)/R1 + (v2-0)/R2 + (v2-v3)/R5 = 0
    # KCL at node3: (v3-v1)/R3 + (v3-0)/R4 + (v3-v2)/R5 = 0
    import numpy as np

    A = np.array(
        [
            [1 / 1000 + 1 / 1000 + 1 / 1000, -1 / 1000],
            [-1 / 1000, 1 / 2000 + 1 / 1000 + 1 / 1000],
        ]
    )
    b = np.array([v1 / 1000, v1 / 2000])
    v2_expected, v3_expected = np.linalg.solve(A, b)

    assert result["node_voltages"]["2"] == pytest.approx(v2_expected)
    assert result["node_voltages"]["3"] == pytest.approx(v3_expected)


def test_ac_rc_series_impedance_divider():
    # AC source 10V(0 deg) at 1kHz across R=1000 ohm in series with
    # C=159.15nF (chosen so that 1/(wC) ~= 1000 ohm at 1kHz, i.e. a 45
    # degree phase drop across the divider).
    freq = 1000.0
    omega = 2 * math.pi * freq
    C = 1 / (omega * 1000)  # exactly makes Xc == R == 1000 ohm

    elements = [
        Element("V", "V1", "1", "0", 10),
        Element("R", "R1", "1", "2", 1000),
        Element("C", "C1", "2", "0", C),
    ]
    result = solve_circuit(elements, frequency_hz=freq)
    assert result["is_ac"] is True

    zc = 1 / (1j * omega * C)
    expected_v2 = 10 * zc / (1000 + zc)
    assert result["node_voltages"]["2"] == pytest.approx(expected_v2)


def test_zero_resistance_rejected():
    elements = [Element("V", "V1", "1", "0", 5), Element("R", "R1", "1", "0", 0)]
    with pytest.raises(CircuitError):
        solve_circuit(elements)


def test_inductor_without_ac_frequency_rejected():
    elements = [Element("V", "V1", "1", "0", 5), Element("L", "L1", "1", "0", 0.01)]
    with pytest.raises(CircuitError):
        solve_circuit(elements)  # frequency_hz defaults to 0 (DC)


def test_same_node_both_terminals_rejected():
    elements = [Element("R", "R1", "1", "1", 100)]
    with pytest.raises(CircuitError):
        solve_circuit(elements)


def test_empty_circuit_rejected():
    with pytest.raises(CircuitError):
        solve_circuit([])


def test_floating_circuit_has_no_unique_solution():
    # Two nodes tied together by a resistor, but nothing ties either to
    # ground — no unique node-voltage solution exists.
    elements = [Element("R", "R1", "1", "2", 100)]
    with pytest.raises(CircuitError):
        solve_circuit(elements)
