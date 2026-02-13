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