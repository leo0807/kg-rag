from src.services.images.pdf_image_extractor import (
    compute_image_content_hash,
    extract_images_from_document,
    register_image_hash,
    _should_fallback_to_page_snapshots,
)


class TestImageDedup:
    def test_same_bytes_produce_same_hash(self):
        image_bytes = b"fake-image-binary"

        assert compute_image_content_hash(image_bytes) == compute_image_content_hash(image_bytes)

    def test_register_image_hash_marks_duplicates(self):
        seen_hashes: set[str] = set()
        image_bytes = b"same-image"

        first_hash, first_duplicate = register_image_hash(seen_hashes, image_bytes)
        second_hash, second_duplicate = register_image_hash(seen_hashes, image_bytes)

        assert first_hash == second_hash
        assert first_duplicate is False
        assert second_duplicate is True

    def test_register_image_hash_keeps_distinct_images(self):
        seen_hashes: set[str] = set()

        first_hash, first_duplicate = register_image_hash(seen_hashes, b"image-a")
        second_hash, second_duplicate = register_image_hash(seen_hashes, b"image-b")

        assert first_hash != second_hash
        assert first_duplicate is False
        assert second_duplicate is False


class _FakePage:
    def __init__(self, xrefs):
        self._xrefs = xrefs

    def get_images(self, full=True):
        return [(xref,) for xref in self._xrefs]


class TestOfficePdfFallback:
    def test_detects_shared_embedded_resources_across_pages(self):
        doc = [_FakePage(list(range(1, 111))) for _ in range(4)]

        assert _should_fallback_to_page_snapshots(doc) is True

    def test_keeps_normal_pdf_on_small_distinct_sets(self):
        doc = [
            _FakePage([1, 2]),
            _FakePage([3, 4]),
            _FakePage([5, 6]),
        ]

        assert _should_fallback_to_page_snapshots(doc) is False


def test_extract_images_from_document_prefers_docx_path(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(
        "src.services.images.pdf_image_extractor._extract_images_from_docx",
        lambda source_path, doc_id, sections=None: [sentinel],
    )

    results = extract_images_from_document("CPS1000.docx", "CPS1000", [])

    assert results == [sentinel]
