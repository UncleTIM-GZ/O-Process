"""Tests for ProvenanceChain."""

from __future__ import annotations

from oprocess.governance.provenance import ProvenanceChain, ProvenanceEntry


class TestProvenanceChain:
    def test_add_and_export(self):
        chain = ProvenanceChain()
        chain.add("1.0", "queried", "root lookup")
        chain.add("1.1", "matched", "child match")

        assert len(chain) == 2
        entries = chain.to_list()
        assert entries[0]["node_id"] == "1.0"
        assert entries[0]["action"] == "queried"
        assert entries[1]["node_id"] == "1.1"

    def test_node_ids(self):
        chain = ProvenanceChain()
        chain.add("4.4.3", "queried")
        chain.add("4.4", "derived")
        assert chain.node_ids() == ["4.4.3", "4.4"]

    def test_empty_chain(self):
        chain = ProvenanceChain()
        assert len(chain) == 0
        assert chain.to_list() == []


class TestProvenanceEntry:
    def test_to_dict(self):
        entry = ProvenanceEntry(
            node_id="8.5", action="matched", details="AI ops"
        )
        d = entry.to_dict()
        assert d["node_id"] == "8.5"
        assert d["action"] == "matched"
        assert "timestamp" in d
