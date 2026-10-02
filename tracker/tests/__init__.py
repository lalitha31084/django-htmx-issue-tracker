"""Test suite for the tracker app.

The suite is deliberately split along the two axes of this project:

``test_standard_requests``
    Everything a browser does with JavaScript **disabled**: full pages (200) and
    redirects (302).

``test_enhanced_requests``
    The same endpoints driven by an enhancement layer, simulated by sending the
    ``HX-Request: true`` header. These must answer with small HTML fragments
    that contain no ``<html>``/``<body>`` tags.

``test_models`` / ``test_forms`` / ``test_views_extra``
    Unit level coverage of the domain rules and the extra endpoints.
"""