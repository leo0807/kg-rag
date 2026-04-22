from src.services.pdf_image_extractor import (
    compute_image_content_hash,
    register_image_hash,
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
