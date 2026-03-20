"""Catalogs List page - Card-based catalog management view."""
from nicegui import ui

from app.components.layout import layout_frame
from app.services.ducklake import manager


def _render_catalog_card(catalog_details: dict, on_click_handler):
    """Render a single catalog card."""
    name = catalog_details["name"]
    schema_count = catalog_details.get("schema_count", 0)
    
    with ui.card().classes("w-full cursor-pointer hover:shadow-lg transition-shadow").on(
        "click", lambda: on_click_handler(name)
    ):
        with ui.row().classes("w-full items-center"):
            # Icon
            ui.icon("storage", size="32px").classes("text-primary")
            
            # Content
            with ui.column().classes("flex-grow q-ml-md"):
                ui.label(name).classes("text-h6 text-weight-medium")
                with ui.row().classes("items-center gap-2"):
                    ui.icon("folder", size="16px").classes("text-grey-6")
                    ui.label(f"{schema_count} schema{'s' if schema_count != 1 else ''}").classes(
                        "text-caption text-grey-7"
                    )
            
            # Action icon
            ui.icon("chevron_right", size="24px").classes("text-grey-5")


def catalogs_page():
    """Render the Catalogs List page."""
    layout_frame()

    ui.query("body").style("overflow: hidden")
    ui.query(".nicegui-content").style(
        "height: calc(100vh - 64px); overflow-y: auto; background-color: #FAFAFA"
    )

    if not manager.is_initialized:
        with ui.column().classes("w-full h-full items-center justify-center q-pa-lg"):
            ui.label("Metastore is not initialized.").classes("text-subtitle1 text-warning")
            init_button = ui.button("Initialize Metastore", icon="play_arrow")
            status_label = ui.label("").classes("text-caption")

            async def do_init():
                try:
                    manager.initialize()
                    status_label.set_text("✅ Metastore initialized successfully!")
                    ui.navigate.to("/catalogs")
                except Exception as e:
                    status_label.set_text(f"❌ Error: {e}")

            init_button.on_click(do_init)
        return

    # Main content container
    with ui.column().classes("w-full max-w-screen-xl mx-auto q-pa-lg"):
        # Page header
        with ui.row().classes("w-full items-center justify-between q-mb-md"):
            with ui.column():
                ui.label("Catalogs").classes("text-h4 text-weight-bold")
                ui.label("Browse and manage your data catalogs").classes("text-body2 text-grey-7")
            
            # Action button
            create_btn = ui.button("Create Catalog", icon="add").classes("bg-primary text-white")

        # Search and filter bar
        search_container = ui.column().classes("w-full")
        with search_container:
            with ui.row().classes("w-full items-center gap-4 q-mb-md"):
                search_input = ui.input(placeholder="Search catalogs...").props(
                    'outlined dense prepend-inner-icon="search"'
                ).classes("flex-grow")

        # Stats cards
        stats_container = ui.row().classes("w-full gap-4 q-mb-lg")
        
        # Catalog grid
        ui.label("Your Catalogs").classes("text-h6 text-weight-medium q-mb-sm")
        catalogs_container = ui.column().classes("w-full gap-3")

        # Load data
        def refresh_page():
            """Refresh the catalogs list and stats."""
            stats_container.clear()
            catalogs_container.clear()

            # Get stats
            try:
                stats = manager.get_metastore_stats()
                
                with stats_container:
                    with ui.card().classes("flex-1"):
                        with ui.column().classes("q-pa-md"):
                            ui.label("Total Catalogs").classes("text-caption text-grey-7")
                            ui.label(str(stats["total_catalogs"])).classes(
                                "text-h4 text-weight-bold text-primary"
                            )
                    
                    with ui.card().classes("flex-1"):
                        with ui.column().classes("q-pa-md"):
                            ui.label("Total Schemas").classes("text-caption text-grey-7")
                            ui.label(str(stats["total_schemas"])).classes("text-h4 text-weight-bold")
                    
                    with ui.card().classes("flex-1"):
                        with ui.column().classes("q-pa-md"):
                            ui.label("Total Tables").classes("text-caption text-grey-7")
                            ui.label(str(stats["total_tables"])).classes("text-h4 text-weight-bold")

            except Exception as e:
                with stats_container:
                    ui.label(f"Error loading stats: {e}").classes("text-negative")

            # Get catalog list
            try:
                catalogs = manager.list_catalogs()
                search_term = search_input.value.lower() if hasattr(search_input, 'value') else ""

                filtered_catalogs = [c for c in catalogs if search_term in c.lower()]

                if not filtered_catalogs:
                    with catalogs_container:
                        with ui.card().classes("w-full"):
                            with ui.column().classes("items-center q-pa-xl"):
                                ui.icon("storage", size="64px").classes("text-grey-5")
                                ui.label("No catalogs found").classes("text-h6 text-grey-7 q-mt-md")
                                ui.label("Create your first catalog to get started").classes(
                                    "text-caption text-grey-6"
                                )
                else:
                    with catalogs_container:
                        for catalog in filtered_catalogs:
                            details = manager.get_catalog_details(catalog)
                            _render_catalog_card(
                                details,
                                lambda name: ui.navigate.to(f"/explorer?catalog={name}")
                            )

            except Exception as e:
                with catalogs_container:
                    ui.label(f"Error loading catalogs: {e}").classes("text-negative")

        # Wire up search
        search_input.on("input", lambda: refresh_page())

        # Wire up create catalog button
        def show_create_dialog():
            """Show create catalog dialog."""
            from app.pages.explorer import _show_create_catalog_dialog
            
            # Create a dummy container for refresh callback
            dummy_container = ui.column()
            
            # Custom refresh that updates this page instead
            original_show = _show_create_catalog_dialog
            
            # We'll just refresh the current page after creation
            dialog_catalog_name = ""
            dialog_description = ""
            dialog_storage_path = ""

            with ui.dialog() as dialog, ui.card().classes("w-full").style(
                "min-width: 500px; max-width: 600px"
            ):
                # Dialog header
                with ui.row().classes("w-full items-center justify-between q-pb-md").style(
                    "border-bottom: 1px solid #E5E5E5"
                ):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("storage", size="24px").classes("text-primary")
                        ui.label("Create New Catalog").classes("text-h6 text-weight-medium")
                    ui.button(icon="close", on_click=dialog.close).props("flat round dense")

                # Dialog body
                with ui.column().classes("w-full gap-4 q-py-md"):
                    ui.label("Catalog Name *").classes("text-body2 text-weight-medium")
                    name_input = ui.input(
                        placeholder="e.g., production, analytics, ml_models"
                    ).props('outlined dense').classes("w-full")
                    ui.label(
                        "Use lowercase letters, numbers, and underscores only"
                    ).classes("text-caption text-grey-7 q-mt-n3")

                    ui.label("Description (optional)").classes("text-body2 text-weight-medium q-mt-sm")
                    desc_input = ui.textarea(
                        placeholder="Brief description of this catalog's purpose..."
                    ).props('outlined').classes("w-full").style("min-height: 80px")

                    ui.label("Storage Location (optional)").classes(
                        "text-body2 text-weight-medium q-mt-sm"
                    )
                    path_input = ui.input(
                        placeholder="/data/catalogs/production"
                    ).props('outlined dense').classes("w-full")
                    ui.label(
                        "Defaults to system configuration if not specified"
                    ).classes("text-caption text-grey-7 q-mt-n3")

                    with ui.card().classes("bg-blue-1 q-mt-sm").style(
                        "border-left: 3px solid #0066CC"
                    ):
                        with ui.row().classes("items-start gap-2 q-pa-sm"):
                            ui.icon("info", size="20px").classes("text-primary q-mt-1")
                            with ui.column().classes("flex-grow"):
                                ui.label("Catalog Naming Guidelines").classes(
                                    "text-caption text-weight-medium"
                                )
                                ui.label(
                                    "• Must be unique across your metastore\n"
                                    "• Use descriptive names that indicate purpose\n"
                                    "• Cannot be renamed after creation"
                                ).classes("text-caption text-grey-8").style("white-space: pre-line")

                # Dialog footer
                with ui.row().classes("w-full justify-end gap-2 q-pt-md").style(
                    "border-top: 1px solid #E5E5E5"
                ):
                    ui.button("Cancel", on_click=dialog.close).props("flat")
                    create_dialog_btn = ui.button("Create Catalog", icon="add").classes(
                        "bg-primary text-white"
                    )

                async def handle_create():
                    name = name_input.value.strip()
                    if not name:
                        ui.notify("Catalog name is required", type="warning")
                        return

                    result = manager.create_catalog(
                        name=name,
                        description=desc_input.value.strip(),
                        storage_path=path_input.value.strip()
                    )

                    if result["success"]:
                        ui.notify(result["message"], type="positive")
                        dialog.close()
                        refresh_page()
                    else:
                        ui.notify(result["error"], type="negative")

                create_dialog_btn.on_click(handle_create)

            dialog.open()

        create_btn.on_click(show_create_dialog)

        # Initial load
        refresh_page()
