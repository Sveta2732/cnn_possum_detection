import logging
DEFAULT_FENCE_Y_THRESHOLD = 500


def is_under_fence(bbox, fence_y_threshold=DEFAULT_FENCE_Y_THRESHOLD):
    """
    Determines whether bbox center is below fence line.

    """
    x1, y1, x2, y2 = bbox
    center_y = (y1 + y2) // 2
    logging.info(f"Last bbox center_y: {center_y}")
    return center_y > fence_y_threshold