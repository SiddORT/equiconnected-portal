"""
DB-level constraint tests for the Provider schema:
  - one thumbnail photo per provider (partial unique index)
  - one primary location per provider (partial unique index)
  - unique (provider_id, specialization_id) association
  - cascade delete of child rows
"""
import pytest
from sqlalchemy.exc import IntegrityError

from app.models.enums import ProviderType, VisitStability
from app.models.provider import (
    Provider,
    ProviderLocation,
    ProviderPhoto,
    ProviderSpecialization,
)
from app.models.specialization import Specialization


def _make_provider(db, name="Test Hospital"):
    p = Provider(
        provider_type=ProviderType.HOSPITAL,
        name=name,
        visit_stability=VisitStability.STABLE_VISIT,
    )
    db.add(p)
    db.commit()
    return p


def test_second_thumbnail_rejected(db):
    p = _make_provider(db)
    db.add(ProviderPhoto(provider_id=p.id, storage_reference="ref1", is_thumbnail=True))
    db.commit()
    db.add(ProviderPhoto(provider_id=p.id, storage_reference="ref2", is_thumbnail=True))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    # Non-thumbnail photos remain unlimited
    db.add(ProviderPhoto(provider_id=p.id, storage_reference="ref3", is_thumbnail=False))
    db.add(ProviderPhoto(provider_id=p.id, storage_reference="ref4", is_thumbnail=False))
    db.commit()


def test_second_primary_location_rejected(db):
    p = _make_provider(db)
    db.add(ProviderLocation(provider_id=p.id, address_line_1="1 Main St", city="Pune", is_primary=True))
    db.commit()
    db.add(ProviderLocation(provider_id=p.id, address_line_1="2 Main St", city="Pune", is_primary=True))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    # Non-primary locations remain unlimited
    db.add(ProviderLocation(provider_id=p.id, address_line_1="3 Main St", city="Pune"))
    db.add(ProviderLocation(provider_id=p.id, address_line_1="4 Main St", city="Pune"))
    db.commit()


def test_duplicate_specialization_link_rejected(db):
    p = _make_provider(db)
    s = Specialization(name="Cardiology")
    db.add(s)
    db.commit()
    db.add(ProviderSpecialization(provider_id=p.id, specialization_id=s.id))
    db.commit()
    db.add(ProviderSpecialization(provider_id=p.id, specialization_id=s.id))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_cascade_delete_children(db):
    p = _make_provider(db)
    s = Specialization(name="Neurology")
    db.add(s)
    db.commit()
    db.add_all([
        ProviderLocation(provider_id=p.id, address_line_1="1 Main St", city="Pune", is_primary=True),
        ProviderPhoto(provider_id=p.id, storage_reference="ref1", is_thumbnail=True),
        ProviderSpecialization(provider_id=p.id, specialization_id=s.id),
    ])
    db.commit()

    db.delete(p)
    db.commit()

    assert db.query(ProviderLocation).count() == 0
    assert db.query(ProviderPhoto).count() == 0
    assert db.query(ProviderSpecialization).count() == 0
    # Specialization master record must survive
    assert db.query(Specialization).count() == 1
