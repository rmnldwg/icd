"""
Test the base classes from which the different revisions inherit the core
functionality.
"""
import hypothesis
import hypothesis.strategies as st
import pytest
from hypothesis import assume, given

import icd
from icd.base import ICDBlock, ICDCategory, ICDChapter, ICDEntry, ICDRoot


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

# pylint: disable=no-method-argument
# pylint: disable=no-self-argument
@st.composite
def st_entry(draw, kind=None):
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
def st_root(draw):
    """
    Hypothesis strategy for generating `ICDEntry` instances.
    """
    code = draw(st.text())
    title = draw(st.text())
    release = draw(st.text())
    return ICDRoot(code, title, release)

@st.composite
def st_linear_codex(draw, entry=st_entry(), root=st_root()):
    """Strategy for a linear codex."""
    chain = draw(st.lists(entry, min_size=2))
    for i, element in enumerate(chain):
        if i != 0:
            chain[i-1].add_child(element)
    root = draw(root)
    root.add_child(chain[0])
    return root

@st.composite
def st_tree_codex(
    draw,
    linear_codex_list=st.lists(st_linear_codex(), min_size=2, max_size=10),
    root=st_root()
):
    """Strategy for generating a tree-like codex."""
    entry_list = [draw(root)]
    for lin_cod in draw(linear_codex_list):
        branch_point = draw(st.sampled_from(entry_list))
        branch_point.add_child(lin_cod)
        entry_list = [*entry_list, *list(lin_cod.entries)]

    return entry_list[0]


class TestICDEntry:
    """
    Test the base implementation `icd.base.ICDEntry` from which all other
    classes inherit.
    """
    @given(
        code=st.text(),
        title=st.text(),
        kind=st.one_of(
            st.sampled_from(["root", "chapter", "block", "category"]),
            st.text()
        ),
        parent=st.one_of(st_entry(), st.none()),
        children=st.lists(st_entry())
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


    @given(entry=st_entry())
    def test___str__(self, entry):
        """Test string representation."""
        assert str(entry) == f"{entry.kind} {entry.code}: {entry.title}"


    @given(entry=st_entry())
    def test___len__(self, entry):
        """Test built in length."""
        assert len(entry) == 1 + len(entry.children)


    @given(
        linear_codex=st_linear_codex(),
        release=st.text()
    )
    def test_release(self, linear_codex, release):
        """Check that the release of the root is returned."""
        # pylint: disable=protected-access
        root = linear_codex.root
        leaf = next(linear_codex.leaves)

        assert root.is_root
        root._release = release

        assert leaf.release == release

        with pytest.raises(AttributeError):
            leaf.release = "changed"


    @given(
        entry=st_entry(),
        parent=st_entry(),
    )
    def test_is_st_root(self, entry, parent):
        """Assert that `is_root` property works."""
        assert entry.is_root
        assert parent.is_root
        parent.add_child(entry)
        assert parent.is_root
        assert not entry.is_root


    @given(
        linear_codex=st_linear_codex()
    )
    def test_st_root(self, linear_codex):
        """Test if correct root is returned."""
        root = linear_codex.root

        for entry in root.entries:
            assert entry.root == root


    @given(
        entry=st_entry(),
        chapter=st_entry(kind="chapter")
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
        entry=st_entry(),
        block=st_entry(kind="block")
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


    @given(linear_codex=st_linear_codex())
    def test_depth(self, linear_codex):
        """Test computation of `depth`."""
        for i, entry in enumerate(linear_codex.entries):
            assert entry.depth - i == 1


    @given(
        entry=st_entry(),
        children=st.lists(st_entry(), min_size=1)
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
        entry=st_entry(),
        children=st.lists(st_entry(), min_size=1)
    )
    def test_leaves(self, entry, children):
        """Check `leaves` property returns all leaf entries."""
        for child in children:
            entry.add_child(child)

        assert children == list(entry.leaves)


    @given(
        linear_codex=st_linear_codex(),
        children=st.lists(st_entry(), min_size=1)
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


    @given(linear_codex=st_linear_codex())
    def test_depth_in_kind(self, linear_codex):
        """Test if `depth_in_kind` is computed correctly."""
        depth_in_kind_list = [
            entry.depth_in_kind for entry in linear_codex.entries
        ]
        kind_list = [entry.kind for entry in linear_codex.entries]
        kind_seq_count = count_identical_seq(kind_list)

        assert kind_seq_count == depth_in_kind_list


    @given(
        entry=st_entry(),
        children=st.lists(st_entry(), min_size=1)
    )
    def test__child_dict(self, entry, children):
        """Check the dictionary of children."""
        # pylint: disable=protected-access
        child_codes = [child.code for child in children]
        assume(len(set(child_codes)) == len(child_codes))
        for child in children:
            entry.add_child(child)
        child_dict = entry._child_dict()
        assert all(child_dict[child.code] == child for child in children)


    @given(linear_codex=st_linear_codex())
    def test_tree_and_ancestry(self, linear_codex):
        """
        Make sure that for a linear codex the `ancestry` and `tree`
        functions return the same string.
        """
        root = linear_codex
        leaf = next(root.leaves)
        assert root.tree() == leaf.ancestry()


    @given(
        entry=st_entry(),
        other_entry=st_entry(),
        new_child=st_entry(),
    )
    def test_add_and_remove_child(self, entry, other_entry, new_child):
        """Assert that the `add_child` method is as consistent as planned."""
        other_entry.add_child(new_child)
        entry.add_child(new_child)
        assert new_child in entry.children
        assert new_child not in other_entry.children
        assert new_child.parent == entry

        entry.add_child(new_child)
        assert len(entry.children) == 1

        entry.remove_child(new_child)
        assert len(entry.children) == 0
        assert new_child not in entry.children
        assert new_child.parent is None


    @given(
        entry=st_entry(),
    )
    def test_code_matches(self, entry):
        """Test the code-matching works"""
        code = entry.code
        dotless_code = code.replace('.', '')
        assert entry.code_matches(code) and entry.code_matches(dotless_code)


    @given(
        tree_codex=st_tree_codex(),
        maxdepth=st.integers(min_value=0, max_value=100)
    )
    def test_search_exists_and_get(self, tree_codex, maxdepth):
        """Make sure the `search` method finds existing codes in a tree."""
        for entry in tree_codex.entries:
            code = entry.code
            dotless_code = code.replace('.', '')
            if maxdepth <= entry.depth:
                assert entry not in tree_codex.search(code, maxdepth=maxdepth)
                assert tree_codex.get(code, maxdepth, entry.kind) is not entry
            else:
                assert (
                    tree_codex.exists(code, maxdepth=maxdepth) and
                    tree_codex.exists(dotless_code, maxdepth=maxdepth)
                )
                assert entry in tree_codex.search(code, maxdepth=maxdepth)


class TestICDRoot:
    """Test the base implementation `icd.base.ICDRoot`."""
    @given(
        code=st.text(),
        title=st.text(),
        release=st.text(),
        children=st.lists(st_entry(kind="chapter"))
    )
    def test___init__(self, code, title, release, children):
        """Test constructor"""
        root = ICDRoot(code, title, release)
        for child in children:
            root.add_child(child)
        child_dict = {child.code: child for child in children}

        assert root.code == code
        assert root.title == title
        assert root.kind == "root"
        assert root.release == release
        assert root.chapters == child_dict


class TestICDChapter:
    """Test the base implementation `icd.base.ICDChapter`."""
    @given(
        code=st.integers(min_value=1, max_value=3400),
        title=st.text(),
        children=st.lists(st_entry(kind="block"))
    )
    def test___init__(self, code, title, children):
        """Test constructor"""
        chapter = ICDChapter(code, title)
        for child in children:
            chapter.add_child(child)
        child_dict = {child.code: child for child in children}

        assert chapter.code == code
        assert chapter.title == title
        assert chapter.kind == "chapter"
        assert chapter.blocks == child_dict

    @pytest.mark.parametrize(
        ["number", "roman_numeral"],
        [
            (1, 'I'),
            (3, 'III'),
            (4, 'IV'),
            (13, 'XIII'),
            (45, 'XLV'),
            (78, 'LXXVIII'),
            (173, 'CLXXIII'),
            (2821, 'MMDCCCXXI'),
        ]
    )
    def test_romanize(self, number, roman_numeral):
        """Make sure the romanization is correct."""
        assert ICDChapter.romanize(number) == roman_numeral


class TestICDBlock:
    """Test the base implementation `icd.base.ICDBlock`."""
    @given(
        code=st.integers(min_value=1, max_value=3400),
        title=st.text(),
        children=st.lists(
            st.one_of(st_entry(kind="category"), st_entry(kind="block"))
        )
    )
    def test___init__(self, code, title, children):
        """Test constructor"""
        block = ICDBlock(code, title)
        for child in children:
            block.add_child(child)

        assert block.code == code
        assert block.title == title
        assert block.kind == "block"
        assert block.categories == {
            c.code: c for c in children if c.kind == "category"
        }
        assert block.blocks == {
            c.code: c for c in children if c.kind == "block"
        }


class TestICDCategory:
    """Test the base implementation `icd.base.ICDCategory`."""
    @given(
        code=st.integers(min_value=1, max_value=3400),
        title=st.text(),
        children=st.lists(st_entry(kind="category"))
    )
    def test___init__(self, code, title, children):
        """Test constructor"""
        category = ICDCategory(code, title)
        for child in children:
            category.add_child(child)

        assert category.code == code
        assert category.title == title
        assert category.kind == "category"
        assert category.categories == {
            c.code: c for c in children if c.kind == "category"
        }
