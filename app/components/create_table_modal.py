"""Create Table Modal Component."""
from nicegui import ui

from app.services.ducklake import manager


class ColumnDefinition:
    """Represents a column definition in the create table form."""

    def __init__(
        self,
        name: str = "",
        data_type: str = "VARCHAR",
        is_nullable: bool = True,
        comment: str = "",
    ):
        self.name = name
        self.data_type = data_type
        self.is_nullable = is_nullable
        self.comment = comment


async def show_create_table_dialog(
    catalog: str, schema: str, on_success: callable | None = None
):
    """Show the create table modal dialog.

    Args:
        catalog: Catalog name where table will be created
        schema: Schema name where table will be created
        on_success: Callback function to call after successful table creation
    """
    # Initial column definitions
    columns = [
        ColumnDefinition("id", "BIGINT", False, "Primary key"),
        ColumnDefinition("created_at", "TIMESTAMP", False, "Creation timestamp"),
    ]

    # Data type options
    DATA_TYPES = [
        "VARCHAR",
        "INTEGER",
        "BIGINT",
        "DOUBLE",
        "BOOLEAN",
        "DATE",
        "TIMESTAMP",
        "JSON",
    ]

    with ui.dialog() as dialog, ui.card().classes("w-full").style(
        "min-width: 800px; max-width: 900px"
    ):
        # Dialog header
        with ui.row().classes("w-full items-center justify-between q-pb-md").style(
            "border-bottom: 1px solid #E5E5E5"
        ):
            with ui.row().classes("items-center gap-2"):
                ui.icon("table_chart", size="24px").classes("text-primary")
                ui.label("Create New Table").classes("text-h6 text-weight-medium")
            ui.button(icon="close", on_click=dialog.close).props("flat round dense")

        # Dialog body (scrollable)
        with ui.scroll_area().classes("w-full").style(
            "max-height: calc(80vh - 180px)"
        ):
            with ui.column().classes("w-full gap-4 q-py-md"):
                # Schema context
                with ui.card().classes("bg-grey-1"):
                    with ui.row().classes("items-center gap-2 q-pa-sm"):
                        ui.icon("storage", size="20px").classes("text-grey-7")
                        ui.label("Catalog:").classes("text-caption text-grey-7")
                        ui.label(catalog).classes("text-caption text-weight-medium")
                        ui.label("›").classes("text-caption text-grey-5")
                        ui.icon("folder", size="20px").classes("text-grey-7")
                        ui.label("Schema:").classes("text-caption text-grey-7")
                        ui.label(schema).classes("text-caption text-weight-medium")

                # Table name and description
                ui.label("Table Name *").classes("text-body2 text-weight-medium")
                table_name_input = ui.input(
                    placeholder="e.g., users, orders, events"
                ).props("outlined dense").classes("w-full")
                ui.label("Use lowercase letters, numbers, and underscores only").classes(
                    "text-caption text-grey-7 q-mt-n3"
                )

                ui.label("Description (optional)").classes(
                    "text-body2 text-weight-medium q-mt-sm"
                )
                description_input = ui.textarea(
                    placeholder="Brief description of this table..."
                ).props("outlined").classes("w-full").style("min-height: 60px")

                # Column definitions section
                with ui.row().classes("w-full items-center justify-between q-mt-md q-mb-sm"):
                    ui.label("Column Definitions *").classes(
                        "text-body2 text-weight-medium"
                    )

                # Column headers
                with ui.row().classes("w-full items-center gap-2 q-px-sm q-pb-xs").style(
                    "border-bottom: 2px solid #E5E5E5"
                ):
                    ui.label("Column Name").classes(
                        "flex-1 text-caption text-weight-medium text-grey-7"
                    )
                    ui.label("Data Type").classes(
                        "w-32 text-caption text-weight-medium text-grey-7"
                    )
                    ui.label("Nullable").style("width: 100px").classes(
                        "text-caption text-weight-medium text-grey-7"
                    )
                    ui.label("Comment").classes(
                        "flex-1 text-caption text-weight-medium text-grey-7"
                    )
                    ui.label("").style("width: 40px")  # Action spacer

                # Column rows container
                column_rows_container = ui.column().classes("w-full gap-2 q-mt-sm")

                def create_column_row(col_def: ColumnDefinition):
                    """Create a column definition row."""
                    with ui.row().classes("w-full items-center gap-2 q-pa-sm bg-grey-1").style(
                        "border-radius: 4px"
                    ) as row:
                        # Column name
                        name_input = ui.input(
                            placeholder="column_name", value=col_def.name
                        ).props("outlined dense").classes("flex-1")
                        name_input.on("update:model-value", lambda e: setattr(col_def, "name", e.args.lower()))

                        # Data type
                        type_select = ui.select(
                            options=DATA_TYPES, value=col_def.data_type
                        ).props("outlined dense").classes("w-32")
                        type_select.on("update:model-value", lambda e: setattr(col_def, "data_type", e.args))

                        # Nullable checkbox
                        with ui.row().classes("items-center gap-1").style("width: 100px"):
                            nullable_checkbox = ui.checkbox(value=col_def.is_nullable)
                            nullable_checkbox.on("update:model-value", lambda e: setattr(col_def, "is_nullable", e.args))
                            ui.label("Nullable").classes("text-caption")

                        # Comment
                        comment_input = ui.input(
                            placeholder="Comment (optional)", value=col_def.comment
                        ).props("outlined dense").classes("flex-1")
                        comment_input.on("update:model-value", lambda e: setattr(col_def, "comment", e.args))

                        # Remove button
                        def remove_row():
                            columns.remove(col_def)
                            row.delete()

                        ui.button(icon="delete", on_click=remove_row).props(
                            "flat round dense color=negative"
                        )

                def render_columns():
                    """Render all column rows."""
                    column_rows_container.clear()
                    with column_rows_container:
                        for col_def in columns:
                            create_column_row(col_def)

                render_columns()

                # Add column button
                def add_column():
                    columns.append(ColumnDefinition())
                    render_columns()

                ui.button("Add Column", icon="add", on_click=add_column).props(
                    "flat dense color=primary"
                )

                # Info callout
                with ui.card().classes("bg-blue-1 q-mt-md").style(
                    "border-left: 3px solid #0066CC"
                ):
                    with ui.row().classes("items-start gap-2 q-pa-sm"):
                        ui.icon("info", size="20px").classes("text-primary q-mt-1")
                        with ui.column().classes("flex-grow"):
                            ui.label("Table Creation Tips").classes(
                                "text-caption text-weight-medium"
                            )
                            ui.label(
                                "• At least one column is required\n"
                                "• Column names must be lowercase alphanumeric with underscores\n"
                                "• Consider adding a primary key for better performance\n"
                                "• Nullable columns can contain NULL values"
                            ).classes("text-caption text-grey-8").style(
                                "white-space: pre-line"
                            )

        # Status message
        status_label = ui.label("").classes("text-caption")

        # Dialog footer
        with ui.row().classes("w-full justify-end items-center q-pt-md q-mt-md").style(
            "border-top: 1px solid #E5E5E5"
        ):
            # Actions
            with ui.row().classes("gap-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                
                async def handle_create():
                    """Handle table creation."""
                    # Clear previous status
                    status_label.set_text("")

                    # Validate table name
                    table_name = table_name_input.value.strip()
                    if not table_name:
                        status_label.set_text("❌ Table name is required")
                        status_label.classes("text-negative")
                        return

                    # Validate columns
                    if not columns:
                        status_label.set_text("❌ At least one column is required")
                        status_label.classes("text-negative")
                        return

                    # Build column definitions
                    column_defs = []
                    for col in columns:
                        if not col.name.strip():
                            status_label.set_text("❌ All columns must have names")
                            status_label.classes("text-negative")
                            return
                        column_defs.append(
                            {
                                "name": col.name.strip(),
                                "data_type": col.data_type,
                                "is_nullable": col.is_nullable,
                                "comment": col.comment.strip() if col.comment else None,
                            }
                        )

                    # Create table
                    try:
                        result = manager.create_table(
                            catalog=catalog,
                            schema=schema,
                            table_name=table_name,
                            columns=column_defs,
                            description=description_input.value.strip()
                            if description_input.value
                            else None,
                        )

                        if result["success"]:
                            status_label.set_text(
                                f"✅ {result.get('message', 'Table created successfully')}"
                            )
                            status_label.classes("text-positive")
                            
                            # Call success callback if provided
                            if on_success:
                                await on_success()
                            
                            # Close dialog after a short delay
                            ui.timer(1.5, dialog.close, once=True)
                        else:
                            status_label.set_text(f"❌ {result.get('error', 'Failed to create table')}")
                            status_label.classes("text-negative")
                    except Exception as e:
                        status_label.set_text(f"❌ Error: {str(e)}")
                        status_label.classes("text-negative")

                create_button = ui.button("Create Table", icon="add", on_click=handle_create).classes(
                    "bg-primary text-white"
                )

    dialog.open()
