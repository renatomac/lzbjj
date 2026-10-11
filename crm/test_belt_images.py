from django.test import SimpleTestCase
from crm.templatetags.belt_images import belt_image_path, belt_image


class BeltImageTests(SimpleTestCase):
    def test_all_youth_monthly_combinations(self):
        prefixes = {
            "white": "W", "gray-white": "GyW", "gray": "Gy",
            "gray-black": "GyB", "yellow-white": "YW", "yellow": "Y",
            "yellow-black": "YB", "orange-white": "OW", "orange": "O",
            "orange-black": "OB", "green-white": "GnW", "green": "Gn",
            "green-black": "GnB",
        }
        suffixes = ["0", "1", "2", "3", "4", "1r", "2r",
                    "3r", "4r", "1y", "2y", "3y"]
        for rank, prefix in prefixes.items():
            for month, suffix in enumerate(suffixes):
                with self.subTest(rank=rank, month=month):
                    self.assertEqual(
                        belt_image_path(rank, month, "child"),
                        f"crm/img/belts/{prefix}{suffix}.svg",
                    )

    def test_adult_rank(self):
        self.assertEqual(belt_image_path("blue", 3, "adult"),
                         "crm/img/belts/B3.svg")

    def test_invalid_rank_and_stripes(self):
        self.assertIsNone(belt_image_path("not-a-belt", 0, "child"))
        self.assertIsNone(belt_image_path("gray", 12, "child"))
        self.assertIsNone(belt_image_path("blue", "unknown", "adult"))

    def test_accessible_image(self):
        html = str(belt_image("gray-white", 5, "child"))
        self.assertIn("GyW1r.svg", html)
        self.assertIn("alt=", html)

    def test_youth_rank_artwork_even_when_member_type_is_adult(self):
        cases = [
            ("green", 0, "Gn0.svg"),
            ("yellow", 0, "Y0.svg"),
            ("yellow", 6, "Y2r.svg"),
            ("gray", 1, "Gy1.svg"),
            ("gray-white", 1, "GyW1.svg"),
        ]
        for rank, stripes, filename in cases:
            for member_type in ("adult", "transition", "child"):
                with self.subTest(rank=rank, stripes=stripes, member_type=member_type):
                    self.assertEqual(
                        belt_image_path(rank, stripes, member_type),
                        "crm/img/belts/" + filename,
                    )

    def test_white_belt_with_monthly_stripes(self):
        self.assertEqual(
            belt_image_path("white", 6, "transition"),
            "crm/img/belts/W2r.svg",
        )
