"""Tests for WorkspaceService CRUD operations."""

import pytest

from app.services.workspace.workspace_service import WorkspaceNode, WorkspaceService


@pytest.fixture
def workspace(tmp_path):
    return WorkspaceService(str(tmp_path))


class TestWorkspaceServiceReadWrite:
    def test_write_and_read_file(self, workspace):
        workspace.write_file("query.sql", "SELECT 1")
        assert workspace.read_file("query.sql") == "SELECT 1"

    def test_write_creates_parent_directories(self, workspace):
        workspace.write_file("folder/sub/script.py", "print('hi')")
        assert workspace.read_file("folder/sub/script.py") == "print('hi')"

    def test_read_raises_for_missing_file(self, workspace):
        with pytest.raises(FileNotFoundError):
            workspace.read_file("does_not_exist.sql")

    def test_write_raises_for_disallowed_extension(self, workspace):
        with pytest.raises(ValueError, match="not allowed"):
            workspace.write_file("evil.sh", "rm -rf /")


class TestWorkspaceServiceFolderOperations:
    def test_create_folder(self, workspace):
        workspace.create_folder("my_folder")
        assert (workspace.root / "my_folder").is_dir()

    def test_create_nested_folder(self, workspace):
        workspace.create_folder("a/b/c")
        assert (workspace.root / "a" / "b" / "c").is_dir()


class TestWorkspaceServiceDelete:
    def test_delete_file(self, workspace):
        workspace.write_file("to_delete.sql", "SELECT 1")
        workspace.delete("to_delete.sql")
        with pytest.raises(FileNotFoundError):
            workspace.read_file("to_delete.sql")

    def test_delete_folder_recursively(self, workspace):
        workspace.write_file("myfolder/a.sql", "SELECT 1")
        workspace.write_file("myfolder/b.sql", "SELECT 2")
        workspace.delete("myfolder")
        assert not (workspace.root / "myfolder").exists()

    def test_delete_raises_for_missing_path(self, workspace):
        with pytest.raises(FileNotFoundError):
            workspace.delete("ghost.sql")


class TestWorkspaceServiceTree:
    def test_list_tree_returns_files(self, workspace):
        workspace.write_file("a.sql", "")
        workspace.write_file("b.py", "")
        nodes = workspace.list_tree()
        names = {n.name for n in nodes}
        assert "a.sql" in names
        assert "b.py" in names

    def test_list_tree_nests_children_under_folder(self, workspace):
        workspace.write_file("folder/nested.sql", "")
        nodes = workspace.list_tree()
        folder_node = next((n for n in nodes if n.is_dir and n.name == "folder"), None)
        assert folder_node is not None
        assert any(c.name == "nested.sql" for c in folder_node.children)

    def test_list_tree_excludes_disallowed_extensions(self, workspace):
        workspace.create_folder("scripts")
        (workspace.root / "scripts" / "evil.sh").write_text("rm -rf /")
        nodes = workspace.list_tree()
        scripts_node = next((n for n in nodes if n.is_dir and n.name == "scripts"), None)
        if scripts_node:
            assert all(c.name != "evil.sh" for c in scripts_node.children)

    def test_list_files_filters_by_extension(self, workspace):
        workspace.write_file("query.sql", "")
        workspace.write_file("script.py", "")
        sql_files = workspace.list_files(extensions=["sql"])
        assert all(f.endswith(".sql") for f in sql_files)
        assert not any(f.endswith(".py") for f in sql_files)


class TestWorkspaceServiceSecurity:
    def test_traversal_attack_raises_value_error(self, workspace):
        with pytest.raises(ValueError, match="escapes the workspace root"):
            workspace.read_file("../../etc/passwd")


class TestWorkspaceServiceClone:
    def test_clone_file_creates_copy_in_same_folder(self, workspace):
        workspace.write_file("query.sql", "SELECT 1")
        cloned = workspace.clone("query.sql")
        assert cloned == "query_copy.sql"
        assert workspace.read_file(cloned) == "SELECT 1"

    def test_clone_file_avoids_name_collision(self, workspace):
        workspace.write_file("query.sql", "SELECT 1")
        workspace.clone("query.sql")
        second_clone = workspace.clone("query.sql")
        assert second_clone == "query_copy1.sql"

    def test_clone_directory_copies_all_contents(self, workspace):
        workspace.write_file("myfolder/a.sql", "SELECT 1")
        workspace.write_file("myfolder/b.py", "print(1)")
        workspace.clone("myfolder")
        assert workspace.read_file("myfolder_copy/a.sql") == "SELECT 1"
        assert workspace.read_file("myfolder_copy/b.py") == "print(1)"

    def test_clone_raises_for_missing_source(self, workspace):
        with pytest.raises(FileNotFoundError):
            workspace.clone("nonexistent.sql")


class TestWorkspaceServiceMove:
    def test_move_file_into_folder(self, workspace):
        workspace.write_file("query.sql", "SELECT 1")
        workspace.create_folder("archive")
        new_path = workspace.move("query.sql", "archive")
        assert new_path == "archive/query.sql"
        assert workspace.read_file("archive/query.sql") == "SELECT 1"

    def test_move_raises_for_missing_source(self, workspace):
        workspace.create_folder("archive")
        with pytest.raises(FileNotFoundError):
            workspace.move("ghost.sql", "archive")

    def test_move_raises_when_dest_is_not_a_directory(self, workspace):
        workspace.write_file("query.sql", "SELECT 1")
        workspace.write_file("other.sql", "SELECT 2")
        with pytest.raises(ValueError, match="not a directory"):
            workspace.move("query.sql", "other.sql")

    def test_move_raises_on_name_collision(self, workspace):
        workspace.write_file("query.sql", "SELECT 1")
        workspace.write_file("archive/query.sql", "SELECT 2")
        with pytest.raises(ValueError, match="already exists"):
            workspace.move("query.sql", "archive")
