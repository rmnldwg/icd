"""
Test the base classes from which the different revisions inherit the core
functionality.
"""
import pytest

import hypothesis
import hypothesis.strategies as st
from hypothesis import given

import icd
from icd.base import ICDEntry, ICDRoot, ICDChapter, ICDBlock, ICDCategory


def count_identical_seq(raw_list):
    """
    Count for each element how many preceeding elements are identical
    """
    last = None
    res = [1] * len(raw_list)
    for i, element in enumerate(raw_list):
        if last is not None and last == element:
            count += 1
            res[i] = count
        else:
            count = 1
        last = element
    return res


class TestICDEntry:
    """
    Test the base implementation `icd.base.ICDEntry` from which all other
    classes inherit.
    """
    @st.composite
    def entry(draw, kind=None):  # pylint: disable=no-method-argument
        """
        Hypothesis strategy for generating `ICDEntry` instances.
        """
        code = draw(st.text())
        title = draw(st.text())

        valid_kinds = ["root", "chapter", "block", "category"]
        if kind is None:
            kind = draw(st.sampled_from(valid_kinds))
        return ICDEntry(code, title, kind)

    @st.composite
    def root(draw):  # pylint: disable=no-method-argument
        """
        Hypothesis strategy for generating `ICDEntry` instances.
        """
        code = draw(st.text())
        title = draw(st.text())
        release = draw(st.text())
        return ICDRoot(code, title, release)

    @st.composite
    def linear_codex(draw, entry=entry(), root=root()):
        """Strategy for a linear codex."""
        chain = draw(st.lists(entry, min_size=1))
        for i, element in enumerate(chain):
            if i != 0:
                chain[i-1].add_child(element)
        root = draw(root)
        root.add_child(chain[0])
        return root


    @given(
        code=st.text(),
        title=st.text(),
        kind=st.one_of(
            st.sampled_from(["root", "chapter", "block", "category"]),
            st.text()
        ),
        parent=st.one_of(entry(), st.none()),
        children=st.lists(entry())
    )
    def test___init__(self, code, title, kind, parent, children):
        """Test constructor"""
        if kind not in ["root", "chapter", "block", "category"]:
            with pytest.raises(ValueError):
                instance = ICDEntry(code, title, kind, parent, children)
        else:
            with pytest.raises(TypeError):
                instance = ICDEntry(code, title, kind, "not-an-entry", children)

            instance = ICDEntry(code, title, kind, parent, children)

            assert instance.code == code
            assert instance.title == title
            assert instance.kind == kind

            if parent is not None:
                assert instance.parent == parent
                assert instance in parent.children

            assert all(child in instance.children for child in children)
            assert all(instance == child.parent for child in children)


    @given(entry=entry())
    def test___str__(self, entry):
        """Test string representation."""
        assert str(entry) == f"{entry.kind} {entry.code}: {entry.title}"


    @given(entry=entry())
    def test___len__(self, entry):
        """Test built in length."""
        assert len(entry) == 1 + len(entry.children)


    @given(
        linear_codex=linear_codex(),
        release=st.text()
    )
    def test_release(self, linear_codex, release):
        """Check that the release of the root is returned."""
        root = linear_codex.root
        leaf = next(linear_codex.leaves)

        assert root.is_root
        root._release = release  # pylint: disable=protected-access

        assert leaf.release == release

        with pytest.raises(AttributeError):
            leaf.release = "changed"


    @given(
        entry=entry(),
        parent=entry(),
    )
    def test_is_root(self, entry, parent):
        """Assert that `is_root` property works."""
        assert entry.is_root
        assert parent.is_root
        parent.add_child(entry)
        assert parent.is_root
        assert not entry.is_root


    @given(
        linear_codex=linear_codex()
    )
    def test_root(self, linear_codex):
        """Test if correct root is returned."""
        root = linear_codex.root

        for entry in root.entries:
            assert entry.root == root


    @given(
        entry=entry(),
        chapter=entry(kind="chapter")
    )
    def test_chapter(self, entry, chapter):
        """Make sure `chapter` returns correct entry."""
        if entry.kind == "root":
            with pytest.raises(AttributeError):
                chapter = entry.chapter
        elif entry.kind == "chapter":
            assert entry.chapter == entry
        else:
            chapter.add_child(entry)
            assert chapter.chapter == chapter
            assert entry.chapter == chapter


    @given(
        entry=entry(),
        block=entry(kind="block")
    )
    def test_block(self, entry, block):
        """Test `block` property."""
        if entry.kind in ["root", "chapter"]:
            with pytest.raises(AttributeError):
                block = entry.block
        elif entry.kind == "block":
            assert entry.block == entry
        else:
            block.add_child(entry)
            assert block.block == block
            assert entry.block == block


    @given(linear_codex=linear_codex())
    def test_depth(self, linear_codex):
        """Test computation of `depth`."""
        for i, entry in enumerate(linear_codex.entries):
            assert entry.depth - i == 1


    @given(
        entry=entry(),
        children=st.lists(entry(), min_size=1)
    )
    def test_is_leaf(self, entry, children):
        """Test if `is_leaf` works correctly."""
        assert entry.is_leaf
        for child in children:
            assert child.is_leaf
            entry.add_child(child)
            assert child.is_leaf
        assert not entry.is_leaf


    @given(
        entry=entry(),
        children=st.lists(entry(), min_size=1)
    )
    def test_leaves(self, entry, children):
        """Check `leaves` property returns all leaf entries."""
        for child in children:
            entry.add_child(child)

        assert children == list(entry.leaves)


    @given(
        linear_codex=linear_codex(),
        children=st.lists(entry(), min_size=1)
    )
    def test_entries(self, linear_codex, children):
        """Check `leaves` property returns all leaf entries."""
        root = linear_codex.root
        entry_list = [root]
        while not entry_list[-1].is_leaf:
            entry_list = [*entry_list, *entry_list[-1].children]
        entry_list = [*entry_list, *children]

        entry = next(linear_codex.leaves)
        for child in children:
            entry.add_child(child)

        assert entry_list == list(root.entries)


    @given(linear_codex=linear_codex())
    def test_depth_in_kind(self, linear_codex):
        """Test if `depth_in_kind` is computed correctly."""
        depth_in_kind_list = [
            entry.depth_in_kind for entry in linear_codex.entries
        ]
        kind_list = [entry.kind for entry in linear_codex.entries]
        kind_seq_count = count_identical_seq(kind_list)

        assert kind_seq_count == depth_in_kind_list
