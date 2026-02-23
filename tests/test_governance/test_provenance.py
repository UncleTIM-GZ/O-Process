"""Tests for ProvenanceChain and ProvenanceNode."""

from __future__ import annotations

from oprocess.governance.provenance import ProvenanceChain, ProvenanceNode


class TestProvenanceNode:
    def test_to_dict(self):
        node = ProvenanceNode(
            node_id="8.5",
            name="管理 AI 智能运维",
            confidence=0.92,
            path="8.0 > 8.5",
            derivation_rule="semantic_match",
        )
        d = node.to_dict()
        assert d["node_id"] == "8.5"
        assert d["name"] == "管理 AI 智能运维"
        assert d["confidence"] == 0.92
        assert d["path"] == "8.0 > 8.5"
        assert d["derivation_rule"] == "semantic_match"

    def test_all_fields_present(self):
        node = ProvenanceNode(
            node_id="1.0", name="n", confidence=1.0,
            path="1.0", derivation_rule="direct_lookup",
        )
        d = node.to_dict()
        expected_keys = {
            "node_id", "name", "confidence", "path", "derivation_rule",
        }
        assert set(d.keys()) == expected_keys


class TestProvenanceChain:
    def test_add_and_export(self):
        chain = ProvenanceChain()
        chain.add("1.0", "制定愿景", 1.0, "1.0", "direct_lookup")
        chain.add("1.1", "定义概念", 0.8, "1.0 > 1.1", "semantic_match")

        assert len(chain) == 2
        entries = chain.to_list()
        assert entries[0]["node_id"] == "1.0"
        assert entries[0]["derivation_rule"] == "direct_lookup"
        assert entries[1]["node_id"] == "1.1"
        assert entries[1]["confidence"] == 0.8

    def test_node_ids(self):
        chain = ProvenanceChain()
        chain.add("4.4.3", "运输配送", 0.92, "4.0 > 4.4 > 4.4.3", "semantic_match")
        chain.add("4.4", "供应链", 0.5, "4.0 > 4.4", "rule_based")
        assert chain.node_ids() == ["4.4.3", "4.4"]

    def test_empty_chain(self):
        chain = ProvenanceChain()
        assert len(chain) == 0
        assert chain.to_list() == []
        assert chain.node_ids() == []

    def test_to_list_returns_dicts(self):
        chain = ProvenanceChain()
        chain.add("1.0", "test", 1.0, "1.0", "direct_lookup")
        result = chain.to_list()
        assert isinstance(result, list)
        assert isinstance(result[0], dict)
