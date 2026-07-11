#!/usr/bin/env python3
"""Orientation detection using Xception-based classifier.

Detects whether a photo is rotated (0, 90, 180, or 270 degrees)
and provides correction.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

import torch
import torch.nn as nn
import torch.nn.functional as F


CLASS_TO_ANGLE = {0: 0, 1: 90, 2: 180, 3: 270}
NUM_CLASSES = 4
_INPUT_SIZE = (300, 300)


# ---------------------------------------------------------------------------
# Xception model definition (self-contained, no external deps beyond torch)
# Adapted from pretrained-models.pytorch
# ---------------------------------------------------------------------------

class SeparableConv2d(nn.Module):
    def __init__(self, in_channels, out_channels, kernel_size=1, stride=1, padding=0, dilation=1, bias=False):
        super().__init__()
        self.conv1 = nn.Conv2d(in_channels, in_channels, kernel_size, stride, padding, dilation, groups=in_channels, bias=bias)
        self.pointwise = nn.Conv2d(in_channels, out_channels, 1, 1, 0, 1, 1, bias=bias)

    def forward(self, x):
        x = self.conv1(x)
        x = self.pointwise(x)
        return x


class Block(nn.Module):
    def __init__(self, in_filters, out_filters, reps, strides=1, start_with_relu=True, grow_first=True):
        super().__init__()
        if out_filters != in_filters or strides != 1:
            self.skip = nn.Conv2d(in_filters, out_filters, 1, stride=strides, bias=False)
            self.skipbn = nn.BatchNorm2d(out_filters)
        else:
            self.skip = None

        rep = []
        filters = in_filters
        if grow_first:
            rep.append(nn.ReLU(inplace=True))
            rep.append(SeparableConv2d(in_filters, out_filters, 3, stride=1, padding=1, bias=False))
            rep.append(nn.BatchNorm2d(out_filters))
            filters = out_filters

        for _ in range(reps - 1):
            rep.append(nn.ReLU(inplace=True))
            rep.append(SeparableConv2d(filters, filters, 3, stride=1, padding=1, bias=False))
            rep.append(nn.BatchNorm2d(filters))

        if not grow_first:
            rep.append(nn.ReLU(inplace=True))
            rep.append(SeparableConv2d(in_filters, out_filters, 3, stride=1, padding=1, bias=False))
            rep.append(nn.BatchNorm2d(out_filters))

        if not start_with_relu:
            rep = rep[1:]
        else:
            rep[0] = nn.ReLU(inplace=False)

        if strides != 1:
            rep.append(nn.MaxPool2d(3, strides, 1))
        self.rep = nn.Sequential(*rep)

    def forward(self, inp):
        x = self.rep(inp)
        if self.skip is not None:
            skip = self.skip(inp)
            skip = self.skipbn(skip)
        else:
            skip = inp
        x += skip
        return x


class Xception(nn.Module):
    def __init__(self, num_classes=1000):
        super().__init__()
        self.num_classes = num_classes

        self.conv1 = nn.Conv2d(3, 32, 3, 2, 0, bias=False)
        self.bn1 = nn.BatchNorm2d(32)
        self.relu1 = nn.ReLU(inplace=True)

        self.conv2 = nn.Conv2d(32, 64, 3, bias=False)
        self.bn2 = nn.BatchNorm2d(64)
        self.relu2 = nn.ReLU(inplace=True)

        self.block1 = Block(64, 128, 2, 2, start_with_relu=False, grow_first=True)
        self.block2 = Block(128, 256, 2, 2, start_with_relu=True, grow_first=True)
        self.block3 = Block(256, 728, 2, 2, start_with_relu=True, grow_first=True)
        self.block4 = Block(728, 728, 3, 1, start_with_relu=True, grow_first=True)
        self.block5 = Block(728, 728, 3, 1, start_with_relu=True, grow_first=True)
        self.block6 = Block(728, 728, 3, 1, start_with_relu=True, grow_first=True)
        self.block7 = Block(728, 728, 3, 1, start_with_relu=True, grow_first=True)
        self.block8 = Block(728, 728, 3, 1, start_with_relu=True, grow_first=True)
        self.block9 = Block(728, 728, 3, 1, start_with_relu=True, grow_first=True)
        self.block10 = Block(728, 728, 3, 1, start_with_relu=True, grow_first=True)
        self.block11 = Block(728, 728, 3, 1, start_with_relu=True, grow_first=True)
        self.block12 = Block(728, 1024, 2, 2, start_with_relu=True, grow_first=False)

        self.conv3 = SeparableConv2d(1024, 1536, 3, 1, 1)
        self.bn3 = nn.BatchNorm2d(1536)
        self.relu3 = nn.ReLU(inplace=True)

        self.conv4 = SeparableConv2d(1536, 2048, 3, 1, 1)
        self.bn4 = nn.BatchNorm2d(2048)

        self.fc = nn.Linear(2048, num_classes)

    def features(self, input):
        x = self.conv1(input)
        x = self.bn1(x)
        x = self.relu1(x)
        x = self.conv2(x)
        x = self.bn2(x)
        x = self.relu2(x)
        x = self.block1(x)
        x = self.block2(x)
        x = self.block3(x)
        x = self.block4(x)
        x = self.block5(x)
        x = self.block6(x)
        x = self.block7(x)
        x = self.block8(x)
        x = self.block9(x)
        x = self.block10(x)
        x = self.block11(x)
        x = self.block12(x)
        x = self.conv3(x)
        x = self.bn3(x)
        x = self.relu3(x)
        x = self.conv4(x)
        x = self.bn4(x)
        return x

    def logits(self, features):
        x = nn.ReLU(inplace=True)(features)
        x = F.adaptive_avg_pool2d(x, (1, 1))
        x = x.view(x.size(0), -1)
        x = self.last_linear(x)
        return x

    def forward(self, input):
        x = self.features(input)
        x = self.logits(x)
        return x


# ---------------------------------------------------------------------------
# Orientation detector
# ---------------------------------------------------------------------------

class OrientationDetector:
    """Xception-based 4-way orientation classifier (0/90/180/270 degrees)."""

    _DEFAULT_WEIGHTS = Path(__file__).resolve().parent / "Xception_xception_1000_220318_best.pth"

    def __init__(self, weights_path: str | Path | None = None, device: str = "cpu"):
        self.device = device
        weights_path = Path(weights_path or self._DEFAULT_WEIGHTS)

        model = Xception(num_classes=NUM_CLASSES)
        model.last_linear = model.fc
        del model.fc
        model.last_linear = nn.Sequential(
            nn.Linear(2048, 128),
            nn.ReLU(inplace=True),
            nn.Linear(128, NUM_CLASSES),
        )

        ckpt = torch.load(str(weights_path), map_location=device, weights_only=False)
        state = ckpt.get("net", ckpt)
        state = {k: v for k, v in state.items()}

        remap = {"fc.0.": "last_linear.0.", "fc.2.": "last_linear.2."}
        for old_key in list(state.keys()):
            for old_prefix, new_prefix in remap.items():
                if old_key.startswith(old_prefix):
                    new_key = new_prefix + old_key[len(old_prefix):]
                    state[new_key] = state.pop(old_key)
                    break

        missing, unexpected = model.load_state_dict(state, strict=False)
        if missing:
            print(f"[orientation_detector] missing keys: {missing}", file=sys.stderr)

        model.to(device)
        model.eval()
        self.model = model

        self._mean = np.array([0.5, 0.5, 0.5], dtype=np.float32)
        self._std = np.array([0.5, 0.5, 0.5], dtype=np.float32)

    def _preprocess(self, frame_bgr: np.ndarray) -> torch.Tensor:
        import cv2
        rgb = frame_bgr[..., ::-1].astype(np.float32) / 255.0
        rgb = cv2.resize(rgb, _INPUT_SIZE)
        rgb = (rgb - self._mean) / self._std
        tensor = torch.from_numpy(rgb).permute(2, 0, 1).unsqueeze(0)
        return tensor

    def detect(self, frame_bgr: np.ndarray) -> int:
        x = self._preprocess(frame_bgr).to(self.device)
        with torch.no_grad():
            logits = self.model(x)
            pred = int(logits.argmax(dim=1).item())
        return pred

    def detect_angle(self, frame_bgr: np.ndarray) -> int:
        return CLASS_TO_ANGLE[self.detect(frame_bgr)]

    @staticmethod
    def correct(frame_bgr: np.ndarray, predicted_class: int) -> np.ndarray:
        import cv2
        angle = CLASS_TO_ANGLE.get(predicted_class, 0)
        if angle == 0:
            return frame_bgr
        if angle == 90:
            return cv2.rotate(frame_bgr, cv2.ROTATE_90_COUNTERCLOCKWISE)
        if angle == 180:
            return cv2.rotate(frame_bgr, cv2.ROTATE_180)
        if angle == 270:
            return cv2.rotate(frame_bgr, cv2.ROTATE_90_CLOCKWISE)
        return frame_bgr


# Module-level cache for the detector singleton.
_detector: OrientationDetector | None = None


def get_detector(weights_path: str | Path | None = None, device: str = "cpu") -> OrientationDetector:
    global _detector
    if _detector is None:
        _detector = OrientationDetector(weights_path, device)
    return _detector
