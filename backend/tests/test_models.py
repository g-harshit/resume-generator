from sqlmodel import SQLModel


def test_everything_a_user_owns_is_deleted_with_them():
    """A foreign key to users without ON DELETE CASCADE makes deleting that user fail
    (or leaves their data behind). Every new table with a user_id must cascade."""
    missing = [
        f"{table.name}.{fk.parent.name}"
        for table in SQLModel.metadata.tables.values()
        for fk in table.foreign_keys
        if fk.column.table.name == "users" and fk.ondelete != "CASCADE"
    ]
    assert not missing, f"Foreign keys to users without ON DELETE CASCADE: {missing}"
