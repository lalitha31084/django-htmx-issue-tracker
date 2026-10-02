"""Canonical demo data used by the seeding migration and the management command.

Kept in one place (and free of Django imports) so both the migration and
``manage.py seed_demo_data`` always produce identical data.
"""

SEED_PROJECTS = [
    {
        "name": "Orbit CMS",
        "description": (
            "A customer facing content management system. This project tracks the "
            "work planned for the 2.4 release: templating improvements, an "
            "accessibility audit and a batch of performance fixes."
        ),
        "issues": [
            {
                "title": "Add support for custom field types",
                "description": (
                    "Integrators need to register their own field types instead of "
                    "forking the field registry. Expose a FieldTypeRegistry with a "
                    "register() API and document the migration path."
                ),
                "status": "To Do",
                "comments": [
                    "Confirmed with the platform team - the registry work lands before the 2.4 freeze.",
                    "Docs will live in a new 'custom fields' chapter.",
                ],
            },
            {
                "title": "Editor toolbar overlaps on small screens",
                "description": (
                    "Below 480px the sticky editor toolbar covers the first paragraph. "
                    "Reproduce by opening an article on an iPhone SE in landscape mode."
                ),
                "status": "In Progress",
                "comments": [
                    "Root cause is a hard-coded min-height on the toolbar container.",
                ],
            },
            {
                "title": "Speed up the /api/v2/articles endpoint",
                "description": (
                    "p99 latency is 1.8s for projects with more than 5k articles. "
                    "Add composite indexes and drop the N+1 permission lookups."
                ),
                "status": "In Progress",
                "comments": [],
            },
            {
                "title": "Replace deprecated ugettext calls",
                "description": (
                    "Run the deprecation shim over the whole codebase and delete the "
                    "compatibility layer once the last call site is gone."
                ),
                "status": "Done",
                "comments": [
                    "Removed 214 call sites across 38 templates.",
                ],
            },
            {
                "title": "Document the content migration workflow",
                "description": (
                    "Write a guide covering the export format, the import wizard and "
                    "the rollback procedure."
                ),
                "status": "Done",
                "comments": [],
            },
        ],
    },
    {
        "name": "Pulse Analytics",
        "description": (
            "Real-time analytics dashboard for product teams. The current sprint "
            "focuses on the reporting pipeline and on making the widgets accessible."
        ),
        "issues": [
            {
                "title": "Aggregate events in a background worker",
                "description": (
                    "Aggregation currently runs inside the request/response cycle and "
                    "dominates p95 latency. Move it to a Celery task with idempotent "
                    "reprocessing."
                ),
                "status": "To Do",
                "comments": [
                    "Needs a decision on the storage format for pre-aggregated buckets.",
                ],
            },
            {
                "title": "Keyboard navigation for the widget grid",
                "description": (
                    "Widgets must be reachable and reorderable with the keyboard alone. "
                    "Add roving tabindex and announce moves to screen readers."
                ),
                "status": "To Do",
                "comments": [],
            },
            {
                "title": "Fix timezone drift in weekly rollups",
                "description": (
                    "Weeks that straddle a daylight-saving change are bucketed twice. "
                    "Normalise every event to UTC before bucketing."
                ),
                "status": "In Progress",
                "comments": [
                    "Reproduced with Europe/Berlin across the October DST boundary.",
                ],
            },
            {
                "title": "Add CSV export to every report",
                "description": (
                    "Expose a CSV download action on each report view, respecting the "
                    "current filter and column selection."
                ),
                "status": "Done",
                "comments": [],
            },
        ],
    },
    {
        "name": "Beacon Design System",
        "description": (
            "Shared component library: design tokens, accessible primitives and the "
            "documentation site that consumes them."
        ),
        "issues": [
            {
                "title": "Publish the colour token package",
                "description": (
                    "Export the palette as a versioned JSON/JS package with automated "
                    "contrast checks for WCAG AA."
                ),
                "status": "To Do",
                "comments": [],
            },
            {
                "title": "Migrate buttons to the new focus ring",
                "description": (
                    "The current focus ring fails WCAG 2.2 focus appearance on coloured "
                    "backgrounds. Replace it with the tokenised ring across the library."
                ),
                "status": "In Progress",
                "comments": [
                    "Contrast ratio improved from 2.1:1 to 4.8:1 on the primary hue.",
                    "Still to do: icon-only button variant.",
                ],
            },
            {
                "title": "Upgrade the documentation site to the 2.0 template",
                "description": (
                    "Adopt the new layout, enable the search index and retire the legacy "
                    "sidebar implementation."
                ),
                "status": "Done",
                "comments": [
                    "Search index now covers 96% of the component reference pages.",
                ],
            },
        ],
    },
]