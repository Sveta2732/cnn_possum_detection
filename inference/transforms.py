from torchvision import transforms

# Custom transform that resizes image while preserving aspect ratio
class ResizeWithPadding:
    def __init__(self, size=224, fill=0):
        self.size = size
        self.fill = fill

    def __call__(self, img):
        # Original image size
        w, h = img.size
        # Calculates scaling factor based on longest side
        scale = self.size / max(w, h)

        new_w, new_h = int(w * scale), int(h * scale)

        # Resizes image while maintaining aspect ratio
        img = transforms.functional.resize(img, (new_h, new_w))

        pad_w = self.size - new_w
        pad_h = self.size - new_h

        padding = (
            pad_w // 2,
            pad_h // 2,
            pad_w - pad_w // 2,
            pad_h - pad_h // 2
        )

        return transforms.functional.pad(img, padding, fill=self.fill)

# Transform for inference
def build_test_transform():
    mean = [0.485, 0.456, 0.406]
    std = [0.229, 0.224, 0.225]

    return transforms.Compose([
        ResizeWithPadding(224),
        transforms.ToTensor(),
        transforms.Normalize(mean, std)
    ])

def expand_bbox(bbox, frame_shape, scale=1.8):
    """
    Expands bounding box by a scale factor while keeping it inside frame boundaries.

    """
    x1, y1, x2, y2 = bbox
    h, w = frame_shape[:2]

    box_width = x2 - x1
    box_height = y2 - y1

    new_width = int(box_width * scale)
    new_height = int(box_height * scale)

    center_x = x1 + box_width // 2
    center_y = y1 + box_height // 2

    x1_new = center_x - new_width // 2
    x2_new = center_x + new_width // 2
    y1_new = center_y - new_height // 2
    y2_new = center_y + new_height // 2

    # Clamp to frame boundaries
    x1_new = max(0, x1_new)
    y1_new = max(0, y1_new)
    x2_new = min(w, x2_new)
    y2_new = min(h, y2_new)

    return int(x1_new), int(y1_new), int(x2_new), int(y2_new)