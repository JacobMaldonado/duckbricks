"""Layout rules for the full-height workspace editor."""

WORKSPACE_VIEWPORT_STYLE = "height: calc(100vh - 64px)"

WORKSPACE_CODEMIRROR_LAYOUT_CSS = """
.ws-editor {
    min-width: 0 !important;
    min-height: 0 !important;
}
.ws-codemirror-panel {
    flex: 1 1 0% !important;
    width: 100% !important;
    min-height: 0 !important;
    display: flex !important;
    flex-direction: column !important;
    overflow: visible !important;
}
.ws-editor .nicegui-codemirror {
    flex: 1 1 0% !important;
    width: 100% !important;
    height: 100% !important;
    min-height: 0 !important;
    display: flex !important;
    flex-direction: column !important;
}
.ws-editor .cm-editor {
    flex: 1 1 0% !important;
    width: 100% !important;
    height: 100% !important;
    min-height: 0 !important;
}
.ws-editor .cm-scroller {
    height: 100% !important;
    min-height: 0 !important;
    overflow: auto !important;
}
"""
