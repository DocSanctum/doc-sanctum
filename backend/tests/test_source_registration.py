from __future__ import annotations

import backend.app.api.sources as sources_module
import pytest
from fastapi import HTTPException


@pytest.mark.parametrize("source_type", ["http", "localhost"])
def test_reject_disabled_source_type_raises_422(source_type):
    with pytest.raises(HTTPException) as exc_info:
        sources_module._reject_disabled_source_type(source_type)
    assert exc_info.value.status_code == 422


@pytest.mark.parametrize("source_type", ["local", "github"])
def test_reject_disabled_source_type_allows_active_types(source_type):
    sources_module._reject_disabled_source_type(source_type)  # must not raise
