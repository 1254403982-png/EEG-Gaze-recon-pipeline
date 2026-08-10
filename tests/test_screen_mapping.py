import unittest
from unittest.mock import patch

import cv2
import numpy as np
from PIL import Image

from recon_pipeline.gaze.screen_mapping import (
    MARKER_IDS,
    ScreenMapper,
    _dwell_target_for,
    _reading_aoi,
    _valid_marker_geometry,
)


class ScreenMappingTests(unittest.TestCase):
    def test_reading_aoi_prefers_the_reading_container(self):
        elements = [
            {
                "id": "paragraph-1",
                "tag": "p",
                "policy_region": "reading",
                "x_min": 0.1,
                "y_min": 0.2,
                "x_max": 0.5,
                "y_max": 0.3,
            },
            {
                "id": "reading-container",
                "tag": "readingContent",
                "policy_region": "reading",
                "x_min": 0.05,
                "y_min": 0.1,
                "x_max": 0.65,
                "y_max": 0.95,
            },
        ]

        aoi = _reading_aoi(elements)

        self.assertEqual(aoi["tag"], "readingContent")
        self.assertEqual(aoi["x_max"], 0.65)

    def test_dwell_target_requires_sustained_region_majority(self):
        elements = [
            {
                "id": "paragraph-1",
                "tag": "p",
                "text": "target paragraph",
                "x_min": 0.1,
                "y_min": 0.1,
                "x_max": 0.6,
                "y_max": 0.6,
            }
        ]
        sustained = [(0.3, 0.3, float(age)) for age in range(0, 2501, 100)]
        split = sustained[:14] + [(0.8, 0.8, float(age)) for age in range(1400, 2600, 100)]

        target = _dwell_target_for(sustained, elements)

        self.assertEqual(target["id"], "paragraph-1")
        self.assertEqual(target["dwell_ratio"], 1.0)
        self.assertIsNone(_dwell_target_for(split, elements))

    def test_dwell_target_retains_sentence_or_row_context(self):
        elements = [
            {
                "id": "table-heading",
                "tag": "th",
                "text": "特点",
                "context_text": "方法 特点 实现的目标",
                "policy_region": "reading",
                "x_min": 0.1,
                "y_min": 0.1,
                "x_max": 0.6,
                "y_max": 0.6,
            }
        ]
        points = [(0.3, 0.3, float(age)) for age in range(0, 2501, 100)]

        target = _dwell_target_for(points, elements)

        self.assertEqual(target["text"], "特点")
        self.assertEqual(target["context_text"], "方法 特点 实现的目标")

    def test_dwell_target_prefers_readable_leaf_over_broad_title_container(self):
        elements = [
            {
                "id": "readingTitle",
                "tag": "readingTitle",
                "text": "Broad material title",
                "policy_region": "reading",
                "x_min": 0.05,
                "y_min": 0.05,
                "x_max": 0.95,
                "y_max": 0.60,
            },
            {
                "id": "paragraph-1",
                "tag": "p",
                "text": "Specific paragraph under the title",
                "policy_region": "reading",
                "x_min": 0.10,
                "y_min": 0.40,
                "x_max": 0.90,
                "y_max": 0.55,
            },
        ]
        points = [(0.5, 0.45, float(age)) for age in range(0, 2501, 100)]

        target = _dwell_target_for(points, elements)

        self.assertEqual(target["id"], "paragraph-1")

    def test_rejects_narrow_false_interface_quadrilateral(self):
        detected = {
            10: (0.6926, 0.3888),
            11: (0.8277, 0.3012),
            12: (0.6751, 0.8235),
            13: (0.3364, 0.4660),
        }

        self.assertFalse(_valid_marker_geometry(detected, width=1, height=1))

    def test_rejects_interface_quad_stretched_to_second_screen(self):
        detected = {
            10: (0.3003, 0.3419),
            11: (0.7649, 0.3334),
            12: (0.8911, 0.9876),
            13: (0.3092, 0.7932),
        }

        self.assertFalse(_valid_marker_geometry(detected, width=1, height=1))

    def test_does_not_switch_anchor_source_during_a_brief_dropout(self):
        mapper = ScreenMapper()
        mapper._anchor_source = "screen_boundary"
        mapper._anchor_source_last_seen_at = 100.0
        points = {
            10: (80.0, 60.0),
            11: (720.0, 60.0),
            12: (720.0, 440.0),
            13: (80.0, 440.0),
        }
        image = Image.fromarray(np.full((500, 800, 3), 245, dtype=np.uint8))

        with (
            patch("recon_pipeline.gaze.screen_mapping.time.monotonic", return_value=100.1),
            patch(
                "recon_pipeline.gaze.screen_mapping._detect_interface_anchors",
                return_value=points,
            ),
            patch(
                "recon_pipeline.gaze.screen_mapping._detect_screen_boundary_anchors",
                return_value={},
            ),
        ):
            detected = mapper._detect(image)

        self.assertEqual(detected, {})
        self.assertEqual(mapper._anchor_source, "screen_boundary")

    def test_monitor_boundary_fallback_needs_no_colored_blocks(self):
        width, height = 1000, 700
        image = np.full((height, width, 3), 35, dtype=np.uint8)
        screen_corners = np.asarray(
            ((150, 90), (890, 55), (930, 620), (95, 590)), dtype=np.int32
        )
        cv2.fillConvexPoly(image, screen_corners, (205, 205, 205))
        cv2.polylines(image, [screen_corners], True, (8, 8, 8), 12)
        center_scene = cv2.perspectiveTransform(
            np.asarray([[[0.5, 0.5]]], dtype=np.float32),
            cv2.getPerspectiveTransform(
                np.asarray(((0, 0), (1, 0), (1, 1), (0, 1)), dtype=np.float32),
                screen_corners.astype(np.float32),
            ),
        )[0][0]
        centers = {
            10: (0.06, 0.07),
            11: (0.94, 0.07),
            12: (0.94, 0.93),
            13: (0.07, 0.93),
        }
        mapper = ScreenMapper()
        mapper.update_layout(
            {
                "viewport": {"width": 2560, "height": 1440},
                "markers": [
                    {"id": marker_id, "x_normalized": x, "y_normalized": y}
                    for marker_id, (x, y) in centers.items()
                ],
            }
        )

        result = mapper.process_frame(
            Image.fromarray(image),
            [(float(center_scene[0] / width), float(center_scene[1] / height), 10.0)],
            now_monotonic=100.0,
        )

        self.assertTrue(result["valid"])
        self.assertEqual(result["detected_marker_ids"], list(MARKER_IDS))
        self.assertEqual(result["anchor_source"], "screen_boundary")
        self.assertAlmostEqual(result["screen_x_normalized"], 0.5, delta=0.035)
        self.assertAlmostEqual(result["screen_y_normalized"], 0.5, delta=0.035)

    def test_natural_controls_survive_dim_scene_camera_exposure(self):
        width, height = 800, 500
        image = np.full((height, width, 3), 42, dtype=np.uint8)
        centers = {
            10: (0.08, 0.09),
            11: (0.93, 0.08),
            12: (0.92, 0.91),
            13: (0.09, 0.92),
        }
        orange = (46, 32, 20)
        blue = (20, 30, 55)
        for marker_id, (x, y) in centers.items():
            center_x = round(x * width)
            center_y = round(y * height)
            half_width = 18 if marker_id in {10, 11} else 30
            half_height = 16 if marker_id in {10, 11} else 14
            image[
                center_y - half_height : center_y + half_height,
                center_x - half_width : center_x + half_width,
            ] = orange if marker_id == 10 else blue

        mapper = ScreenMapper()
        mapper.update_layout(
            {
                "viewport": {"width": width, "height": height},
                "markers": [
                    {"id": marker_id, "x_normalized": x, "y_normalized": y}
                    for marker_id, (x, y) in centers.items()
                ],
            }
        )

        result = mapper.process_frame(
            Image.fromarray(image),
            [(0.5, 0.5, 10.0)],
            now_monotonic=100.0,
        )

        self.assertTrue(result["valid"])
        self.assertEqual(result["detected_marker_ids"], list(MARKER_IDS))
        self.assertEqual(result["anchor_source"], "interface")
        self.assertAlmostEqual(result["screen_x_normalized"], 0.5, delta=0.02)
        self.assertAlmostEqual(result["screen_y_normalized"], 0.5, delta=0.02)

    def test_natural_interface_controls_form_screen_anchors(self):
        width, height = 800, 500
        image = np.full((height, width, 3), 245, dtype=np.uint8)
        centers = {
            10: (0.06, 0.07),
            11: (0.94, 0.07),
            12: (0.94, 0.93),
            13: (0.07, 0.93),
        }
        orange = (255, 90, 1)
        blue = (36, 95, 159)
        logo = (round(centers[10][0] * width), round(centers[10][1] * height))
        image[logo[1] - 12 : logo[1] + 12, logo[0] - 18 : logo[0] + 18] = orange
        assistant = (round(centers[11][0] * width), round(centers[11][1] * height))
        image[
            assistant[1] - 16 : assistant[1] + 16,
            assistant[0] - 16 : assistant[0] + 16,
        ] = blue
        for marker_id in (12, 13):
            x, y = centers[marker_id]
            center = (round(x * width), round(y * height))
            image[center[1] - 14 : center[1] + 14, center[0] - 30 : center[0] + 30] = blue

        # Blue content inside the page must not replace the four outer controls.
        image[145:190, 250:420] = blue
        image[260:266, 40:300] = blue
        mapper = ScreenMapper()
        mapper.update_layout(
            {
                "viewport": {"width": width, "height": height},
                "markers": [
                    {"id": marker_id, "x_normalized": x, "y_normalized": y}
                    for marker_id, (x, y) in centers.items()
                ],
            }
        )

        result = mapper.process_frame(
            Image.fromarray(image),
            [(0.5, 0.5, 10.0)],
            now_monotonic=100.0,
        )

        self.assertTrue(result["valid"])
        self.assertEqual(result["detected_marker_ids"], list(MARKER_IDS))
        self.assertEqual(result["anchor_source"], "interface")
        self.assertAlmostEqual(result["screen_x_normalized"], 0.5, delta=0.02)
        self.assertAlmostEqual(result["screen_y_normalized"], 0.5, delta=0.02)

    def test_blue_chat_bubbles_and_selected_level_do_not_replace_anchors(self):
        width, height = 1000, 700
        image = np.full((height, width, 3), 245, dtype=np.uint8)
        centers = {
            10: (0.04, 0.04),
            11: (0.97, 0.04),
            12: (0.95, 0.95),
            13: (0.05, 0.95),
        }
        orange = (255, 90, 1)
        blue = (36, 95, 159)
        image[15:42, 20:62] = orange
        image[12:50, 952:990] = blue
        image[650:680, 900:990] = blue
        image[650:680, 15:110] = blue
        # Dynamic conversation bubbles and the selected explanation level.
        image[90:135, 705:940] = blue
        image[170:255, 680:910] = blue
        image[600:635, 650:825] = blue
        mapper = ScreenMapper()
        mapper.update_layout(
            {
                "viewport": {"width": width, "height": height},
                "markers": [
                    {"id": marker_id, "x_normalized": x, "y_normalized": y}
                    for marker_id, (x, y) in centers.items()
                ],
            }
        )

        result = mapper.process_frame(
            Image.fromarray(image),
            [(0.5, 0.5, 10.0)],
            now_monotonic=100.0,
        )

        self.assertTrue(result["valid"])
        self.assertEqual(result["anchor_source"], "interface")
        self.assertAlmostEqual(result["screen_x_normalized"], 0.5, delta=0.03)
        self.assertAlmostEqual(result["screen_y_normalized"], 0.5, delta=0.03)

    def test_head_motion_does_not_reproject_historical_screen_samples(self):
        width, height = 800, 500
        centers = {
            10: (0.03, 0.05),
            11: (0.97, 0.05),
            12: (0.97, 0.95),
            13: (0.03, 0.95),
        }

        def frame(horizontal_shift: int) -> Image.Image:
            image = np.full((height, width, 3), 245, dtype=np.uint8)
            colors = {
                10: (0, 229, 255),
                11: (255, 43, 214),
                12: (255, 230, 0),
                13: (40, 224, 111),
            }
            for marker_id, (x, y) in centers.items():
                center_x = round(x * width) + horizontal_shift
                center_y = round(y * height)
                image[center_y - 12 : center_y + 12, center_x - 12 : center_x + 12] = (
                    colors[marker_id]
                )
            return Image.fromarray(image)

        mapper = ScreenMapper()
        mapper.update_layout(
            {
                "viewport": {"width": width, "height": height},
                "markers": [
                    {"id": marker_id, "x_normalized": x, "y_normalized": y}
                    for marker_id, (x, y) in centers.items()
                ],
            }
        )
        mapper.process_frame(frame(0), [], now_monotonic=100.0)
        mapped = mapper.map_point(0.25, 0.25, now_monotonic=100.05)
        self.assertTrue(mapped["valid"])

        result = mapper.process_frame(frame(35), [], now_monotonic=100.10)

        self.assertTrue(result["valid"])
        self.assertEqual(len(result["trajectory"]), 1)
        self.assertAlmostEqual(result["trajectory"][0]["x_normalized"], 0.25, delta=0.01)

    def test_single_frame_corner_jump_keeps_previous_homography(self):
        width, height = 800, 500
        layout = {
            10: (0.06, 0.07),
            11: (0.94, 0.07),
            12: (0.94, 0.93),
            13: (0.07, 0.93),
        }
        stable = {
            10: (90.0, 70.0),
            11: (710.0, 65.0),
            12: (720.0, 440.0),
            13: (80.0, 435.0),
        }
        false_second_screen = {
            10: (90.0, 70.0),
            11: (710.0, 65.0),
            12: (795.0, 495.0),
            13: (80.0, 435.0),
        }
        mapper = ScreenMapper()
        mapper.update_layout(
            {
                "viewport": {"width": width, "height": height},
                "markers": [
                    {"id": marker_id, "x_normalized": x, "y_normalized": y}
                    for marker_id, (x, y) in layout.items()
                ],
            }
        )
        image = Image.fromarray(np.full((height, width, 3), 245, dtype=np.uint8))
        with patch.object(mapper, "_detect", side_effect=[stable, false_second_screen]):
            first = mapper.process_frame(image, [], now_monotonic=100.0)
            second = mapper.process_frame(image, [], now_monotonic=100.04)

        self.assertEqual(first["status"], "valid")
        self.assertEqual(second["status"], "tracking_hold")
        np.testing.assert_allclose(second["homography"], first["homography"])

    def test_small_color_fiducials_support_low_interference_mapping(self):
        width, height = 800, 500
        image = np.full((height, width, 3), 245, dtype=np.uint8)
        colors = {
            10: (0, 229, 255),
            11: (255, 43, 214),
            12: (255, 230, 0),
            13: (40, 224, 111),
        }
        centers = {
            10: (0.03, 0.05),
            11: (0.97, 0.05),
            12: (0.97, 0.95),
            13: (0.03, 0.95),
        }
        for marker_id, (x, y) in centers.items():
            center_x, center_y = round(x * width), round(y * height)
            image[center_y - 12 : center_y + 12, center_x - 12 : center_x + 12] = colors[
                marker_id
            ]
        mapper = ScreenMapper()
        mapper.update_layout(
            {
                "viewport": {"width": width, "height": height},
                "markers": [
                    {"id": marker_id, "x_normalized": x, "y_normalized": y}
                    for marker_id, (x, y) in centers.items()
                ],
            }
        )

        result = mapper.process_frame(
            Image.fromarray(image),
            [(0.5, 0.5, 10.0)],
            now_monotonic=100.0,
        )

        self.assertTrue(result["valid"])
        self.assertEqual(result["detected_marker_ids"], list(MARKER_IDS))
        self.assertAlmostEqual(result["screen_x_normalized"], 0.5, delta=0.01)
        self.assertAlmostEqual(result["screen_y_normalized"], 0.5, delta=0.01)

    def test_each_gaze_sample_immediately_updates_monitor_snapshot(self):
        width, height = 800, 500
        centers = {
            10: (0.03, 0.05),
            11: (0.97, 0.05),
            12: (0.97, 0.95),
            13: (0.03, 0.95),
        }
        image = np.full((height, width, 3), 245, dtype=np.uint8)
        colors = {10: (0, 229, 255), 11: (255, 43, 214), 12: (255, 230, 0), 13: (40, 224, 111)}
        for marker_id, (x, y) in centers.items():
            center_x, center_y = round(x * width), round(y * height)
            image[center_y - 12 : center_y + 12, center_x - 12 : center_x + 12] = colors[
                marker_id
            ]
        mapper = ScreenMapper()
        mapper.update_layout(
            {
                "viewport": {"width": width, "height": height},
                "markers": [
                    {"id": marker_id, "x_normalized": x, "y_normalized": y}
                    for marker_id, (x, y) in centers.items()
                ],
            }
        )
        mapper.process_frame(Image.fromarray(image), [], now_monotonic=100.0)

        mapped = mapper.map_point(0.72, 0.64, now_monotonic=100.01)
        snapshot = mapper.snapshot()

        self.assertTrue(mapped["valid"])
        self.assertAlmostEqual(snapshot["screen_x_normalized"], mapped["x_normalized"])
        self.assertAlmostEqual(snapshot["screen_y_normalized"], mapped["y_normalized"])
        self.assertEqual(len(snapshot["trajectory"]), 1)

    def test_display_point_rejects_a_single_mapped_outlier(self):
        mapper = ScreenMapper()
        mapper._homography = np.asarray(
            ((1 / 800, 0, 0), (0, 1 / 500, 0), (0, 0, 1)),
            dtype=np.float32,
        )
        mapper._frame_size = (800, 500)
        mapper._last_homography_at = 100.0
        mapper._latest = {"valid": True, "status": "valid"}

        for index in range(6):
            mapper.map_point(0.5, 0.5, now_monotonic=100.01 + index * 0.01)
        mapped = mapper.map_point(0.9, 0.1, now_monotonic=100.08)
        snapshot = mapper.snapshot()

        self.assertAlmostEqual(mapped["x_normalized"], 0.9)
        self.assertAlmostEqual(mapped["y_normalized"], 0.1)
        self.assertAlmostEqual(snapshot["display_x_normalized"], 0.5, delta=0.02)
        self.assertAlmostEqual(snapshot["display_y_normalized"], 0.5, delta=0.02)

    def test_perspective_warp_maps_scene_gaze_back_to_experiment_content(self):
        width, height = 800, 500
        marker_size = 80
        margin = 20
        screen = np.full((height, width), 255, dtype=np.uint8)
        dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        positions = {
            10: (margin, margin),
            11: (width - margin - marker_size, margin),
            12: (width - margin - marker_size, height - margin - marker_size),
            13: (margin, height - margin - marker_size),
        }
        centers = {}
        for marker_id, (left, top) in positions.items():
            marker = cv2.aruco.generateImageMarker(dictionary, marker_id, marker_size)
            screen[top : top + marker_size, left : left + marker_size] = marker
            centers[marker_id] = (
                (left + marker_size / 2) / width,
                (top + marker_size / 2) / height,
            )

        scene_width, scene_height = 1000, 700
        source_corners = np.float32([[0, 0], [width, 0], [width, height], [0, height]])
        scene_corners = np.float32([[130, 90], [890, 55], [930, 640], [80, 590]])
        screen_to_scene = cv2.getPerspectiveTransform(source_corners, scene_corners)
        scene = cv2.warpPerspective(
            screen,
            screen_to_scene,
            (scene_width, scene_height),
            borderValue=210,
        )
        center_scene = cv2.perspectiveTransform(
            np.float32([[[width / 2, height / 2]]]), screen_to_scene
        )[0][0]

        mapper = ScreenMapper()
        mapper.update_layout(
            {
                "viewport": {"width": width, "height": height},
                "markers": [
                    {
                        "id": marker_id,
                        "x_normalized": centers[marker_id][0],
                        "y_normalized": centers[marker_id][1],
                    }
                    for marker_id in MARKER_IDS
                ],
                "elements": [
                    {
                        "id": "paragraph-1",
                        "tag": "p",
                        "text": "需要被映射命中的实验内容",
                        "x_min": 0.4,
                        "y_min": 0.4,
                        "x_max": 0.6,
                        "y_max": 0.6,
                    }
                ],
                "trial_id": "T01",
                "slide_id": "1",
                "reading_scroll": {"top": 120, "height": 1800, "client_height": 720},
                "mirror": {
                    "reading_title": "测试材料",
                    "reading_html": "<p>正文</p>",
                    "chat_html": "<div>详细解释: 正文</div>",
                    "chat_scroll_top": 88,
                    "selected_level": "详细解释",
                },
            }
        )

        result = mapper.process_frame(
            Image.fromarray(scene),
            [
                (
                    float(center_scene[0] / scene_width),
                    float(center_scene[1] / scene_height),
                    20.0,
                )
            ],
            now_monotonic=100.0,
        )

        self.assertTrue(result["valid"])
        self.assertEqual(result["detected_marker_ids"], list(MARKER_IDS))
        self.assertAlmostEqual(result["screen_x_normalized"], 0.5, delta=0.02)
        self.assertAlmostEqual(result["screen_y_normalized"], 0.5, delta=0.02)
        self.assertEqual(result["target"]["id"], "paragraph-1")
        self.assertEqual(mapper.dashboard_snapshot()["layout"]["reading_scroll"]["top"], 120)
        mirror = mapper.dashboard_snapshot()["layout"]["mirror"]
        self.assertEqual(mirror["reading_title"], "测试材料")
        self.assertEqual(mirror["chat_scroll_top"], 88)

    def test_layout_requires_all_four_markers(self):
        mapper = ScreenMapper()
        with self.assertRaisesRegex(ValueError, "four screen markers"):
            mapper.update_layout(
                {
                    "viewport": {"width": 1920, "height": 1080},
                    "markers": [{"id": 10, "x_normalized": 0.02, "y_normalized": 0.02}],
                }
            )

    def test_layout_rejects_degenerate_marker_geometry(self):
        mapper = ScreenMapper()

        with self.assertRaisesRegex(ValueError, "geometry is degenerate"):
            mapper.update_layout(
                {
                    "viewport": {"width": 1920, "height": 1080},
                    "markers": [
                        {"id": marker_id, "x_normalized": 0.0, "y_normalized": 0.0}
                        for marker_id in MARKER_IDS
                    ],
                }
            )


if __name__ == "__main__":
    unittest.main()
